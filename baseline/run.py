"""Single entry point: load env, get sessions, build prompt, call LLM, parse schedule."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from config.site import SiteConfig, TOUConfig
from data.format.schema import DaySessions


@dataclass
class BaselineResult:
    """Result of running the baseline."""

    schedule: np.ndarray
    parse_success: bool
    raw_response: Optional[str] = None
    parse_error: Optional[str] = None


def run_baseline(
    day: DaySessions,
    site: SiteConfig,
    tou: TOUConfig,
    api_key: Optional[str] = None,
    model: str = "gpt-4o-mini",
) -> BaselineResult:
    """Run baseline: build prompt, call OpenAI (or other provider), parse response to schedule.

    Load OPENAI_API_KEY from api_key arg or from environment (e.g. via dotenv).
    If api_key is missing, return a zero schedule and parse_success=False with parse_error message.

    Pseudocode:
        # key = api_key or os.environ.get("OPENAI_API_KEY")
        # if not key: return BaselineResult(zeros, parse_success=False, parse_error="OPENAI_API_KEY not set")
        # prompt_text = build_prompt(day, site, tou); response = openai.chat.completions.create(...); response_text = content
        # parse_result = parse_llm_schedule(response_text, day)
        # return BaselineResult(schedule=parse_result.schedule, parse_success=parse_result.success, raw_response=..., parse_error=...)
    """
    ...
