"""Script: load config and sessions, run baseline, optionally run checker and print metrics."""

# Usage:
#   python -m scripts.run_baseline
# or
#   python scripts/run_baseline.py
#
# Loads .env from project root so ACN_DATA_API_TOKEN is used.
# Build site + TOU config, run baseline, run constraint checker, print metrics.
# Optionally save schedule or pass --output experiments/baseline_out.json.

import sys
from pathlib import Path

# Load .env from project root so ACN_DATA_API_TOKEN (and LLM keys) are available
_project_root = Path(__file__).resolve().parent.parent
if _project_root not in sys.path:
    sys.path.insert(0, str(_project_root))
try:
    from dotenv import load_dotenv
    load_dotenv(_project_root / ".env")
except ImportError:
    pass


def main() -> None:
    # Pseudocode:
    #   site_id = "caltech"; day_date = today or fixed
    #   day = load_sessions(site_id, day_date); site = SiteConfig(P_max_kw=50, n_steps=day.n_steps, dt_hours=day.dt_hours)
    #   tou = TOUConfig(rates_per_kwh=default_tou_rates(day.n_steps))
    #   baseline_result = run_baseline(day, site, tou); schedule = baseline_result.schedule
    #   check_result = check(schedule, day, site); uncontrolled = charge_asap_schedule(day, site.P_max); uncontrolled_cost = total_cost(uncontrolled, tou, dt)
    #   metrics = compute_metrics(schedule, day, tou, dt, violation_count=len(check_result.violations), uncontrolled_cost_usd=uncontrolled_cost)
    #   print Feasible, Cost, Peak, Unmet, % cost reduction; optional: write metrics to experiments/
    ...


if __name__ == "__main__":
    main()
