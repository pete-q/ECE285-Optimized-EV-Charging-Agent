"""Plan: parse user request into objective, horizon, constraints, session params."""

from dataclasses import dataclass
from typing import Any, Optional

from config.site import SiteConfig, TOUConfig
from data.format.schema import DaySessions


@dataclass
class PlanResult:
    """Structured representation for the optimizer and checker."""

    day: DaySessions
    site: SiteConfig
    tou: TOUConfig
    objective: str  # e.g. "minimize_cost"
    raw: Optional[Any] = None


def plan(
    request: str,
    day: DaySessions,
    site: SiteConfig,
    tou: TOUConfig,
) -> PlanResult:
    """Parse request (e.g. 'minimize cost for this day') into PlanResult. Optional LLM step."""
    ...
