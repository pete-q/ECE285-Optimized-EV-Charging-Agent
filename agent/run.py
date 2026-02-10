"""Agent pipeline: Plan → Optimize → Validate → Refine (if needed) → Explain.

This module orchestrates the full agentic EV charging schedule workflow:
  1. Plan: Parse user request into structured inputs (v1: pass-through).
  2. Optimize: Call the CVXPY solver to compute an optimal schedule.
  3. Validate: Check the schedule against all constraints.
  4. Refine: On failure, optionally adjust inputs and re-solve (v1: no-op).
  5. Explain: Generate a grounded natural-language explanation of results.
"""

from dataclasses import dataclass

import numpy as np

from agent.explain.explain import ScheduleFacts, extract_facts, generate_explanation
from agent.optimize.call_solver import optimize
from agent.plan.plan import plan
from agent.refine.refine import refine
from agent.validate.validate import validate
from config.site import SiteConfig, TOUConfig
from data.format.schema import DaySessions
from evaluation.metrics import charge_asap_schedule, total_cost


@dataclass
class AgentResult:
    """Result of running the full agent pipeline.

    Attributes:
        schedule: Power schedule array of shape (n_sessions, n_steps) in kW.
        total_cost_usd: Total energy cost in USD.
        peak_load_kw: Maximum total power draw across all sessions (kW).
        unmet_energy_kwh: Total unmet energy across all sessions (kWh).
        feasible: True if the schedule satisfies all constraints.
        explanation: Human-readable summary of the schedule results.
    """

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
    max_retries: int = 1,
) -> AgentResult:
    """Run the full agent pipeline: Plan → Optimize → Validate → Refine → Explain.

    Args:
        day: DaySessions with sessions and horizon.
        site: SiteConfig with power cap.
        tou: TOUConfig with TOU rates.
        request: Natural-language request for the planner.
        max_retries: Maximum refinement attempts on solver failure (v1: unused).

    Returns:
        AgentResult with schedule, metrics, feasibility, and explanation.
    """
    # --- 1. Plan: parse request into structured inputs ---
    plan_result = plan(request, day, site, tou)
    day = plan_result.day
    site = plan_result.site
    tou = plan_result.tou

    # --- 2. Optimize: call the solver ---
    solve_result = optimize(day, site, tou)
    schedule = solve_result.schedule

    # --- 3. Validate: check constraints ---
    check_result = validate(schedule, day, site)

    # --- 4. Refine: if solver failed and retries available, try to fix (v1: no-op) ---
    if not solve_result.success and max_retries > 0:
        day, site, tou, solve_result = refine(day, site, tou, solve_result, max_retries)
        schedule = solve_result.schedule
        check_result = validate(schedule, day, site)

    # --- 5. Extract metrics ---
    total_cost_usd = solve_result.total_cost_usd
    peak_load_kw = solve_result.peak_load_kw
    unmet_energy_kwh = float(np.sum(solve_result.unmet_energy_kwh))
    feasible = check_result.feasible

    # --- 6. Compute uncontrolled baseline cost for comparison ---
    site_p_max = site.get_P_max_at_step(0) if day.n_steps > 0 else 50.0
    uncontrolled_schedule = charge_asap_schedule(day, float(site_p_max))
    uncontrolled_cost_usd = total_cost(uncontrolled_schedule, tou, day.dt_hours)

    # --- 7. Generate grounded explanation ---
    facts: ScheduleFacts = extract_facts(
        schedule,
        total_cost_usd,
        peak_load_kw,
        unmet_energy_kwh,
        uncontrolled_cost_usd=uncontrolled_cost_usd,
    )
    explanation = generate_explanation(facts)

    return AgentResult(
        schedule=schedule,
        total_cost_usd=total_cost_usd,
        peak_load_kw=peak_load_kw,
        unmet_energy_kwh=unmet_energy_kwh,
        feasible=feasible,
        explanation=explanation,
    )
