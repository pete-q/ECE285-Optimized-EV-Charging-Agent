"""Agent integration: load sessions, run agent pipeline, check, compute metrics, plot.

Requires ACN_DATA_API_TOKEN in .env. Uses the same site and TOU config as Phase A
and run_baseline for fair comparisons.

Usage (from project root):
  python -m scripts.run_agent [--site SITE] [--date YYYY-MM-DD]
  python scripts/run_agent.py

Writes schedule and load profile to experiments/ if the directory exists.
"""

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if _project_root not in sys.path:
    sys.path.insert(0, str(_project_root))

try:
    from dotenv import load_dotenv
    load_dotenv(_project_root / ".env")
except ImportError:
    pass


def main() -> None:
    # --- 1. Parse CLI: site and date (default yesterday) ---
    parser = argparse.ArgumentParser(
        description="Agent: load from API, run agent pipeline, check, metrics, plot"
    )
    parser.add_argument("--site", default="caltech", help="ACN site (caltech, jpl, office001)")
    parser.add_argument("--date", default=None, help="Date YYYY-MM-DD (default: yesterday)")
    parser.add_argument(
        "--request",
        default="Minimize energy cost for this day.",
        help="Natural-language request for the agent planner.",
    )
    args = parser.parse_args()

    from agent.run import run_agent
    from config.site import SiteConfig, TOUConfig, default_tou_rates
    from constraints.checker import DEFAULT_TOL, check
    from data.loader.loader import load_sessions
    from evaluation.metrics import (
        charge_asap_schedule,
        compute_metrics,
        total_cost,
    )
    from visualization.plots import plot_load_profile, plot_schedule

    day_date = date.today() - timedelta(days=1) if args.date is None else date.fromisoformat(args.date)

    # --- 2. Load sessions from ACN-Data API (requires ACN_DATA_API_TOKEN in .env) ---
    try:
        day = load_sessions(site_id=args.site, day_date=day_date)
    except ValueError as e:
        print("Error:", e, file=sys.stderr)
        print("Set ACN_DATA_API_TOKEN in .env or pass it in the environment.", file=sys.stderr)
        sys.exit(1)
    except ImportError as e:
        print("Error:", e, file=sys.stderr)
        print("Install acnportal: pip install -e ./acnportal", file=sys.stderr)
        sys.exit(1)

    # --- 3. Require at least one session; exit with clear message if API returned none ---
    if len(day.sessions) == 0:
        print(
            f"No sessions returned for site={args.site} on date={day_date}.",
            file=sys.stderr,
        )
        print(
            "Try another --date (e.g. a date when the site had charging activity).",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Loaded {len(day.sessions)} sessions for {args.site} on {day_date}")

    # --- 4. Build site config (power cap 50 kW) and TOU rates (peak/off-peak) ---
    # Same config as Phase A and run_baseline for fair comparison
    site = SiteConfig(P_max_kw=50.0, n_steps=day.n_steps, dt_hours=day.dt_hours)
    tou = TOUConfig(rates_per_kwh=default_tou_rates(day.n_steps))

    # --- 5. Run agent pipeline: plan → optimize → validate → refine → explain ---
    result = run_agent(day, site, tou, request=args.request)

    # --- 6. Validate schedule with constraint checker (independent verification) ---
    check_result = check(result.schedule, day, site)

    # --- 7. Compute full metrics including comparison to uncontrolled baseline ---
    site_p_max = site.get_P_max_at_step(0) if day.n_steps > 0 else 50.0
    uncontrolled = charge_asap_schedule(day, float(site_p_max))
    uncontrolled_cost = total_cost(uncontrolled, tou, day.dt_hours)
    metrics = compute_metrics(
        result.schedule,
        day,
        tou,
        day.dt_hours,
        violation_count=len(check_result.violations),
        uncontrolled_cost_usd=uncontrolled_cost,
    )

    # --- 8. Print results: explanation, feasibility, violations (if any), metrics ---
    print()
    print("=== Agent results ===")
    print()
    print("Explanation:", result.explanation)
    print()
    print("Feasible:", result.feasible)
    if not check_result.feasible and check_result.violations:
        print(f"Violations ({len(check_result.violations)}):")
        for v in check_result.violations[:10]:
            sid = v.session_id or "(site)"
            ts = v.time_step if v.time_step is not None else "-"
            print(f"  [{v.kind}] session={sid} t={ts}  {v.message}")
        if len(check_result.violations) > 10:
            print(f"  ... and {len(check_result.violations) - 10} more violations")
        print(f"  (Checker tol={DEFAULT_TOL}; solver uses CVXPY defaults.)")
    print("Total cost ($):", round(metrics.total_cost_usd, 2))
    print("Peak load (kW):", round(metrics.peak_load_kw, 2))
    print("Total unmet (kWh):", round(metrics.total_unmet_kwh, 2))
    print("% fully served:", round(metrics.pct_fully_served, 1))
    if metrics.cost_reduction_vs_uncontrolled_pct is not None:
        print("% cost reduction vs uncontrolled:", round(metrics.cost_reduction_vs_uncontrolled_pct, 1))

    # --- 9. Save schedule heatmap and load profile to experiments/ if directory exists ---
    out_dir = _project_root / "experiments"
    if out_dir.exists():
        plot_schedule(result.schedule, day, save_path=out_dir / "agent_schedule.png")
        plot_load_profile(result.schedule, day, save_path=out_dir / "agent_load.png")
        print("Plots saved to experiments/")


if __name__ == "__main__":
    main()
