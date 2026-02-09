# Scripts

## Phase A (implemented)

- **`run_phase_a`**: Load sessions from API (`--site`, `--date`), run optimizer, run constraint checker, compute metrics (cost, peak, unmet, % fully served, % cost reduction vs uncontrolled), print results and violations (if any), save schedule and load profile to `experiments/`.
  ```bash
  python -m scripts.run_phase_a --site caltech --date 2019-06-15
  ```
  Requires `ACN_DATA_API_TOKEN` in `.env`.

## Planned

- **run_baseline**: Load data, run prompting baseline, (optional) repair, write schedule + metrics.
- **run_agent**: Load data, run agentic pipeline, write schedule + explanation + metrics.
- **run_benchmark**: Run baseline and agent over 5+ days; output tables.
- **evaluate_faithfulness**: Faithfulness suite; qualitative examples for report.
