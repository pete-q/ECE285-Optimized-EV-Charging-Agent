"""Natural-language problem parser: extract structured EV session data from free text.

This module owns the first LLM call in the NL-input pipeline. It sends the
user's raw text to the LLM with a structured extraction prompt and returns
either a complete ParsedProblem (ready for the solver) or a ClarificationResult
asking the user for the missing information.

Typical flow:
    result = parse_nl_problem(user_text, api_key=key)
    if result.needs_clarification:
        print(result.clarification_message)
    else:
        day, site, tou = parsed_problem_to_day_site_tou(result.problem)
        agent_result = run_agent(day, site, tou, request=user_text)
"""

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from config.site import SiteConfig, TOUConfig, default_tou_rates
from data.format.schema import DaySessions, Session


# ---------------------------------------------------------------------------
# Dataclasses for the parsed representation
# ---------------------------------------------------------------------------

@dataclass
class ParsedSession:
    """One EV charging session extracted from natural language.

    Times are in fractional hours from midnight (e.g. 18.5 = 6:30 pm).
    Any field may be None if the LLM could not determine it from the text.

    Attributes:
        arrival_hour: Hour of arrival (0–24). None if not mentioned.
        departure_hour: Hour of departure (0–24). None if not mentioned.
        energy_kwh: Energy requested (kWh). None if not mentioned.
        max_power_kw: Max charging rate (kW). Defaults to 7.2 (Level 2).
        session_id: Optional label (e.g. "EV-1").
        charger_id: Optional charger label.
    """

    arrival_hour: Optional[float]
    departure_hour: Optional[float]
    energy_kwh: Optional[float]
    max_power_kw: float = 7.2
    session_id: str = ""
    charger_id: str = ""


@dataclass
class ParsedProblem:
    """Complete structured problem extracted from natural language.

    Attributes:
        sessions: List of parsed EV sessions.
        n_steps: Time horizon in steps (default 96 = 24 h at 15-min resolution).
        dt_hours: Step duration in hours (default 0.25).
        site_cap_kw: Site power cap in kW (default 50.0).
        peak_price: TOU peak rate in $/kWh (default 0.45).
        off_peak_price: TOU off-peak rate in $/kWh (default 0.12).
    """

    sessions: List[ParsedSession]
    n_steps: int = 96
    dt_hours: float = 0.25
    site_cap_kw: float = 50.0
    peak_price: float = 0.45
    off_peak_price: float = 0.12


@dataclass
class ParseResult:
    """Result of attempting to parse a natural-language problem description.

    Attributes:
        problem: Fully populated ParsedProblem, or None if clarification needed.
        needs_clarification: True when required fields are missing.
        clarification_message: Human-readable question to ask the user.
        raw_llm_response: Raw text returned by the LLM (for debugging).
    """

    problem: Optional[ParsedProblem]
    needs_clarification: bool
    clarification_message: str = ""
    raw_llm_response: str = ""


# ---------------------------------------------------------------------------
# Extraction prompt
# ---------------------------------------------------------------------------

_EXTRACTION_SYSTEM = (
    "You are a data-extraction assistant for an EV charging scheduler. "
    "Your only job is to read the user's message and extract EV charging session "
    "details into a JSON object. Output ONLY valid JSON — no prose, no markdown fences.\n\n"
    "Return an object with this exact schema:\n"
    "{\n"
    '  "sessions": [\n'
    "    {\n"
    '      "session_id": "EV-1",          // label, or empty string\n'
    '      "arrival_hour": 18.0,          // hour from midnight (0-24), or null if unknown\n'
    '      "departure_hour": 22.0,        // hour from midnight (0-24), or null if unknown\n'
    '      "energy_kwh": 20.0,            // kWh requested, or null if unknown\n'
    '      "max_power_kw": 7.2            // max charging rate kW; default 7.2 if not stated\n'
    "    }\n"
    "  ],\n"
    '  "site_cap_kw": 50.0,              // total site power cap kW; null if not stated\n'
    '  "peak_price": 0.45,               // $/kWh peak TOU rate; null if not stated\n'
    '  "off_peak_price": 0.12            // $/kWh off-peak TOU rate; null if not stated\n'
    "}\n\n"
    "Rules:\n"
    "- Convert time expressions to fractional hours: '6pm' → 18.0, '6:30pm' → 18.5, "
    "'midnight' → 0.0, 'noon' → 12.0.\n"
    "- If the user says 'overnight' or 'all night', use arrival_hour=22.0, departure_hour=7.0.\n"
    "- If the user gives a range like '20-30 kWh', use the midpoint (25.0).\n"
    "- If the user says 'standard charger' or 'Level 2', use max_power_kw=7.2.\n"
    "- If the user says 'fast charger' or 'DC fast', use max_power_kw=50.0.\n"
    "- Do NOT invent values the user did not provide — use null for unknown required fields.\n"
    "- Output ONLY the JSON object. No explanation."
)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _missing_fields(sessions: List[ParsedSession]) -> List[str]:
    """Return a list of human-readable descriptions of missing required fields."""
    missing: List[str] = []
    for i, sess in enumerate(sessions):
        label = sess.session_id or f"EV {i + 1}"
        if sess.arrival_hour is None:
            missing.append(f"{label}: arrival time")
        if sess.departure_hour is None:
            missing.append(f"{label}: departure time")
        if sess.energy_kwh is None:
            missing.append(f"{label}: energy needed (kWh)")
    return missing


def _build_clarification_message(missing: List[str]) -> str:
    """Build a friendly clarification question from a list of missing fields."""
    lines = [
        "To compute the optimal charging schedule I need a few more details:",
        "",
    ]
    for item in missing:
        lines.append(f"  • {item}")
    lines.append("")
    lines.append(
        "For example: \"EV 1 arrives at 6 pm, leaves at 10 pm, needs 18 kWh.\""
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSON parsing helpers
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> str:
    """Strip markdown fences and extract the first JSON object from text."""
    # Remove ```json ... ``` or ``` ... ``` fences
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"```", "", text)
    # Find first { ... } block
    start = text.find("{")
    if start == -1:
        return text.strip()
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return text[start:].strip()


def _parse_llm_json(raw: str) -> Dict[str, Any]:
    """Parse the LLM's JSON response into a dict, tolerating minor formatting issues."""
    cleaned = _extract_json(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned invalid JSON: {exc}\nRaw: {raw!r}") from exc


def _session_from_dict(d: Dict[str, Any], index: int) -> ParsedSession:
    """Build a ParsedSession from one element of the LLM's sessions array."""
    def _float_or_none(v: Any) -> Optional[float]:
        return None if v is None else float(v)

    return ParsedSession(
        arrival_hour=_float_or_none(d.get("arrival_hour")),
        departure_hour=_float_or_none(d.get("departure_hour")),
        energy_kwh=_float_or_none(d.get("energy_kwh")),
        max_power_kw=float(d.get("max_power_kw") or 7.2),
        session_id=str(d.get("session_id") or f"EV-{index + 1}"),
        charger_id=str(d.get("charger_id") or f"charger-{index + 1}"),
    )


# ---------------------------------------------------------------------------
# Main parse function
# ---------------------------------------------------------------------------

def parse_nl_problem(
    user_text: str,
    *,
    model: str = "gpt-4o",
    api_key: Optional[str] = None,
) -> ParseResult:
    """Extract a structured EV charging problem from natural-language text.

    Sends one LLM call to extract session details (arrival, departure, energy,
    power) and optional site/TOU parameters. Validates the result and returns
    either a complete ParsedProblem or a clarification request.

    Args:
        user_text: Free-form user description of the charging problem.
        model: OpenAI model name.
        api_key: OpenAI API key (falls back to OPENAI_API_KEY env var).

    Returns:
        ParseResult with either a populated problem or needs_clarification=True
        and a clarification_message explaining what is missing.

    Raises:
        ValueError: If OPENAI_API_KEY is not set.
        ImportError: If the openai package is not installed.
    """
    key = api_key or os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise ValueError(
            "OPENAI_API_KEY is not set. Set it in .env or pass api_key to parse_nl_problem."
        )

    try:
        from openai import OpenAI  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "The 'openai' package is not installed. "
            "Install it with 'pip install openai>=1.0.0'."
        ) from exc

    client = OpenAI(api_key=key)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _EXTRACTION_SYSTEM},
            {"role": "user", "content": user_text},
        ],
        temperature=0.0,
    )

    raw = (response.choices[0].message.content or "").strip()

    # Parse JSON
    try:
        data = _parse_llm_json(raw)
    except ValueError:
        # LLM returned something unparseable — ask for clarification
        return ParseResult(
            problem=None,
            needs_clarification=True,
            clarification_message=(
                "I wasn't able to extract structured session data from your message. "
                "Could you describe each EV's arrival time, departure time, and energy "
                "needed? For example: \"EV 1 arrives at 6 pm, leaves at 10 pm, needs 20 kWh.\""
            ),
            raw_llm_response=raw,
        )

    # Build ParsedSession list
    raw_sessions: List[Dict[str, Any]] = data.get("sessions") or []
    if not raw_sessions:
        return ParseResult(
            problem=None,
            needs_clarification=True,
            clarification_message=(
                "I couldn't find any EV sessions in your message. "
                "Please describe each EV: how many EVs, when they arrive and depart, "
                "and how much energy each one needs."
            ),
            raw_llm_response=raw,
        )

    sessions = [_session_from_dict(s, i) for i, s in enumerate(raw_sessions)]

    # Validate — check for missing required fields
    missing = _missing_fields(sessions)
    if missing:
        return ParseResult(
            problem=None,
            needs_clarification=True,
            clarification_message=_build_clarification_message(missing),
            raw_llm_response=raw,
        )

    # Build ParsedProblem with defaults for any optional site/TOU fields
    def _float_default(v: Any, default: float) -> float:
        return default if v is None else float(v)

    problem = ParsedProblem(
        sessions=sessions,
        n_steps=96,
        dt_hours=0.25,
        site_cap_kw=_float_default(data.get("site_cap_kw"), 50.0),
        peak_price=_float_default(data.get("peak_price"), 0.45),
        off_peak_price=_float_default(data.get("off_peak_price"), 0.12),
    )

    return ParseResult(
        problem=problem,
        needs_clarification=False,
        raw_llm_response=raw,
    )


# ---------------------------------------------------------------------------
# Converter: ParsedProblem → DaySessions + SiteConfig + TOUConfig
# ---------------------------------------------------------------------------

def parsed_problem_to_day_site_tou(
    problem: ParsedProblem,
) -> tuple[DaySessions, SiteConfig, TOUConfig]:
    """Convert a ParsedProblem into the typed inputs expected by the solver.

    Converts fractional arrival/departure hours to step indices using the
    problem's dt_hours. Clamps indices to [0, n_steps] and ensures
    arrival_idx < departure_idx. Assigns sequential session_id / charger_id
    labels if not already set.

    Args:
        problem: Fully populated ParsedProblem (no None fields in sessions).

    Returns:
        Tuple of (DaySessions, SiteConfig, TOUConfig) ready for run_agent().

    Raises:
        ValueError: If any session has arrival_idx >= departure_idx after
            clamping, or if energy_kwh is non-positive.
    """
    n_steps = problem.n_steps
    dt = problem.dt_hours

    sessions: List[Session] = []
    for i, ps in enumerate(problem.sessions):
        # arrival_hour and departure_hour are guaranteed non-None by parse_nl_problem
        arrival_idx = int(round(ps.arrival_hour / dt))  # type: ignore[arg-type]
        departure_idx = int(round(ps.departure_hour / dt))  # type: ignore[arg-type]

        # Handle overnight sessions (departure < arrival in clock time)
        if departure_idx <= arrival_idx:
            departure_idx = arrival_idx + max(1, int(round(1.0 / dt)))

        # Clamp to horizon
        arrival_idx = max(0, min(arrival_idx, n_steps - 1))
        departure_idx = max(arrival_idx + 1, min(departure_idx, n_steps))

        energy_kwh = float(ps.energy_kwh)  # type: ignore[arg-type]
        if energy_kwh <= 0:
            energy_kwh = 1.0  # safe fallback

        sessions.append(
            Session(
                session_id=ps.session_id or f"EV-{i + 1}",
                arrival_idx=arrival_idx,
                departure_idx=departure_idx,
                energy_kwh=energy_kwh,
                charger_id=ps.charger_id or f"charger-{i + 1}",
                max_power_kw=max(0.1, ps.max_power_kw),
            )
        )

    day = DaySessions(sessions=sessions, n_steps=n_steps, dt_hours=dt)
    site = SiteConfig(P_max_kw=problem.site_cap_kw, n_steps=n_steps, dt_hours=dt)
    tou = TOUConfig(
        rates_per_kwh=default_tou_rates(
            n_steps,
            peak_price=problem.peak_price,
            off_peak_price=problem.off_peak_price,
        )
    )
    return day, site, tou
