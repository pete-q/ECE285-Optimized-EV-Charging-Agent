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
    """Convert model output string to schedule matrix. Handle failures (return success=False, error_message).

    Pseudocode:
        # n_sessions, n_steps = len(day.sessions), day.n_steps; schedule = zeros(n_sessions, n_steps)
        # try: parse text (split newline/comma, convert to float); fill schedule row by row
        # return ParseResult(schedule, success=True) except: return ParseResult(zeros, success=False, error_message=str(e))
    """
    ...
