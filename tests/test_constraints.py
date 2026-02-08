"""Unit tests for constraint checker: feasible schedule, and one violation per constraint type."""

import numpy as np
import pytest

from config.site import SiteConfig
from constraints.checker import check, CheckResult, Violation
from data.format.schema import DaySessions, Session


def test_check_feasible_schedule() -> None:
    """One schedule that satisfies all constraints; assert result.feasible and no violations."""
    ...


def test_check_availability_violation() -> None:
    """Schedule with non-zero power outside [arrival, departure); assert violation kind 'availability'."""
    ...


def test_check_per_charger_violation() -> None:
    """Schedule with p_i(t) > max_power_kw or negative; assert violation kind 'per_charger'."""
    ...


def test_check_site_cap_violation() -> None:
    """Schedule where sum_i p_i(t) > P_max at some t; assert violation kind 'site_cap'."""
    ...


def test_check_energy_violation() -> None:
    """Schedule that over-delivers or under-delivers (unmet); assert violation or unmet set correctly."""
    ...
