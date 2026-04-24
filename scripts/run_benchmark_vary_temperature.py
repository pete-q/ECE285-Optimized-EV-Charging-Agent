"""Benchmark with temperature variation: same dates across N runs, non-zero LLM temperature.

Runs the full optimizer / agent / baseline pipeline over the same fixed set of benchmark
dates N times (default 5). Each run uses the specified LLM temperature so the agent and
baseline produce genuinely different outputs per run, making mean ± std dev meaningful.

The optimizer is deterministic and produces identical results every run (temperature has
no effect on it), so its std dev will be ~0. Only agent and baseline vary.

Usage (from project root):
  python -m scripts.run_benchmark_vary_temperature
  python -m scripts.run_benchmark_vary_temperature --nruns 5 --temperature 0.7
  python -m scripts.run_benchmark_vary_temperature --nruns 3 --temperature 1.0 --ndays 10
  python -m scripts.run_benchmark_vary_temperature --skip-baseline

Requires:
  - ACN_DATA_API_TOKEN in .env
  - OPENAI_API_KEY in .env

Output layout under --output-dir (default: benchmark_results/vary_temperature/):
  run_1/
    agent_vs_baseline_metrics.csv
    per_day/*.png
  run_2/ ...
  run_N/ ...
  all_runs_metrics.csv               <- all rows, run_id column prepended
  multi_run_average_table.md         <- mean ± std dev per pipeline per metric
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
# CSV helpers
# ---------------------------------------------------------------------------

_CSV_COLS = [
    "pipeline", "date", "n_sessions", "total_cost_usd", "peak_load_kw",
    "total_unmet_kwh", "pct_fully_served", "cost_reduction_pct",
    "violation_count", "feasible",
]
_ALL_RUNS_COLS = ["run_id"] + _CSV_COLS


def _write_run_csv(rows: List[Dict], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_COLS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in _CSV_COLS})


def _write_all_runs_csv(all_run_rows: List[Tuple[int, List[Dict]]], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_ALL_RUNS_COLS, extrasaction="ignore")
        writer.writeheader()
        for run_id, rows in all_run_rows:
            for row in rows:
                writer.writerow({"run_id": run_id, **{k: row.get(k) for k in _CSV_COLS}})


# ---------------------------------------------------------------------------
# Per-run execution
# ---------------------------------------------------------------------------

def _run_single(
    run_id: int,
    dates: List[date],
    out_dir: Path,
    temperature: float,
    *,
    skip_optimizer: bool,
    skip_agent: bool,
    skip_baseline: bool,
) -> List[Dict]:
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
        if not day.sessions:
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
                print("    Optimizer: ERROR"); traceback.print_exc()

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
                print("    Agent:     ERROR"); traceback.print_exc()

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
                print("    Baseline:  ERROR"); traceback.print_exc()
        print()

    _write_run_csv(all_rows, run_dir / "agent_vs_baseline_metrics.csv")
    print(f"  [Run {run_id}] Wrote {run_dir / 'agent_vs_baseline_metrics.csv'} ({len(all_rows)} rows)\n")
    return all_rows


# ---------------------------------------------------------------------------
# Cross-run aggregation (mean ± std dev over run-level aligned averages)
# ---------------------------------------------------------------------------

def _aligned_dates(rows: List[Dict], pipelines: List[str]) -> Set[str]:
    dates_by_p: Dict[str, Set[str]] = {}
    for r in rows:
        dates_by_p.setdefault(r["pipeline"], set()).add(str(r["date"]))
    if not pipelines:
        return set()
    common = set(dates_by_p.get(pipelines[0], set()))
    for p in pipelines[1:]:
        common &= dates_by_p.get(p, set())
    return common


def _run_avg(rows: List[Dict], pipeline: str, keep: Set[str]) -> Optional[Dict[str, float]]:
    pr = [r for r in rows if r["pipeline"] == pipeline and str(r["date"]) in keep]
    if not pr:
        return None
    return {
        "avg_cost_usd":   float(np.mean([r["total_cost_usd"]   for r in pr])),
        "avg_peak_kw":    float(np.mean([r["peak_load_kw"]     for r in pr])),
        "avg_unmet_kwh":  float(np.mean([r["total_unmet_kwh"]  for r in pr])),
        "avg_served_pct": float(np.mean([r["pct_fully_served"] for r in pr])),
        "avg_violations": float(np.mean([r["violation_count"]  for r in pr])),
        "n_days": len({r["date"] for r in pr}),
    }


def _aggregate(all_run_rows: List[Tuple[int, List[Dict]]], pipelines: List[str]) -> List[Dict]:
    metric_keys = ["avg_cost_usd", "avg_peak_kw", "avg_unmet_kwh", "avg_served_pct", "avg_violations"]
    result: List[Dict] = []
    for pipeline in pipelines:
        run_avgs: List[Dict[str, float]] = []
        days_per_run: List[int] = []
        for _, rows in all_run_rows:
            common = _aligned_dates(rows, pipelines)
            avg = _run_avg(rows, pipeline, common)
            if avg is not None:
                run_avgs.append(avg)
                days_per_run.append(int(avg["n_days"]))
        if not run_avgs:
            continue
        n = len(run_avgs)
        row: Dict = {
            "pipeline": pipeline,
            "n_runs": n,
            "avg_days_per_run": float(np.mean(days_per_run)),
        }
        for k in metric_keys:
            vals = [a[k] for a in run_avgs]
            row[f"mean_{k}"] = float(np.mean(vals))
            row[f"std_{k}"]  = float(np.std(vals, ddof=1)) if n > 1 else 0.0
        result.append(row)
    return result


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def _fmt(mean: float, std: float) -> str:
    return f"{mean:.2f} ± {std:.2f}"


def _write_table_md(agg_rows: List[Dict], path: Path, temperature: float, n_runs: int) -> None:
    avg_days = agg_rows[0]["avg_days_per_run"] if agg_rows else 0
    lines = [
        f"# Multi-Run Average Results (temperature={temperature}, {n_runs} runs, ~{avg_days:.0f} days/run)",
        "",
        "Values are **mean ± sample std dev** across runs (each run uses the same date set).",
        "LLM temperature > 0 introduces stochasticity; optimizer std dev is ~0 (deterministic).",
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


def _plot_bar(agg_rows: List[Dict], path: Path, temperature: float) -> None:
    import matplotlib.pyplot as plt

    pipelines = [r["pipeline"] for r in agg_rows]
    metrics = [
        ("mean_avg_cost_usd",   "std_avg_cost_usd",   "Cost ($)"),
        ("mean_avg_peak_kw",    "std_avg_peak_kw",    "Peak (kW)"),
        ("mean_avg_unmet_kwh",  "std_avg_unmet_kwh",  "Unmet (kWh)"),
        ("mean_avg_served_pct", "std_avg_served_pct", "Served (%)"),
    ]
    n_metrics = len(metrics)
    n_p = len(pipelines)
    width = 0.8 / n_p
    x = np.arange(n_metrics)

    fig, ax = plt.subplots(figsize=(11, 5))
    for i, pipeline in enumerate(pipelines):
        rec = next(r for r in agg_rows if r["pipeline"] == pipeline)
        means = [rec[mk] for mk, _, _ in metrics]
        stds  = [rec[sk] for _, sk, _ in metrics]
        offset = (i - n_p / 2 + 0.5) * width
        ax.bar(x + offset, means, width, label=pipeline.capitalize(),
               yerr=stds, capsize=4, error_kw={"elinewidth": 1.2, "capthick": 1.2})

    n_runs = agg_rows[0]["n_runs"] if agg_rows else 0
    ax.set_xticks(x)
    ax.set_xticklabels([label for _, _, label in metrics])
    ax.set_ylabel("Value")
    ax.set_title(f"Benchmark Results — temperature={temperature}, N={n_runs} runs (error bars = ±1 std dev)")
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
            "Run benchmark N times at a specified LLM temperature to measure output "
            "variance. Same dates used every run; mean ± std dev reported."
        )
    )
    parser.add_argument("--nruns", type=int, default=5,
                        help="Number of independent runs (default: 5)")
    parser.add_argument("--temperature", type=float, default=0.7,
                        help="LLM temperature for agent and baseline (default: 0.7)")
    parser.add_argument("--ndays", type=int, default=None,
                        help="Use first N benchmark dates per run (default: all 20)")
    parser.add_argument("--dates", nargs="+", default=None,
                        help="Override date list as YYYY-MM-DD")
    parser.add_argument("--output-dir", type=Path,
                        default=_project_root / "benchmark_results" / "vary_temperature",
                        help="Root output directory")
    parser.add_argument("--skip-optimizer", action="store_true")
    parser.add_argument("--skip-baseline",  action="store_true")
    parser.add_argument("--skip-agent",     action="store_true")
    args = parser.parse_args()

    dates: List[date] = (
        [date.fromisoformat(d) for d in args.dates] if args.dates else list(BENCHMARK_DATES)
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
    print(f"Temperature : {args.temperature}")
    print(f"Dates/run   : {len(dates)} ({dates[0]} to {dates[-1]}) — same set every run")
    print()

    all_run_rows: List[Tuple[int, List[Dict]]] = []
    for run_id in range(1, args.nruns + 1):
        print(f"{'='*60}")
        print(f"RUN {run_id} / {args.nruns}  (temperature={args.temperature})")
        print(f"{'='*60}")
        rows = _run_single(
            run_id, dates, out_dir, args.temperature,
            skip_optimizer=args.skip_optimizer,
            skip_agent=args.skip_agent,
            skip_baseline=args.skip_baseline,
        )
        if rows:
            all_run_rows.append((run_id, rows))
        else:
            print(f"  [Run {run_id}] WARNING: no rows — skipping in aggregation.\n")

    if not all_run_rows:
        print("No results. Check API keys and ACN_DATA_API_TOKEN.", file=sys.stderr)
        sys.exit(1)

    all_csv = out_dir / "all_runs_metrics.csv"
    _write_all_runs_csv(all_run_rows, all_csv)
    print(f"Wrote {all_csv}  ({sum(len(r) for _, r in all_run_rows)} rows)")

    all_flat = [r for _, rows in all_run_rows for r in rows]
    seen = {r["pipeline"] for r in all_flat}
    pipelines = [p for p in ["optimizer", "baseline", "agent"] if p in seen]
    agg_rows = _aggregate(all_run_rows, pipelines)

    if not agg_rows:
        print("No aggregated results.", file=sys.stderr)
        sys.exit(1)

    table_path = out_dir / "multi_run_average_table.md"
    _write_table_md(agg_rows, table_path, args.temperature, len(all_run_rows))
    print(f"Wrote {table_path}")

    bar_path = out_dir / "multi_run_average_bar.png"
    _plot_bar(agg_rows, bar_path, args.temperature)
    print(f"Wrote {bar_path}")

    # Console summary
    print("\n" + "="*60)
    print(f"SUMMARY  temperature={args.temperature}  N={len(all_run_rows)} runs")
    print("="*60)
    print(f"{'Pipeline':<12} {'Cost ($)':>20} {'Served (%)':>20} {'Unmet (kWh)':>22}")
    print("-"*76)
    for r in agg_rows:
        print(
            f"{r['pipeline']:<12} "
            f"{_fmt(r['mean_avg_cost_usd'],  r['std_avg_cost_usd']):>20} "
            f"{_fmt(r['mean_avg_served_pct'], r['std_avg_served_pct']):>20} "
            f"{_fmt(r['mean_avg_unmet_kwh'],  r['std_avg_unmet_kwh']):>22}"
        )
    print(f"\n(mean ± sample std dev, same {len(dates)}-date set repeated {len(all_run_rows)} times)")
    print("\nDone.")


if __name__ == "__main__":
    main()
