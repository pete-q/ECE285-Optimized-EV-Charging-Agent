"""Tests using synthetic DaySessions: loader, solver, metrics, etc.

Optional fixture provides a single DaySessions without hitting the API.
"""

import numpy as np
import pytest

from data.loader.loader import synthetic_day_sessions
from data.format.schema import DaySessions, Session


@pytest.fixture
def sample_day_sessions() -> DaySessions:
    """Return one DaySessions instance for tests that need data without the API.

    Hand-built minimal day: 2 sessions, 8 steps, 0.25 h step. Replace with
    synthetic_day_sessions(n_steps=96, dt_hours=0.25, n_sessions=4) once implemented.
    """
    sessions = [
        Session("s1", arrival_idx=0, departure_idx=4, energy_kwh=10.0, charger_id="c1", max_power_kw=7.0),
        Session("s2", arrival_idx=2, departure_idx=6, energy_kwh=5.0, charger_id="c2", max_power_kw=7.0),
    ]
    return DaySessions(sessions=sessions, n_steps=8, dt_hours=0.25)


def test_synthetic_day_sessions_shape() -> None:
    """synthetic_day_sessions returns DaySessions with correct n_steps and len(sessions)."""
    # PSEUDOCODE:
    # day = synthetic_day_sessions(n_steps=96, dt_hours=0.25, n_sessions=4)
    # assert day.n_steps == 96, day.dt_hours == 0.25, len(day.sessions) in [3, 4, 5]
    # assert day.n_steps * day.dt_hours == 24  # optional: consistency check
    pytest.skip("Implement: call synthetic_day_sessions, assert n_steps, dt_hours, len(sessions)")


def test_synthetic_sessions_have_valid_windows() -> None:
    """Each session has arrival_idx < departure_idx and within [0, n_steps)."""
    # PSEUDOCODE:
    # day = synthetic_day_sessions(...)  # or use fixture sample_day_sessions
    # for s in day.sessions: assert 0 <= s.arrival_idx < s.departure_idx <= day.n_steps
    pytest.skip("Implement: assert each session window in [0, n_steps) and arrival < departure")
