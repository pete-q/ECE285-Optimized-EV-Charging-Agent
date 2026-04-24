"""Run the optimizer / agent / baseline benchmark N times and aggregate with mean ± std dev.

Each run processes the same set of 19–20 benchmark dates independently, writing its own
CSV and plots to a per-run subdirectory.  After all runs finish, results are aggregated
across runs (mean ± std dev) for paper-ready tables and bar charts.

Usage (from project root):
  python -m scripts.run_multi_run_benchmark
  python -m scripts.run_multi_run_benchmark --nruns 5 --ndays 20
  python -m scripts.run_multi_run_benchmark --nruns 3 --skip-baseline
  python -m scripts.run_multi_run_benchmark --nruns 3 --dates 2019-05-01 2019-05-08 2019-06-03

Requires:
  - ACN_DATA_API_TOKEN in .env
  - OPENAI_API_KEY in .env (for agent and baseline)

Output layout under --output-dir (default: benchmark_results/):
  run_1/
    agent_vs_baseline_metrics.csv    <- per-day rows, identical format to run_agent_vs_baseline
    per_day/*.png
  run_2/ ...
  run_N/ ...
  all_runs_metrics.csv               <- all rows from all runs, with run_id column prepended
  multi_run_average_table.md         <- mean ± std per pipeline per metric
  multi_run_average_bar.png          <- grouped bar chart with error bars
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import traceback
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

try:
    from dotenv import load_dotenv
    load_dotenv(_project_root / ".env")
except ImportError:
    pass

# Import shared constants and per-day runner functions from run_agent_vs_baseline.
from scripts.run_agent_vs_baseline import (
    BENCHMARK_DATES,
    P_MAX_KW,
    SITE_ID,
    _build_config,
    _build_nl_request,
    run_phase_agent,
    run_phase_baseline,
    run_phase_optimizer,
)
from data.loader.loader import load_sessions

# ---------------------------------------------------------------------------
# Per-run CSV helpers
# ---------------------------------------------------------------------------

_CSV_COLS = [
    "pipeline", "date", "n_sessions", "total_cost_usd", "peak_load_kw",
    "total_unmet_kwh", "pct_fully_served", "cost_reduction_pct",
    "violation_count", "feasible",
]

_ALL_RUNS_COLS = ["run_id"] + _CSV_COLS


def _write_csv(rows: List[Dict], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_COLS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in _CSV_COLS})


def _run_single(
    run_id: int,
    dates: List[date],
    out_dir: Path,
    *,
    skip_optimizer: bool,
    skip_agent: bool,
    skip_baseline: bool,
    temperature: float = 0.0,
) -> List[Dict]:
    """Execute one full benchmark run over *dates*. Returns list of per-day metric rows."""
    run_dir = out_dir / f"run_{run_id}"
    per_day_dir = run_dir / "per_day"
    run_dir.mkdir(parents=True, exist_ok=True)
    per_day_dir.mkdir(parents=True, exist_ok=True)

    all_rows: List[Dict] = []

    for i, day_date in enumerate(dates, 1):
        print(f"  [Run {run_id}] [{i}/{len(dates)}] {day_date}")

        try:
            day = load_sessions(site_id=SITE_ID, day_date=day_date)
        except Exception as exc:
            print(f"    Load error: {exc}")
            continue
        if len(day.sessions) == 0:
            print("    No sessions; skipping.")
            continue

        site, tou = _build_config(day.n_steps, day.dt_hours)
        nl_request = _build_nl_request(day, site_id=SITE_ID, cap_kw=P_MAX_KW)

        if not skip_optimizer:
            try:
                out = run_phase_optimizer(day_date, day, site, tou, per_day_dir)
                if out:
                    row, _ = out
                    all_rows.append(row)
                    print(f"    Optimizer: cost=${row['total_cost_usd']:.2f}  served={row['pct_fully_served']:.1f}%")
                else:
                    print("    Optimizer: solver failed")
            except Exception:
                print("    Optimizer: ERROR")
                traceback.print_exc()

        if not skip_agent:
            try:
                out = run_phase_agent(day_date, day, site, tou, nl_request, per_day_dir, temperature)
                if out:
                    row, _ = out
                    all_rows.append(row)
                    print(f"    Agent:     cost=${row['total_cost_usd']:.2f}  served={row['pct_fully_served']:.1f}%")
                else:
                    print("    Agent:     skipped (no API key)")
            except Exception:
                print("    Agent:     ERROR")
                traceback.print_exc()

        if not skip_baseline:
            try:
                out = run_phase_baseline(day_date, day, site, tou, nl_request, per_day_dir, temperature)
                if out:
                    row, _ = out
                    all_rows.append(row)
                    print(f"    Baseline:  cost=${row['total_cost_usd']:.2f}  served={row['pct_fully_served']:.1f}%")
                else:
                    print("    Baseline:  skipped (no API key)")
            except Exception:
                print("    Baseline:  ERROR")
                traceback.print_exc()

        print()

    csv_path = run_dir / "agent_vs_baseline_metrics.csv"
    _write_csv(all_rows, csv_path)
    print(f"  [Run {run_id}] Wrote {csv_path} ({len(all_rows)} rows)\n")
    return all_rows


# ---------------------------------------------------------------------------
# Cross-run aggregation
# ---------------------------------------------------------------------------

def _aligned_dates_for_rows(rows: List[Dict], pipelines: List[str]) -> Set[str]:
    """Return dates present in every pipeline in *rows* (aligned intersection)."""
    dates_by_p: Dict[str, Set[str]] = {}
    for r in rows:
        dates_by_p.setdefault(r["pipeline"], set()).add(str(r["date"]))
    if not pipelines:
        return set()
    common = set(dates_by_p.get(pipelines[0], set()))
    for p in pipelines[1:]:
        common &= dates_by_p.get(p, set())
    return common


def _per_pipeline_avg(rows: List[Dict], pipeline: str, keep_dates: Set[str]) -> Optional[Dict[str, float]]:
    """Average per-day metrics for one pipeline over *keep_dates*. Returns None if no rows."""
    pr = [r for r in rows if r["pipeline"] == pipeline and str(r["date"]) in keep_dates]
    if not pr:
        return None
    return {
        "avg_cost_usd":    float(np.mean([r["total_cost_usd"]    for r in pr])),
        "avg_peak_kw":     float(np.mean([r["peak_load_kw"]      for r in pr])),
        "avg_unmet_kwh":   float(np.mean([r["total_unmet_kwh"]   for r in pr])),
        "avg_served_pct":  float(np.mean([r["pct_fully_served"]  for r in pr])),
        "avg_violations":  float(np.mean([r["violation_count"]   for r in pr])),
        "n_days":          len({r["date"] for r in pr}),
    }


def _aggregate_runs(
    all_run_rows: List[Tuple[int, List[Dict]]],
    pipelines: List[str],
) -> List[Dict]:
    """Compute mean ± std dev across runs for each pipeline.

    Strategy: for each run, compute the within-run aligned average for each pipeline,
    then compute mean ± std dev of those run-level averages across runs.
    """
    # Metrics we track
    metric_keys = ["avg_cost_usd", "avg_peak_kw", "avg_unmet_kwh", "avg_served_pct", "avg_violations"]

    result_rows: List[Dict] = []
    for pipeline in pipelines:
        run_avgs: List[Dict[str, float]] = []
        days_per_run: List[int] = []

        for run_id, rows in all_run_rows:
            common_dates = _aligned_dates_for_rows(rows, pipelines)
            avg = _per_pipeline_avg(rows, pipeline, common_dates)
            if avg is not None:
                run_avgs.append(avg)
                days_per_run.append(int(avg["n_days"]))

        if not run_avgs:
            continue

        n_runs = len(run_avgs)
        row: Dict = {
            "pipeline": pipeline,
            "n_runs": n_runs,
            "avg_days_per_run": float(np.mean(days_per_run)) if days_per_run else 0.0,
        }
        for k in metric_keys:
            vals = [a[k] for a in run_avgs]
            row[f"mean_{k}"] = float(np.mean(vals))
            row[f"std_{k}"]  = float(np.std(vals, ddof=1)) if n_runs > 1 else 0.0

        result_rows.append(row)

    return result_rows


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def _write_all_runs_csv(
    all_run_rows: List[Tuple[int, List[Dict]]], path: Path
) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_ALL_RUNS_COLS, extrasaction="ignore")
        writer.writeheader()
        for run_id, rows in all_run_rows:
            for row in rows:
                writer.writerow({"run_id": run_id, **{k: row.get(k) for k in _CSV_COLS}})


def _fmt(mean: float, std: float) -> str:
    return f"{mean:.2f} ± {std:.2f}"


def _write_multi_run_table_md(agg_rows: List[Dict], path: Path) -> None:
    n_runs = agg_rows[0]["n_runs"] if agg_rows else 0
    avg_days = agg_rows[0]["avg_days_per_run"] if agg_rows else 0
    lines = [
        f"# Multi-Run Average Results ({n_runs} runs, ~{avg_days:.0f} days/run)",
        "",
        "Values are **mean ± sample std dev** across runs. "
        "Each run's figure is itself the aligned average over common dates within that run.",
        "",
        "| Pipeline | Runs | Days/Run | Cost ($) | Peak (kW) | Unmet (kWh) | Served (%) | Violations |",
        "|----------|------|----------|----------|-----------|-------------|------------|------------|",
    ]
    for r in agg_rows:
        lines.append(
            f"| {r['pipeline']:9} "
            f"| {int(r['n_runs']):4d} "
            f"| {r['avg_days_per_run']:8.1f} "
            f"| {_fmt(r['mean_avg_cost_usd'],   r['std_avg_cost_usd'])} "
            f"| {_fmt(r['mean_avg_peak_kw'],     r['std_avg_peak_kw'])} "
            f"| {_fmt(r['mean_avg_unmet_kwh'],   r['std_avg_unmet_kwh'])} "
            f"| {_fmt(r['mean_avg_served_pct'],  r['std_avg_served_pct'])} "
            f"| {_fmt(r['mean_avg_violations'],  r['std_avg_violations'])} |"
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def _plot_multi_run_bar(agg_rows: List[Dict], path: Path) -> None:
    import matplotlib.pyplot as plt

    pipelines = [r["pipeline"] for r in agg_rows]
    metrics = [
        ("mean_avg_cost_usd",   "std_avg_cost_usd",   "Cost ($)"),
        ("mean_avg_peak_kw",    "std_avg_peak_kw",    "Peak (kW)"),
        ("mean_avg_unmet_kwh",  "std_avg_unmet_kwh",  "Unmet (kWh)"),
        ("mean_avg_served_pct", "std_avg_served_pct", "Served (%)"),
    ]

    n_metrics = len(metrics)
    n_pipelines = len(pipelines)
    width = 0.8 / n_pipelines
    x = np.arange(n_metrics)

    fig, ax = plt.subplots(figsize=(11, 5))
    for i, pipeline in enumerate(pipelines):
        rec = next(r for r in agg_rows if r["pipeline"] == pipeline)
        means = [rec[mk] for mk, _, _ in metrics]
        stds  = [rec[sk] for _, sk, _ in metrics]
        offset = (i - n_pipelines / 2 + 0.5) * width
        bars = ax.bar(x + offset, means, width, label=pipeline.capitalize(), yerr=stds,
                      capsize=4, error_kw={"elinewidth": 1.2, "capthick": 1.2})

    ax.set_xticks(x)
    ax.set_xticklabels([label for _, _, label in metrics])
    ax.set_ylabel("Value")
    n_runs = agg_rows[0]["n_runs"] if agg_rows else 0
    ax.set_title(f"Multi-Run Average Results by Pipeline (N={n_runs} runs, error bars = ±1 std dev)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run optimizer / agent / baseline benchmark N times and aggregate "
            "with mean ± std dev across runs."
        )
    )
    parser.add_argument(
        "--nruns", type=int, default=3,
        help="Number of independent runs (default: 3)",
    )
    parser.add_argument(
        "--ndays", type=int, default=None,
        help="Use first N benchmark dates per run (default: all 20)",
    )
    parser.add_argument(
        "--dates", nargs="+", default=None,
        help="Override benchmark date list as YYYY-MM-DD",
    )
    parser.add_argument(
        "--output-dir", type=Path,
        default=_project_root / "benchmark_results",
        help="Root output directory (default: benchmark_results/)",
    )
    parser.add_argument("--skip-optimizer", action="store_true", help="Skip optimizer phase")
    parser.add_argument("--skip-baseline",  action="store_true", help="Skip LLM baseline")
    parser.add_argument("--skip-agent",     action="store_true", help="Skip agent pipeline")
    args = parser.parse_args()

    dates: List[date] = (
        [date.fromisoformat(d) for d in args.dates]
        if args.dates
        else list(BENCHMARK_DATES)
    )
    if args.ndays is not None:
        dates = dates[: args.ndays]

    out_dir = args.output_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if not os.environ.get("OPENAI_API_KEY", "").strip():
        print("WARNING: OPENAI_API_KEY not set — agent and baseline will be skipped.", file=sys.stderr)
    if not os.environ.get("ACN_DATA_API_TOKEN", "").strip():
        print("WARNING: ACN_DATA_API_TOKEN not set — session loading may fail.", file=sys.stderr)

    print(f"Output root : {out_dir}")
    print(f"Runs        : {args.nruns}")
    print(f"Dates/run   : {len(dates)} ({dates[0]} to {dates[-1]})")
    print()

    # ------------------------------------------------------------------ runs
    all_run_rows: List[Tuple[int, List[Dict]]] = []
    for run_id in range(1, args.nruns + 1):
        print(f"{'='*60}")
        print(f"RUN {run_id} / {args.nruns}")
        print(f"{'='*60}")
        rows = _run_single(
            run_id, dates, out_dir,
            skip_optimizer=args.skip_optimizer,
            skip_agent=args.skip_agent,
            skip_baseline=args.skip_baseline,
            temperature=0.0,
        )
        if rows:
            all_run_rows.append((run_id, rows))
        else:
            print(f"  [Run {run_id}] WARNING: no rows produced — skipping this run in aggregation.\n")

    if not all_run_rows:
        print("No results across any run. Check API keys and ACN_DATA_API_TOKEN.", file=sys.stderr)
        sys.exit(1)

    # -------------------------------------------------------- all_runs CSV
    all_csv_path = out_dir / "all_runs_metrics.csv"
    _write_all_runs_csv(all_run_rows, all_csv_path)
    total_rows = sum(len(r) for _, r in all_run_rows)
    print(f"Wrote {all_csv_path}  ({total_rows} rows across {len(all_run_rows)} runs)")

    # -------------------------------------------------------- aggregation
    # Determine which pipelines are present across runs.
    all_rows_flat = [r for _, rows in all_run_rows for r in rows]
    seen_pipelines = {r["pipeline"] for r in all_rows_flat}
    pipelines = [p for p in ["optimizer", "baseline", "agent"] if p in seen_pipelines]

    agg_rows = _aggregate_runs(all_run_rows, pipelines)

    if not agg_rows:
        print("No aggregated results. Nothing to write.", file=sys.stderr)
        sys.exit(1)

    # ------------------------------------------------------- table + bar
    table_path = out_dir / "multi_run_average_table.md"
    _write_multi_run_table_md(agg_rows, table_path)
    print(f"Wrote {table_path}")

    bar_path = out_dir / "multi_run_average_bar.png"
    _plot_multi_run_bar(agg_rows, bar_path)
    print(f"Wrote {bar_path}")

    # ---------------------------------------------------- console summary
    print("\n" + "="*60)
    print("MULTI-RUN SUMMARY")
    print("="*60)
    n_runs_used = agg_rows[0]["n_runs"]
    print(f"{'Pipeline':<12} {'Cost ($)':>20} {'Served (%)':>20} {'Unmet (kWh)':>22}")
    print("-" * 76)
    for r in agg_rows:
        print(
            f"{r['pipeline']:<12} "
            f"{_fmt(r['mean_avg_cost_usd'],  r['std_avg_cost_usd']):>20} "
            f"{_fmt(r['mean_avg_served_pct'], r['std_avg_served_pct']):>20} "
            f"{_fmt(r['mean_avg_unmet_kwh'],  r['std_avg_unmet_kwh']):>22}"
        )
    print(f"\n(N={n_runs_used} runs, mean ± sample std dev)")
    print("\nDone.")


if __name__ == "__main__":
    main()
