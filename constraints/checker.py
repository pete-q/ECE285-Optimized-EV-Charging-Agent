"""Constraint checker: feasibility of a schedule against sessions and site config."""

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from config.site import SiteConfig
from data.format.schema import DaySessions


@dataclass
class Violation:
    """Single constraint violation."""

    kind: str  # "availability" | "per_charger" | "site_cap" | "energy"
    session_id: Optional[str]
    time_step: Optional[int]
    message: str


@dataclass
class CheckResult:
    """Result of checking a schedule."""

    feasible: bool
    violations: List[Violation]
    unmet_energy_kwh: np.ndarray  # per session
    peak_load_kw: float


def check(
    schedule: np.ndarray,
    day: DaySessions,
    site: SiteConfig,
    dt_hours: Optional[float] = None,
) -> CheckResult:
    """Check schedule against availability, per-charger limits, site cap, and energy.

    Args:
        schedule: Shape (n_sessions, n_steps), power in kW. Order must match day.sessions.
        day: DaySessions with sessions and n_steps, dt_hours.
        site: SiteConfig with P_max and n_steps.
        dt_hours: Override for step duration; defaults to day.dt_hours.

    Returns:
        CheckResult with feasible, violations, per-session unmet energy, and peak load.
    """
    TOL = 1e-6
    dt = dt_hours if dt_hours is not None else day.dt_hours
    violations: List[Violation] = []
    n_steps = day.n_steps
    n_sessions = len(day.sessions)
    total_power = np.zeros(n_steps)
    unmet_energy_kwh = np.zeros(n_sessions)

    # One pass over (i, t): availability, per-charger, and accumulate total_power; then energy per session
    for i in range(n_sessions):
        s = day.sessions[i]
        delivered = 0.0
        for t in range(n_steps):
            p = schedule[i, t]
            total_power[t] += p
            delivered += p * dt

            if t < s.arrival_idx or t >= s.departure_idx:
                if abs(p) > TOL:
                    violations.append(
                        Violation(
                            kind="availability",
                            session_id=s.session_id,
                            time_step=t,
                            message="Charging outside connection window",
                        )
                    )
            if p < - TOL or p > s.max_power_kw + TOL:
                violations.append(
                    Violation(
                        kind="per_charger",
                        session_id=s.session_id,
                        time_step=t,
                        message="Power outside [0, max_power_kw]",
                    )
                )

        unmet_i = s.energy_kwh - delivered
        unmet_energy_kwh[i] = max(0.0, unmet_i)
        if unmet_i < -TOL:
            violations.append(
                Violation(
                    kind="energy",
                    session_id=s.session_id,
                    time_step=None,
                    message="Over-delivered energy",
                )
            )
        elif unmet_i > TOL:
            violations.append(
                Violation(
                    kind="energy",
                    session_id=s.session_id,
                    time_step=None,
                    message="Under-delivered energy",
                )
            )

    # Site capacity: one pass over t (total_power already computed above)
    for t in range(n_steps):
        p_max_t = site.get_P_max_at_step(t)
        if total_power[t] > p_max_t + TOL:
            violations.append(
                Violation(
                    kind="site_cap",
                    session_id=None,
                    time_step=t,
                    message="Total power exceeds site cap",
                )
            )

    # STEP 5 — Result
    peak_load_kw = float(total_power.max()) if n_steps > 0 else 0.0
    feasible = len(violations) == 0
    return CheckResult(
        feasible=feasible,
        violations=violations,
        unmet_energy_kwh=unmet_energy_kwh,
        peak_load_kw=peak_load_kw,
    )
