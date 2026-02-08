"""Build the LLM prompt: objective, constraints, session table."""

from typing import Optional

from config.site import SiteConfig, TOUConfig
from data.format.schema import DaySessions


def build_prompt(
    day: DaySessions,
    site: SiteConfig,
    tou: TOUConfig,
    instruction: Optional[str] = None,
) -> str:
    """Assemble prompt string: minimize TOU cost, horizon, site cap, session list (arrival, departure, E_i, charger, max power).

    Use a clear structure (e.g. table or bullets) so the model can output a parseable schedule.
    instruction: Optional extra instruction (e.g. output format).
    """
    ...
