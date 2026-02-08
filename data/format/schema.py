"""Standardized session and day format for the EV charging pipeline.

Time is discrete: steps 0 .. n_steps-1. Each step has duration dt_hours.
Session availability is [arrival_idx, departure_idx) (inclusive start, exclusive end).
Power in kW, energy in kWh.
"""

from dataclasses import dataclass
from typing import List


# Default time resolution: 15-minute intervals
DEFAULT_DT_HOURS = 0.25
DEFAULT_STEPS_PER_HOUR = 4


@dataclass(frozen=True)
class Session:
    """One charging session (one EV visit).

    Attributes:
        session_id: Unique identifier (e.g. from ACN-Data sessionID).
        arrival_idx: First time step index when charging is allowed (inclusive).
        departure_idx: First time step index when charging is no longer allowed (exclusive).
        energy_kwh: Requested energy to deliver (kWh).
        charger_id: Assigned charger/station ID (e.g. spaceID).
        max_power_kw: Maximum charging power for this session (kW).
    """

    session_id: str
    arrival_idx: int
    departure_idx: int
    energy_kwh: float
    charger_id: str
    max_power_kw: float

    def __post_init__(self) -> None:
        """

        """
        if self.arrival_idx >= self.departure_idx:
            raise ValueError("Arrival index must be less than departure index")
        if self.energy_kwh <= 0:
            raise ValueError("Energy must be positive")
        if self.max_power_kw <= 0:
            raise ValueError("Maximum power must be positive")
        if self.arrival_idx < 0 or self.departure_idx < 0:
            raise ValueError("Indices must be non-negative")
        

@dataclass
class DaySessions:
    """Sessions for a single day with a fixed horizon.

    Attributes:
        sessions: List of Session in arbitrary order.
        n_steps: Number of time steps in the horizon (0 .. n_steps-1).
        dt_hours: Duration of each time step in hours.
    """

    sessions: List[Session]
    n_steps: int
    dt_hours: float = DEFAULT_DT_HOURS

    def __post_init__(self) -> None:
        """

        """
        if self.departure_idx > self.n_steps:
            raise ValueError("Departure index must be less than or equal to the number of steps")
