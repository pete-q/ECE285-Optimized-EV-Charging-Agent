"""Evaluation metrics: cost, unmet energy, peak load, violations, % fully served."""

from dataclasses import dataclass
from typing import Optional

import numpy as np

from config.site import TOUConfig
from data.format.schema import DaySessions


@dataclass
class Metrics:
    """Aggregate metrics for one schedule."""

    total_cost_usd: float
    total_unmet_kwh: float
    peak_load_kw: float
    violation_count: int
    pct_fully_served: float  # 0–100
    cost_reduction_vs_uncontrolled_pct: Optional[float] = None


def total_cost(
    schedule: np.ndarray,
    tou: TOUConfig,
    dt_hours: float,
) -> float:
    """Total energy cost ($): sum_t c(t) * sum_i p_i(t) * dt."""
    ...


def total_unmet_kwh(schedule: np.ndarray, day: DaySessions, dt_hours: float) -> float:
    """Sum over sessions of (E_i - delivered_i)."""
    ...


def peak_load_kw(schedule: np.ndarray) -> float:
    """max_t sum_i p_i(t)."""
    ...


def pct_fully_served(schedule: np.ndarray, day: DaySessions, dt_hours: float) -> float:
    """Percentage of sessions with zero unmet energy (0–100)."""
    ...


def charge_asap_schedule(day: DaySessions, site_p_max: float) -> np.ndarray:
    """Uncontrolled baseline: each session charges at max rate from arrival until E_i met."""
    ...


def compute_metrics(
    schedule: np.ndarray,
    day: DaySessions,
    tou: TOUConfig,
    dt_hours: float,
    violation_count: int = 0,
    uncontrolled_cost_usd: Optional[float] = None,
) -> Metrics:
    """Compute all metrics; set cost_reduction_vs_uncontrolled_pct if uncontrolled_cost_usd given."""
    ...
