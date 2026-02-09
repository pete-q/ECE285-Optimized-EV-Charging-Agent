"""Parse LLM response text into schedule array (n_sessions x n_steps) in kW."""

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

from data.format.schema import DaySessions


@dataclass
class ParseResult:
    """Result of parsing LLM output."""

    schedule: np.ndarray  # (n_sessions, n_steps)
    success: bool
    error_message: Optional[str] = None


def parse_llm_schedule(
    response_text: str,
    day: DaySessions,
) -> ParseResult:
    """Convert model output string to schedule matrix.

    Expected format (as specified in baseline.prompt.build_prompt):
        - One line per session, in any order.
        - Each line starts with: 'Session i:' where i is the integer session_index.
        - After the colon, there are exactly n_steps floating-point numbers separated
          by spaces; the k-th number is p[i,k] in kW at time step k.

    This parser is deliberately simple and robust:
        - Ignores non-matching lines.
        - Tolerates extra whitespace.
        - Fails with a clear error message if:
            * No valid session lines are found.
            * A session appears more than once.
            * A line has the wrong number of numeric values.
    """
    n_sessions = len(day.sessions)
    n_steps = day.n_steps
    schedule = np.zeros((n_sessions, n_steps), dtype=float)

    # Empty day: trivial schedule, no need to parse
    if n_sessions == 0 or n_steps == 0:
        return ParseResult(schedule=schedule, success=True, error_message=None)

    used_rows: List[bool] = [False] * n_sessions
    lines = response_text.splitlines()

    def _parse_session_line(line: str) -> Optional[Tuple[int, List[float]]]:
        """Parse one 'Session i: v0 v1 ...' line. Return (i, values) or None."""
        stripped = line.strip()
        if not stripped.lower().startswith("session"):
            return None

        # Split at the first colon: "Session i:" / "Session i - " etc.
        if ":" in stripped:
            left, right = stripped.split(":", 1)
        else:
            # If there is no colon, we do not consider this a valid session line
            return None

        # Extract the session index i from the left part.
        # Expected pattern: "Session i" (case-insensitive), but be tolerant to spaces.
        tokens = left.strip().split()
        if len(tokens) < 2:
            return None
        try:
            session_idx = int(tokens[-1])
        except ValueError:
            return None

        # Parse the numeric values on the right side.
        value_strs = right.strip().split()
        if not value_strs:
            return None
        try:
            values = [float(v) for v in value_strs]
        except ValueError:
            # At least one token is not a float; treat this line as invalid
            return None

        return session_idx, values

    errors: List[str] = []
    for line in lines:
        parsed = _parse_session_line(line)
        if parsed is None:
            continue

        session_idx, values = parsed
        if session_idx < 0 or session_idx >= n_sessions:
            errors.append(f"Session index {session_idx} is out of range [0, {n_sessions - 1}].")
            continue

        if used_rows[session_idx]:
            errors.append(f"Duplicate schedule line for session {session_idx}.")
            continue

        if len(values) != n_steps:
            errors.append(
                f"Session {session_idx} has {len(values)} values, "
                f"but n_steps={n_steps} is required."
            )
            continue

        schedule[session_idx, :] = values
        used_rows[session_idx] = True

    def _fallback_matrix_parse(lines: List[str]) -> ParseResult:
        """Fallback parser: treat each numeric line as one session row.

        This is used when the model did not include the 'Session i:' prefix but
        still returned a numeric matrix. We take up to n_sessions lines that
        contain exactly n_steps floating-point values and map them to sessions
        in order (row 0 -> session 0, etc.).
        """

        row_idx = 0
        for line in lines:
            if row_idx >= n_sessions:
                break
            tokens = line.strip().split()
            if not tokens:
                continue
            # Try to parse the whole line as floats.
            try:
                values = [float(tok) for tok in tokens]
            except ValueError:
                continue

            if len(values) != n_steps:
                continue

            schedule[row_idx, :] = values
            row_idx += 1

        if row_idx == 0:
            return ParseResult(
                schedule=schedule,
                success=False,
                error_message=(
                    "Could not find any valid 'Session i:' lines or numeric "
                    "rows with the expected length in the model output."
                ),
            )

        # We successfully filled at least one row; treat this as a successful parse.
        return ParseResult(schedule=schedule, success=True, error_message=None)

    if not any(used_rows):
        # Try a more permissive numeric-matrix parse before giving up.
        return _fallback_matrix_parse(lines)

    if errors:
        # We still return the partially filled schedule, but mark parse as failed.
        return ParseResult(
            schedule=schedule,
            success=False,
            error_message="; ".join(errors),
        )

    return ParseResult(schedule=schedule, success=True, error_message=None)
