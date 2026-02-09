"""Validate: run constraint checker on schedule; return feasibility and metrics."""

from constraints.checker import check, CheckResult
from config.site import SiteConfig
from data.format.schema import DaySessions
import numpy as np


def validate(
    schedule: np.ndarray,
    day: DaySessions,
    site: SiteConfig,
) -> CheckResult:
    """Run constraint checker; return CheckResult (feasible, violations, unmet, peak)."""
    # return check(schedule, day, site)
    ...
