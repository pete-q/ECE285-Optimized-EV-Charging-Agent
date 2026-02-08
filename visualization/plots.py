"""Schedule and load profile visualization for reports."""

from pathlib import Path
from typing import Optional

import numpy as np

from data.format.schema import DaySessions


def plot_schedule(
    schedule: np.ndarray,
    day: DaySessions,
    save_path: Optional[Path] = None,
) -> None:
    """Plot schedule matrix: sessions (rows) vs time (columns), color = power (kW).

    If save_path is set, save figure to file (e.g. PNG).
    """
    ...


def plot_load_profile(
    schedule: np.ndarray,
    day: DaySessions,
    save_path: Optional[Path] = None,
    title: Optional[str] = None,
) -> None:
    """Plot facility load sum_i p_i(t) vs time; optionally annotate with cost/unmet in title."""
    ...
