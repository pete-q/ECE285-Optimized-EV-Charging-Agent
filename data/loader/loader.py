"""Load sessions from ACN-Data API or synthetic data; map to standardized format."""

from datetime import date
from typing import Any, Dict, List, Optional

from data.format.schema import DaySessions, Session


def load_sessions(
    site_id: str,
    day_date: date,
    api_token: Optional[str] = None,
    n_steps: int = 96,
    dt_hours: float = 0.25,
) -> DaySessions:
    """Load sessions for the given site and date. Map to DaySessions.

    If api_token is None or empty, return synthetic sessions for testing.
    Otherwise use acnportal.acndata.DataClient to fetch and map raw sessions.

    Args:
        site_id: ACN site (e.g. 'caltech', 'jpl', 'office001').
        day_date: Date for the horizon.
        api_token: ACN-Data API token; if None, use synthetic data.
        n_steps: Number of time steps in the horizon.
        dt_hours: Duration of each step (hours).

    Returns:
        DaySessions with sessions and n_steps, dt_hours.
    """
    ...


def raw_session_to_standard(raw: Dict[str, Any], t0_idx: int, dt_hours: float) -> Session:
    """Map one raw ACN-Data session dict to Session.

    Use connectionTime, disconnectTime, kWhDelivered, sessionID, spaceID, etc.
    Convert times to step indices; set max_power_kw from data or default.
    """
    ...


def synthetic_day_sessions(n_sessions: int = 5, n_steps: int = 96, dt_hours: float = 0.25) -> DaySessions:
    """Return a small synthetic DaySessions for testing without the API."""
    ...
