"""Build the LLM prompt: objective, constraints, session table."""

from typing import Optional, Sequence

from config.site import SiteConfig, TOUConfig
from data.format.schema import DaySessions


def _format_rates_summary(tou: TOUConfig) -> str:
    """Return a short textual summary of TOU rates.

    We do not rely on the model to reconstruct the exact per-step vector,
    but giving min/mean/max helps it understand that energy is more expensive
    in some parts of the day.
    """
    import numpy as np

    rates = np.asarray(tou.rates_per_kwh).flatten()
    if rates.size == 0:
        return "The energy price is constant over the day."

    min_rate = float(np.min(rates))
    max_rate = float(np.max(rates))
    mean_rate = float(np.mean(rates))
    if abs(max_rate - min_rate) < 1e-9:
        return f"The energy price is constant at ${min_rate:.3f} per kWh for all time steps."
    return (
        "Energy prices vary over the day. "
        f"The minimum price is ${min_rate:.3f} per kWh, "
        f"the maximum price is ${max_rate:.3f} per kWh, "
        f"and the average price is ${mean_rate:.3f} per kWh."
    )


def _format_site_cap(site: SiteConfig) -> str:
    """Return a human-readable description of the site power cap."""
    import numpy as np

    if np.isscalar(site.P_max_kw):
        return f"The site power cap is {float(site.P_max_kw):.1f} kW at all time steps."

    caps = np.asarray(site.P_max_kw).flatten()
    if caps.size == 0:
        return "There is effectively no site power cap specified."

    min_cap = float(np.min(caps))
    max_cap = float(np.max(caps))
    if abs(max_cap - min_cap) < 1e-9:
        return f"The site power cap is {min_cap:.1f} kW at all time steps."
    return (
        "The site power cap can vary over time. "
        f"It is between {min_cap:.1f} kW and {max_cap:.1f} kW across the horizon."
    )


def _format_table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    """Render a simple pipe-delimited table that is easy to parse."""
    # Header line
    header_line = " | ".join(headers)
    # Separator line using dashes so the model sees a clear table structure
    separator_line = " | ".join("---" for _ in headers)

    def _format_row(row: Sequence[object]) -> str:
        return " | ".join(str(value) for value in row)

    body_lines = [_format_row(row) for row in rows]
    return "\n".join([header_line, separator_line, *body_lines])


def build_prompt(
    day: DaySessions,
    site: SiteConfig,
    tou: TOUConfig,
    instruction: Optional[str] = None,
) -> str:
    """Assemble the baseline LLM prompt.

    The prompt has three main parts:
      1. Problem description: objective, time discretization, site power cap, and TOU summary.
      2. Session table: one row per charging session, in the same order as `day.sessions`.
      3. Output specification: what schedule to produce and in what format.

    The schedule that the model returns must have:
      - Shape: (number of sessions) x (number of time steps).
      - Units: power in kW.
      - Order: same session order as the table below, and time steps t = 0..n_steps-1.
    """
    lines: list[str] = []

    n_sessions = len(day.sessions)
    n_steps = day.n_steps
    dt_hours = day.dt_hours

    # --- 1. Problem description ---
    lines.append("You are scheduling electric vehicle charging for one site over one day.")
    lines.append(
        "Your primary objective is to meet the energy_kwh demand of each session as well "
        "as possible while still optimizing for low total energy cost under the TOU tariff."
    )
    lines.append(
        "In other words, you should do your best to deliver the requested energy_kwh for "
        "each session, subject to all constraints, and among all such schedules you "
        "should prefer those with lower total cost."
    )
    lines.append("")
    lines.append("Time discretization:")
    lines.append(
        f"- The day is divided into {n_steps} discrete time steps, "
        f"each of duration {dt_hours:.3f} hours."
    )
    lines.append("- Time step t = 0 corresponds to midnight (start of the day).")
    lines.append("- Time steps are indexed t = 0, 1, ..., n_steps-1.")
    lines.append("")
    lines.append("Site power cap:")
    lines.append(f"- { _format_site_cap(site) }")
    lines.append("")
    lines.append("Energy prices:")
    lines.append(f"- {_format_rates_summary(tou)}")
    lines.append("")

    # --- 2. Session table ---
    lines.append(
        "Each row in the following table describes one charging session. "
        "You must keep the sessions in exactly this order when you output the schedule."
    )
    lines.append(
        "The arrival and departure indices use the same time steps described above, "
        "and charging is only allowed for time steps t where "
        "arrival_idx <= t < departure_idx."
    )
    lines.append("")

    headers = [
        "session_index",
        "session_id",
        "arrival_idx",
        "departure_idx",
        "energy_kwh",
        "charger_id",
        "max_power_kw",
    ]
    rows: list[list[object]] = []
    for index, sess in enumerate(day.sessions):
        rows.append(
            [
                index,
                sess.session_id,
                sess.arrival_idx,
                sess.departure_idx,
                f"{sess.energy_kwh:.3f}",
                sess.charger_id,
                f"{sess.max_power_kw:.3f}",
            ]
        )

    lines.append(_format_table(headers, rows))
    lines.append("")

    # --- 3. Output specification ---
    lines.append("You must output a charging schedule that satisfies the following:")
    lines.append(
        "- The schedule is a matrix of real numbers p[i,t] in kW, "
        "where i is the session_index from the table above and "
        "t is the time step index from 0 to n_steps-1."
    )
    lines.append(
        "- For each session i, p[i,t] must be 0 for all t outside the interval "
        "[arrival_idx_i, departure_idx_i)."
    )
    lines.append(
        "- For each session i and each allowed time step t, "
        "0 <= p[i,t] <= max_power_kw_i."
    )
    lines.append(
        "- At every time step t, the total site power "
        "sum over all sessions of p[i,t] must not exceed the site power cap."
    )
    lines.append(
        "- For each session i, the total energy delivered "
        "sum_t p[i,t] * dt_hours should be as close as possible to energy_kwh_i."
    )
    lines.append(
        "- Schedules that leave most or all sessions with unmet energy "
        "(for example, p[i,t] = 0 for all i,t) are NOT acceptable solutions."
    )
    lines.append("")
    lines.append("Output format (very important):")
    lines.append(
        "- Print one line per session in the same order as the table above."
    )
    lines.append(
        "- Each line must start with the literal text 'Session i:' where i is the session_index,"
    )
    lines.append(
        "  followed by exactly n_steps floating-point numbers separated by spaces."
    )
    lines.append(
        "- The k-th number on that line is the power p[i,k] in kW for time step k."
    )
    lines.append("")
    lines.append("Example (for illustration only, not matching the real data):")
    lines.append("Session 0: 0.0 7.0 7.0 7.0 0.0 0.0")
    lines.append("Session 1: 0.0 0.0 3.5 3.5 3.5 0.0")
    lines.append("")
    lines.append(
        "Now produce the schedule following the exact output format described above."
    )

    if instruction:
        lines.append("")
        lines.append("Additional instruction from the user:")
        lines.append(instruction)

    return "\n".join(lines)
