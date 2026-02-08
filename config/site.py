"""Site and experiment configuration: power cap, time step, TOU rates."""

from dataclasses import dataclass
from typing import Union

import numpy as np


@dataclass
class SiteConfig:
    """Site-level constraints for one day.

    Attributes:
        P_max_kw: Site power cap (kW). Either a scalar (constant) or array of length n_steps.
        n_steps: Number of time steps in the horizon.
        dt_hours: Duration of each time step (hours).
    """

    P_max_kw: Union[float, np.ndarray]
    n_steps: int
    dt_hours: float = 0.25

    def get_P_max_at_step(self, t: int) -> float:
        """Return site power cap at time step t (kW)."""
        ...


@dataclass
class TOUConfig:
    """Time-of-use energy rates ($/kWh) per time step.

    Attributes:
        rates_per_kwh: Array of length n_steps; cost in $/kWh for each step.
    """

    rates_per_kwh: np.ndarray

    @property
    def n_steps(self) -> int:
        ...


def default_tou_rates(
    n_steps: int,
    peak_price: float = 0.45,
    off_peak_price: float = 0.12,
) -> np.ndarray:
    """Return TOU rate vector of length n_steps ($/kWh). Define peak/off-peak windows as needed."""
    ...
