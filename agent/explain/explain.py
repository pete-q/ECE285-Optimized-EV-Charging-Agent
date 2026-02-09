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
    # cost_reduction_pct = None; if uncontrolled_cost_usd: cost_reduction_pct = 100*(uncontrolled - total_cost_usd)/uncontrolled
    # return ScheduleFacts(total_cost_usd, peak_load_kw, total_unmet_kwh, cost_reduction_vs_uncontrolled_pct=cost_reduction_pct)
    ...


def generate_explanation(facts: ScheduleFacts, use_llm: bool = False) -> str:
    """Generate short NL explanation using only facts (template or LLM)."""
    # template: "Total cost ${facts.total_cost_usd:.2f}. Peak {facts.peak_load_kw:.1f} kW. Unmet {facts.total_unmet_kwh:.1f} kWh."
    # if facts.cost_reduction_vs_uncontrolled_pct: add " Cost reduction vs uncontrolled: {pct:.1f}%."; return s
    ...
