"""Script: load config and sessions, run baseline, optionally run checker and print metrics."""

# Usage idea:
#   python -m scripts.run_baseline
# or
#   python scripts/run_baseline.py
#
# Load .env from project root. Load sessions (synthetic if no ACN token).
# Build site + TOU config, run baseline, run constraint checker, print metrics.
# Optionally save schedule or pass --output experiments/baseline_out.json.


def main() -> None:
    ...


if __name__ == "__main__":
    main()
