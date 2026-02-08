"""Tests using synthetic DaySessions: loader, solver, metrics, etc."""

import numpy as np
import pytest

from data.loader.loader import synthetic_day_sessions
from data.format.schema import DaySessions


def test_synthetic_day_sessions_shape() -> None:
    """synthetic_day_sessions returns DaySessions with correct n_steps and len(sessions)."""
    ...


def test_synthetic_sessions_have_valid_windows() -> None:
    """Each session has arrival_idx < departure_idx and within [0, n_steps)."""
    ...
