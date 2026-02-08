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
    ...
