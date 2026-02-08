"""Load sessions from ACN-Data API or synthetic data; map to standardized format."""

from datetime import date
from typing import Any, Dict, List, Optional

from data.format.schema import DaySessions, Session


def synthetic_day_sessions(
    n_steps: int = 96,
    dt_hours: float = 0.25,
    n_sessions: int = 4,
) -> DaySessions:
    """Return a small, deterministic DaySessions for testing without the API.

    Args:
        n_steps: Number of time steps in the horizon.
        dt_hours: Duration of each step (hours). Must be consistent so n_steps/dt_hours is 24.
        n_sessions: Number of sessions to generate (e.g. 3–5).

    Returns:
        DaySessions with sessions, n_steps, dt_hours. Sessions have consistent n_steps/dt_hours.
    """
    # PSEUDOCODE:
    # 1. Ensure n_steps and dt_hours are consistent (e.g. n_steps * dt_hours == 24, or fix one from the other).
    # 2. Build a list of Session objects (deterministic): for each i in range(n_sessions),
    #    set session_id e.g. "syn_i", charger_id e.g. "space_1", energy_kwh and max_power_kw (fixed values),
    #    arrival_idx and departure_idx within [0, n_steps) with arrival_idx < departure_idx.
    # 3. return DaySessions(sessions=list, n_steps=n_steps, dt_hours=dt_hours)
    raise NotImplementedError("synthetic_day_sessions: build deterministic Session list and return DaySessions")


def raw_session_to_standard(raw: Dict[str, Any], t0_idx: int, dt_hours: float) -> Session:
    """Map one raw ACN-Data session dict to Session.

    ACN-Data keys: connectionTime, disconnectTime, kWhDelivered, sessionID, spaceID.
    Converts wall-clock times to step indices using t0_idx (step index for day start) and dt_hours.

    Args:
        raw: Dict with connectionTime, disconnectTime, kWhDelivered, sessionID, spaceID (and optionally
             fields for max power if available).
        t0_idx: Step index corresponding to the day start (e.g. 0 if day starts at midnight).
        dt_hours: Duration of one step in hours (e.g. 0.25).

    Returns:
        Session with arrival_idx, departure_idx, energy_kwh, session_id, charger_id, max_power_kw.
    """
    # PSEUDOCODE:
    # 1. Parse connectionTime, disconnectTime (e.g. ISO strings or timestamps) to a time value (e.g. hours from midnight).
    # 2. arrival_step = t0_idx + round((connection_time_hours - t0_hours) / dt_hours), clamp to [0, n_steps).
    # 3. departure_step = t0_idx + round((disconnect_time_hours - t0_hours) / dt_hours), clamp; ensure > arrival_step.
    # 4. energy_kwh = raw["kWhDelivered"] (or requested energy if API provides it).
    # 5. session_id = str(raw["sessionID"]), charger_id = str(raw["spaceID"]).
    # 6. max_power_kw = raw.get("maxPower") or default (e.g. 7.0) if not in API.
    # 7. return Session(session_id=..., arrival_idx=..., departure_idx=..., energy_kwh=..., charger_id=..., max_power_kw=...)
    raise NotImplementedError("raw_session_to_standard: map raw keys to Session with time -> step indices")


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
        api_token: ACN-Data API token; if None or empty, use synthetic data.
        n_steps: Number of time steps in the horizon.
        dt_hours: Duration of each step (hours).

    Returns:
        DaySessions with sessions and n_steps, dt_hours.
    """
    # PSEUDOCODE:
    # 1. IF api_token is None or empty string:
    #        return synthetic_day_sessions(n_steps=n_steps, dt_hours=dt_hours)
    # 2. ELSE:
    #        client = acnportal.acndata.DataClient(api_token)
    #        raw_sessions = client.get_sessions(site_id, day_date)  # or equivalent API call for site+date
    #        t0_idx = 0   # step index for start of day (e.g. midnight)
    #        sessions = [raw_session_to_standard(raw, t0_idx, dt_hours) for raw in raw_sessions]
    #        return DaySessions(sessions=sessions, n_steps=n_steps, dt_hours=dt_hours)
    raise NotImplementedError("load_sessions: if no token return synthetic; else fetch via DataClient and map")
