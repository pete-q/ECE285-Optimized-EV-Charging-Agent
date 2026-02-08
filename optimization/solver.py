"""CVXPY cost-minimization solver: decision variables p_i(t), objective, constraints."""

from dataclasses import dataclass
from typing import Optional

import numpy as np

from config.site import SiteConfig, TOUConfig
from data.format.schema import DaySessions


@dataclass
class SolveResult:
    """Result of optimization: schedule, cost, unmet, peak, and status."""

    schedule: np.ndarray  # (n_sessions, n_steps) in kW
    total_cost_usd: float
    unmet_energy_kwh: np.ndarray  # per session
    peak_load_kw: float
    success: bool
    message: Optional[str] = None


def solve(
    day: DaySessions,
    site: SiteConfig,
    tou: TOUConfig,
    penalty_unmet: float = 1e6,
) -> SolveResult:
    """Formulate and solve min sum_t c(t)*sum_i p_i(t)*dt + M*sum_i u_i; report peak.

    Args:
        day: Sessions and horizon (n_steps, dt_hours).
        site: P_max, n_steps, dt_hours.
        tou: rates_per_kwh for each step.
        penalty_unmet: M in objective ($/kWh penalty for slack u_i).

    Returns:
        SolveResult with schedule, cost, unmet, peak, and success flag.
    """
    ...
