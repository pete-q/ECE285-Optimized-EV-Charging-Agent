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
    """Run Plan → Optimize → Validate → Refine → Explain; return schedule, metrics, and explanation."""
    ...
