# Paper Updates — Session Log

This document tracks all changes made to the project for the paper submission, including motivation and implementation details.

---

## Session: April 24, 2026

### Goal
Improve benchmark rigor for the paper by (1) averaging results across multiple runs and (2) capturing variance via mean ± std dev — the standard format for LLM evaluation papers.

---

### 1. Multi-Run Benchmark Script (`scripts/run_multi_run_benchmark.py`) — NEW

**Why:** The original `run_agent_vs_baseline.py` ran the full optimizer / agent / baseline pipeline exactly once over 19–20 benchmark dates. A single run is not sufficient for a paper — results must be averaged across multiple independent runs to show stability and reduce noise.

**What it does:**
- Runs the full pipeline N times (default: 3) over the same 20 benchmark dates
- Each run writes to its own subdirectory: `benchmark_results/run_N/`
- After all runs, aggregates across runs with **mean ± sample std dev** (ddof=1)
- All per-day rows from every run are combined into `all_runs_metrics.csv` (with a `run_id` column)
- Produces `multi_run_average_table.md` and `multi_run_average_bar.png` with error bars

**Usage:**
```bash
python -m scripts.run_multi_run_benchmark                      # 3 runs, 20 dates
python -m scripts.run_multi_run_benchmark --nruns 5 --ndays 19
python -m scripts.run_multi_run_benchmark --nruns 3 --skip-baseline
```

---

### 2. Temperature Parameter Threaded Through LLM Stack

**Why:** Both scripts below require controllable LLM temperature. Previously it was hardcoded to `0.0` everywhere.

**Files changed:**

| File | Change |
|------|--------|
| `agent/llm_agent.py` | Added `temperature: float = 0.0` parameter to `run_agent_llm`; forwarded to all 3 internal OpenAI API calls |
| `agent/run.py` | Added `temperature: float = 0.0` to `run_agent`; forwarded to `run_agent_llm` |
| `baseline/run.py` | Added `temperature: float = 0.0` to `run_baseline`; forwarded to the OpenAI API call |
| `scripts/run_agent_vs_baseline.py` | Added `temperature: float = 0.0` to `run_phase_agent` and `run_phase_baseline`; forwarded to `run_agent` and `run_baseline` respectively |

**Backward compatibility:** All new `temperature` parameters default to `0.0`, so existing behavior and any callers not passing the argument are completely unchanged.

---

### 3. Temperature-Variation Benchmark (`scripts/run_benchmark_vary_temperature.py`) — NEW

**Why:** With `temperature=0.0`, the LLM is (nearly) deterministic, so repeated runs over the same dates produce near-identical outputs and std dev ≈ 0. To get meaningful variance for the paper, the LLM temperature must be raised. This script measures **output variance due to LLM stochasticity**.

**What it does:**
- Runs the pipeline N times (default: 5) over the **same fixed date set** each run
- Uses a configurable LLM temperature (default: `0.7`) for agent and baseline
- The optimizer is always deterministic regardless of temperature (std dev ≈ 0 for optimizer, meaningful for agent/baseline)
- Produces the same output structure as `run_multi_run_benchmark` under `benchmark_results/vary_temperature/`

**Usage:**
```bash
python -m scripts.run_benchmark_vary_temperature                          # 5 runs, temp=0.7
python -m scripts.run_benchmark_vary_temperature --nruns 5 --temperature 1.0
python -m scripts.run_benchmark_vary_temperature --nruns 3 --ndays 10 --skip-baseline
```

---

### 4. Date-Set Variation Benchmark (`scripts/run_benchmark_vary_dates.py`) — NEW

**Why:** An alternative approach to multi-run averaging: instead of varying LLM temperature, each run samples a **different random subset of dates** from a larger pool. This tests how sensitive pipeline metrics are to *which days* are selected — measuring generalization rather than stochasticity. Temperature is fixed at `0.0`.

**What it does:**
- Defines a pool of ~70 known-good ACN Caltech weekday dates spanning 2018–2019 (covering the same dense periods as the original benchmark, with additional neighbouring weekdays added)
- Each run samples 19 dates **without replacement** from this pool using a seeded RNG (reproducible via `--seed`)
- Writes `run_N/dates_used.txt` recording exactly which dates each run used
- Produces the same aggregate outputs (`all_runs_metrics.csv`, `multi_run_average_table.md`, `multi_run_average_bar.png`) under `benchmark_results/vary_dates/`

**Usage:**
```bash
python -m scripts.run_benchmark_vary_dates                         # 5 runs, 19 dates, seed=42
python -m scripts.run_benchmark_vary_dates --nruns 5 --ndays 19 --seed 42
python -m scripts.run_benchmark_vary_dates --nruns 3 --seed 99 --skip-baseline
```

---

### Summary of New / Modified Files

| File | Status | Purpose |
|------|--------|---------|
| `scripts/run_multi_run_benchmark.py` | **New** | Run same dates N times, aggregate with mean ± std |
| `scripts/run_benchmark_vary_temperature.py` | **New** | Same dates N times, raised temperature, measure LLM variance |
| `scripts/run_benchmark_vary_dates.py` | **New** | Different random date sample per run, measure day-composition sensitivity |
| `agent/llm_agent.py` | Modified | `temperature` param added to `run_agent_llm` |
| `agent/run.py` | Modified | `temperature` param added to `run_agent` |
| `baseline/run.py` | Modified | `temperature` param added to `run_baseline` |
| `scripts/run_agent_vs_baseline.py` | Modified | `temperature` param added to `run_phase_agent` and `run_phase_baseline` |
