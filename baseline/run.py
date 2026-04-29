"""Baseline runner: build prompt, call LLM, parse the schedule out of the response."""

from dataclasses import dataclass
import os
from typing import Optional

import numpy as np

from config.site import SiteConfig, TOUConfig
from data.format.schema import DaySessions
from baseline.prompt import build_prompt
from baseline.parse import ParseResult, parse_llm_schedule


@dataclass
class BaselineResult:
    schedule: np.ndarray
    parse_success: bool
    raw_response: Optional[str] = None
    parse_error: Optional[str] = None


def _default_schedule(day: DaySessions) -> np.ndarray:
    return np.zeros((len(day.sessions), day.n_steps), dtype=float)


def run_baseline(
    day: DaySessions,
    site: SiteConfig,
    tou: TOUConfig,
    api_key: Optional[str] = None,
    model: str = "gpt-4o",
    max_completion_tokens: int = 8192,
    instruction: Optional[str] = None,
    temperature: float = 0.0,
) -> BaselineResult:
    if tou.n_steps != day.n_steps:
        raise ValueError(
            f"TOUConfig.n_steps ({tou.n_steps}) != DaySessions.n_steps ({day.n_steps})"
        )
    if site.n_steps != day.n_steps:
        raise ValueError(
            f"SiteConfig.n_steps ({site.n_steps}) != DaySessions.n_steps ({day.n_steps})"
        )
    if day.dt_hours <= 0.0:
        raise ValueError(f"dt_hours must be positive, got {day.dt_hours}")

    if len(day.sessions) == 0 or day.n_steps == 0:
        return BaselineResult(
            schedule=_default_schedule(day),
            parse_success=True,
        )

    is_claude = model.startswith("claude-")

    if is_claude:
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            return BaselineResult(
                schedule=_default_schedule(day),
                parse_success=False,
                parse_error="ANTHROPIC_API_KEY not set",
            )
    else:
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            return BaselineResult(
                schedule=_default_schedule(day),
                parse_success=False,
                parse_error="OPENAI_API_KEY not set",
            )

    prompt_text = build_prompt(day, site, tou, instruction=instruction)

    system_prompt = (
        "You output ONLY the schedule: one line per session, each line "
        "'Session i: v0 v1 v2 ...' with exactly the number of space-separated "
        "floats specified in the prompt (one per time step). No commentary, "
        "no explanations. Follow the algorithm in the prompt. Ensure every "
        "line has the correct number of values; zeros outside each session's "
        "window, positive power inside until energy_kwh is delivered."
    )

    def _call_llm():
        # Claude uses the native Anthropic SDK; GPT uses OpenAI directly.
        # Claude at temperature>0 sometimes outputs chain-of-thought instead of
        # the schedule, so we retry up to 3 times when parsing fails.
        if is_claude:
            try:
                import anthropic as _anthropic  # type: ignore[import]
            except ImportError as exc:  # pragma: no cover
                return None, f"anthropic package not installed: {exc}"
            try:
                client = _anthropic.Anthropic(api_key=key)
                msg = client.messages.create(
                    model=model,
                    max_tokens=max_completion_tokens,
                    temperature=temperature,
                    system=system_prompt,
                    messages=[{"role": "user", "content": prompt_text}],
                )
                return (msg.content[0].text if msg.content else ""), None
            except Exception as exc:  # pragma: no cover
                return None, str(exc)
        else:
            try:
                from openai import OpenAI  # type: ignore[import]
            except ImportError as exc:  # pragma: no cover
                return None, f"openai package not installed: {exc}"
            try:
                client = OpenAI(api_key=key)
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt_text},
                    ],
                    max_tokens=max_completion_tokens,
                    temperature=temperature,
                )
                if not resp.choices:
                    return None, "API returned no choices"
                return resp.choices[0].message.content or "", None
            except Exception as exc:  # pragma: no cover
                return None, str(exc)

    max_attempts = 3
    last_response: Optional[str] = None
    last_error: Optional[str] = None

    for _ in range(max_attempts):
        response_text, call_error = _call_llm()
        if response_text is None:
            last_error = call_error
            continue

        last_response = response_text
        parse_result: ParseResult = parse_llm_schedule(response_text, day)
        if parse_result.success:
            return BaselineResult(
                schedule=parse_result.schedule,
                parse_success=True,
                raw_response=response_text,
            )
        last_error = parse_result.error_message

    if last_response is not None:
        parse_result = parse_llm_schedule(last_response, day)
        return BaselineResult(
            schedule=parse_result.schedule,
            parse_success=False,
            raw_response=last_response,
            parse_error=f"Parse failed after {max_attempts} attempts. Last error: {last_error}",
        )

    return BaselineResult(
        schedule=_default_schedule(day),
        parse_success=False,
        parse_error=f"All {max_attempts} LLM calls failed. Last error: {last_error}",
    )
