# ECE 285 — Agentic EV Charging Schedule Assistant

**Group 10**: Ryan Luo, Peter Quawas

This repository contains a day-ahead EV charging benchmark with three pipelines:
- Optimizer (CVXPY)
- Direct LLM baseline
- Agent pipeline (Plan -> Optimize -> Validate -> Refine -> Explain)

For reproducibility, all benchmark scripts write explicit artifacts (CSV, markdown summaries, plots) under `benchmark_results/` and can be rerun from the project root with fixed dates, seeds, and model settings.

## Layout

| Path | Purpose |
|------|---------|
| `agent/` | Agentic pipeline: Plan → Optimize → Validate → Refine → Explain |
| `baseline/` | Direct LLM prompting baseline |
| `config/` | Site constraints, TOU rates, experiment configs |
| `constraints/` | Constraint checker (availability, per-charger, site cap, energy) |
| `data/` | ACN-Data loader and standardized session format |
| `evaluation/` | Metrics, benchmark runner, faithfulness evaluation |
| `optimization/` | CVXPY cost-minimization formulation and solver |
| `scripts/` | CLI entry points for all pipelines and benchmarks |
| `tests/` | Unit and integration tests |
| `visualization/` | Schedule and load-profile plots |
| `web/` | FastAPI server and HTML chat UI |
| `experiments/` | Benchmark outputs (CSV, JSON, plots) — gitignored |
| `final_report_results/` | Pre-computed results used in the final report |
| `acnportal/` | ACN-Data/ACN-Sim client (cloned separately, see Setup) |

## Setup

### 1) Clone the project and `acnportal`

```bash
git clone <this-repo-url>
cd Project
git clone https://github.com/zach401/acnportal acnportal
```

`acnportal` is intentionally kept as a separate dependency and is installed from `./acnportal` via `requirements.txt`.

### 2) Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

If you prefer `uv`, this also works:

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

### 3) Configure environment variables

```bash
cp .env.example .env
```

Add whichever keys match your run mode:

```bash
ACN_DATA_API_TOKEN=your_caltech_acn_token   # required for ACN API-backed runs
OPENAI_API_KEY=your_openai_key              # required for gpt-* models
ANTHROPIC_API_KEY=your_anthropic_key        # required for claude-* models
```

Notes:
- `ACN_DATA_API_TOKEN` is required for any command that fetches real sessions from ACN-Data.
- For LLM phases (baseline/agent), you need either `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`, depending on model family.
- `.env` is gitignored and should stay local.

### 4) Verify environment before running benchmarks

```bash
python --version
pip --version
python -c "import cvxpy, numpy, pandas, matplotlib; print('deps ok')"
pytest -q
```

If `pytest -q` passes, the local environment is ready for benchmark reproduction.

## Tests

From the project root with the venv active:

```bash
pytest
```

To run a specific file:

```bash
pytest tests/test_constraints.py
pytest tests/test_baseline_parse.py
pytest tests/test_data_loader.py
pytest tests/test_faithfulness.py
```

- `test_constraints.py` — constraint checker: feasible schedule and one violation per constraint type
- `test_baseline_parse.py` — LLM output resampling and schedule parsing
- `test_data_loader.py` — ACN-Data API loader and session format conversion (skips live fetch if token not set)
- `test_faithfulness.py` — claim extraction and ground-truth comparison for explanation faithfulness

## Web GUI

Start the server from the project root:

```bash
uvicorn web.app:app --reload --port 8000
```

Then open http://localhost:8000.

You can type a natural-language scheduling request like:

> "I have 5 EVs. EV1 arrives at 08:00, leaves at 17:00, and needs 20 kWh. EV2 arrives at 09:00, leaves at 18:00, needs 15 kWh. Site capacity is 50 kW. Schedule for today."

The agent parses the request, solves the optimizer, validates constraints, and returns a plain-English explanation with a schedule table and load-profile chart. Follow-up questions like "what if EV3 arrives two hours later?" work within the same session.

Needs `OPENAI_API_KEY` in `.env`.

## Running the Pipelines

Run all commands from the repo root with your virtual environment active.

### Reproducibility checklist (recommended order)

1. Verify the optimizer is working deterministically:

```bash
python -m scripts.run_phase_a --site caltech --date 2019-06-15
```

2. Run a quick 3-pipeline smoke test over a few dates (temperature=0, not the paper configuration):

```bash
python -m scripts.run_agent_vs_baseline --dates 2019-05-01 2019-05-08 2019-05-15
```

3. Run the full paper experiments (see Exact rerun recipes below).

4. Recompute summary tables from any existing CSV without rerunning:

```bash
python -m scripts.recompute_averages --csv benchmark_results/agent_vs_baseline_metrics.csv --mode both
```

### Single-day sanity commands

```bash
# Optimizer only (no LLM)
python -m scripts.run_phase_a --site caltech --date 2019-06-15

# Baseline LLM
python -m scripts.run_baseline --site caltech --date 2019-06-15 --model gpt-4o

# Full agent pipeline
python -m scripts.run_agent --site caltech --date 2019-06-15
```

What each command does:
- `run_phase_a`: deterministic CVXPY optimizer + constraint checks + metrics + plots.
- `run_baseline`: prompt-only LLM scheduler + parser + checks/metrics.
- `run_agent`: full Plan -> Optimize -> Validate -> Refine -> Explain pipeline.

### API mode vs text mode

`run_agent` supports two ways to run:

```bash
# API mode: pulls real ACN sessions (needs ACN_DATA_API_TOKEN)
python -m scripts.run_agent --site caltech --date 2019-01-15

# Text mode: no ACN API token needed
python -m scripts.run_agent --text "I have 2 EVs: EV1 arrives 6pm leaves 10pm needs 20 kWh, EV2 arrives 7pm leaves 11pm needs 15 kWh"
```

For benchmark reproduction, prefer API mode with explicit `--date` values.

### Standard benchmark (optimizer vs baseline vs agent)

```bash
python -m scripts.run_agent_vs_baseline
python -m scripts.run_agent_vs_baseline --ndays 10
python -m scripts.run_agent_vs_baseline --dates 2019-06-15 2019-06-16
python -m scripts.run_agent_vs_baseline --skip-baseline
```

Main outputs go to `benchmark_results/`:
- `agent_vs_baseline_metrics.csv`
- `day_by_day_comparison.md`
- `average_results_table.md`
- `average_results_bar.png`
- `per_day/*.png` plots for each pipeline/day

Determinism notes:
- Optimizer outputs are deterministic for a fixed date/configuration.
- LLM outputs depend on model and temperature settings.
- To minimize stochastic variation, use fixed dates and temperature `0.0` where applicable.

### Multi-run benchmarks (variance and robustness analysis)

The two temperature-variation runs below are the ones used in the paper (see Exact rerun recipes). The others are additional experiments available for exploratory use.

```bash
# Paper experiment: non-zero LLM temperature, same dates every run
python -m scripts.run_benchmark_vary_temperature --nruns 5 --temperature 0.7 --model gpt-4o
python -m scripts.run_benchmark_vary_temperature --nruns 5 --temperature 0.7 --model claude-sonnet-4-6

# Additional: repeat same date set across runs, temperature fixed to 0.0
python -m scripts.run_multi_run_benchmark --nruns 5 --ndays 20

# Additional: sample different date subsets each run (date-composition sensitivity)
python -m scripts.run_benchmark_vary_dates --nruns 5 --ndays 19 --seed 42
```

Outputs are written under `benchmark_results/` in run-specific folders (for example `vary_dates/` and `vary_temperature_<model>/`) with:
- per-run CSVs/plots
- `all_runs_metrics.csv`
- `multi_run_average_table.md`
- `multi_run_average_bar.png`

Resume support (temperature benchmark):

```bash
python -m scripts.run_benchmark_vary_temperature --nruns 5 --start-run 3 --temperature 0.7 --model gpt-4o
```

This reuses `run_1` and `run_2` from disk and continues from run 3.

### Script-to-key matrix

| Script | Needs ACN token | Needs LLM key |
|------|------------------|---------------|
| `run_phase_a` | Yes | No |
| `run_baseline` | Yes | Yes |
| `run_agent` (API mode) | Yes | Yes |
| `run_agent` (text mode) | No | Yes |
| `run_agent_vs_baseline` | Yes | Yes |
| `run_multi_run_benchmark` | Yes | Yes (unless skipping LLM phases) |
| `run_benchmark_vary_dates` | Yes | Yes (unless skipping LLM phases) |
| `run_benchmark_vary_temperature` | Yes | Yes (provider-specific) |

### Recompute averages without rerunning expensive jobs

```bash
python -m scripts.recompute_averages --csv benchmark_results/agent_vs_baseline_metrics.csv --mode both
```

Helpful when you only need refreshed aligned/unaligned summary tables and plots.

## Exact rerun recipes

These two commands reproduce Table V in the paper (mean ± std dev across 5 runs × 20 days, temperature=0.7). Both use `--site caltech` (the Caltech campus garage in the ACN-Data platform). All 20 benchmark dates are used by default.

### Reproduce paper Table V — GPT-4o rows

Requires `OPENAI_API_KEY`.

```bash
python -m scripts.run_benchmark_vary_temperature \
    --nruns 5 --temperature 0.7 --model gpt-4o
```

Expected artifacts:
- `benchmark_results/vary_temperature_gpt-4o/all_runs_metrics.csv`
- `benchmark_results/vary_temperature_gpt-4o/multi_run_average_table.md`
- `benchmark_results/vary_temperature_gpt-4o/multi_run_average_bar.png`

### Reproduce paper Table V — Claude Sonnet 4.6 rows

Requires `ANTHROPIC_API_KEY`.

```bash
python -m scripts.run_benchmark_vary_temperature \
    --nruns 5 --temperature 0.7 --model claude-sonnet-4-6
```

Expected artifacts:
- `benchmark_results/vary_temperature_claude-sonnet-4-6/all_runs_metrics.csv`
- `benchmark_results/vary_temperature_claude-sonnet-4-6/multi_run_average_table.md`
- `benchmark_results/vary_temperature_claude-sonnet-4-6/multi_run_average_bar.png`

Together these two runs produce all five rows of Table V (the Numerical Solver row appears in both; results are identical since the optimizer is deterministic).

Pre-computed versions of both are already in `benchmark_results/`. The example schedule and load-profile plots in `final_report_results/` were generated with `run_phase_a` and `run_agent` on individual benchmark dates.

## Pre-computed Results

`final_report_results/` contains the artifacts used in the report:

- `agent_vs_baseline_metrics.csv` — per-day benchmark metrics
- `average_results_table.md` — aggregated comparison table
- `average_results_bar.png` — aggregated comparison bar chart
- `phase_a_schedule.png`, `phase_a_load.png` — optimizer example outputs
- `agent_schedule.png`, `agent_load.png` — agent example outputs
- `per_day/` — per-day schedule/load plots across pipelines

## Report

Final report: `reports/final_report.tex` (PDF: `reports/i.pdf`).
