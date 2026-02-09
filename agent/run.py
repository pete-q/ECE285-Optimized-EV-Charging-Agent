"""Agent pipeline: Plan → Optimize → Validate → Refine (if needed) → Explain."""

from dataclasses import dataclass
from typing import Optional

import numpy as np

from config.site import SiteConfig, TOUConfig
from data.format.schema import DaySessions


@dataclass
class AgentResult:
    """Result of running the full agent pipeline."""

    schedule: np.ndarray
    total_cost_usd: float
    peak_load_kw: float
    unmet_energy_kwh: float
    feasible: bool
    explanation: str


def run_agent(
    day: DaySessions,
    site: SiteConfig,
    tou: TOUConfig,
    request: str = "Minimize energy cost for this day.",
) -> AgentResult:
    """Run Plan → Optimize → Validate → Refine → Explain; return schedule, metrics, and explanation.

    Pseudocode:
        # plan_result = plan(request, day, site, tou); day, site, tou = plan_result.day, .site, .tou
        # solve_result = optimize(day, site, tou); schedule = solve_result.schedule; check_result = validate(schedule, day, site)
        # if not check_result.feasible and max_retries: day, site, tou, solve_result = refine(...); re-validate
        # total_cost_usd = solve_result.total_cost_usd; peak = solve_result.peak_load_kw; unmet = sum(solve_result.unmet_energy_kwh)
        # uncontrolled_cost = total_cost(charge_asap_schedule(...), tou, dt); facts = extract_facts(..., uncontrolled_cost)
        # explanation = generate_explanation(facts); return AgentResult(schedule, total_cost_usd, peak, unmet, feasible, explanation)
    """
    ...
