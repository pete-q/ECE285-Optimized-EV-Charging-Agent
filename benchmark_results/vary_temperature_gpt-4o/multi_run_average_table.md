# Multi-Run Average Results (temperature=0.7, 5 runs, ~20 days/run)

Values are **mean ± sample std dev** across runs (each run uses the same date set).
LLM temperature > 0 introduces stochasticity; optimizer std dev is ~0 (deterministic).

| Pipeline | Runs | Days/Run | Cost ($) | Peak (kW) | Unmet (kWh) | Served (%) | Violations |
|----------|------|----------|----------|-----------|-------------|------------|------------|
| optimizer |    5 |     20.0 | 100.83 ± 0.00 | 47.35 ± 0.00 | 27.82 ± 0.00 | 71.31 ± 0.00 | 15.80 ± 0.00 |
| baseline  |    5 |     20.0 | 95.29 ± 10.55 | 76.90 ± 5.69 | 209.47 ± 8.07 | 36.36 ± 2.81 | 121.62 ± 6.36 |
| agent     |    5 |     20.0 | 100.83 ± 0.00 | 47.35 ± 0.00 | 27.82 ± 0.00 | 71.31 ± 0.00 | 15.80 ± 0.00 |