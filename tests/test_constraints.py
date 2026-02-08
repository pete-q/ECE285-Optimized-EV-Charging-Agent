"""Unit tests for constraint checker: feasible schedule, and one violation per constraint type."""

import numpy as np
import pytest

from config.site import SiteConfig
from constraints.checker import check, CheckResult, Violation
from data.format.schema import DaySessions, Session


def test_check_feasible_schedule() -> None:
    """One schedule that satisfies all constraints; assert result.feasible and no violations."""
    # BUILD: DaySessions with 1–2 sessions, n_steps (e.g. 8), dt_hours=0.25; each session has
    #        [arrival_idx, departure_idx), energy_kwh, max_power_kw. Build schedule (n_sessions, n_steps)
    #        with zeros outside [arrival, departure), and within [arrival, departure) power <= max_power_kw,
    #        and sum_t p_i(t)*dt == energy_kwh for each i. SiteConfig with P_max_kw >= max_t sum_i p_i(t).
    # CALL:  result = check(schedule, day, site)
    # ASSERT: result.feasible is True, len(result.violations) == 0, result.unmet_energy_kwh all >= 0
    pytest.skip("Implement: hand-build DaySessions + schedule + site, then assert result.feasible and no violations")


def test_check_availability_violation() -> None:
    """Schedule with non-zero power outside [arrival, departure); assert violation kind 'availability'."""
    # BUILD: DaySessions with one session, e.g. arrival_idx=2, departure_idx=6. Schedule with a non-zero
    #        value at t=0 or t>=6 (outside window). SiteConfig with any P_max.
    # CALL:  result = check(schedule, day, site)
    # ASSERT: result.feasible is False, at least one v in result.violations with v.kind == "availability"
    pytest.skip("Implement: schedule with power outside [arrival, departure), assert kind 'availability'")


def test_check_per_charger_violation() -> None:
    """Schedule with p_i(t) > max_power_kw or negative; assert violation kind 'per_charger'."""
    # BUILD: One session with max_power_kw = 7.0. Schedule has 8.0 or -0.1 at some t in [arrival, departure).
    # CALL:  result = check(schedule, day, site)
    # ASSERT: result.feasible is False, at least one violation with kind == "per_charger"
    pytest.skip("Implement: schedule with p_i(t) > max_power_kw or < 0, assert kind 'per_charger'")


def test_check_site_cap_violation() -> None:
    """Schedule where sum_i p_i(t) > P_max at some t; assert violation kind 'site_cap'."""
    # BUILD: Two sessions, both charging at max at same t; SiteConfig P_max_kw smaller than sum of their powers.
    # CALL:  result = check(schedule, day, site)
    # ASSERT: result.feasible is False, at least one violation with kind == "site_cap"
    pytest.skip("Implement: sum_i p_i(t) > P_max at some t, assert kind 'site_cap'")


def test_check_energy_violation() -> None:
    """Schedule that over-delivers or under-delivers (unmet); assert violation or unmet set correctly."""
    # BUILD: One session with energy_kwh = 10.0. Schedule delivers 0 (under) or way more than 10 (over).
    # CALL:  result = check(schedule, day, site)
    # ASSERT: result.feasible is False and (energy violation present and/or result.unmet_energy_kwh[i] > 0)
    pytest.skip("Implement: under- or over-deliver energy, assert energy violation or unmet_energy_kwh")
