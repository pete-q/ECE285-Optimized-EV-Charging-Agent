"""Optimize: call optimization solver; return schedule, cost, peak, unmet."""

from optimization.solver import solve, SolveResult
from config.site import SiteConfig, TOUConfig
from data.format.schema import DaySessions


def optimize(day: DaySessions, site: SiteConfig, tou: TOUConfig, penalty_unmet: float = 1e6) -> SolveResult:
    """Call optimization.solver.solve and return SolveResult."""
    ...
