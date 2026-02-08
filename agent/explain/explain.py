"""Explain: extract schedule-derived facts; generate natural-language explanation grounded in them."""

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class ScheduleFacts:
    """Numeric facts from the schedule for grounding the explanation."""

    total_cost_usd: float
    peak_load_kw: float
    total_unmet_kwh: float
    cost_reduction_vs_uncontrolled_pct: Optional[float] = None


def extract_facts(
    schedule: np.ndarray,
    total_cost_usd: float,
    peak_load_kw: float,
    total_unmet_kwh: float,
    uncontrolled_cost_usd: Optional[float] = None,
) -> ScheduleFacts:
    """Build ScheduleFacts from computed metrics."""
    ...


def generate_explanation(facts: ScheduleFacts, use_llm: bool = False) -> str:
    """Generate short NL explanation using only facts (template or LLM)."""
    ...
