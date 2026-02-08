# ECE 285 Project — Agentic EV Charging Schedule Assistant

**Group #10**: Ryan Luo, Peter Quawas

Day-ahead charging schedule assistant for a parking facility: LLM baseline vs agentic pipeline (optimization + grounded explanations). Data from Caltech ACN-Data; objective: minimize TOU energy cost; report peak load and evaluate explanation faithfulness.

## Layout

| Path | Purpose |
|------|--------|
| `data/` | Data loader (ACN-Data), standardized session format |
| `constraints/` | Constraint checker (availability, per-charger, site cap, energy) |
| `baseline/` | Direct LLM prompting baseline |
| `agent/` | Agentic pipeline: Plan → Optimize → Validate → Refine → Explain |
| `optimization/` | CVXPY formulation and solver |
| `evaluation/` | Metrics, benchmark, faithfulness evaluation |
| `visualization/` | Schedule and load profile plots |
| `config/` | Site constraints, TOU rates, experiment configs |
| `scripts/` | Run baseline, agent, benchmark |
| `experiments/` | Benchmark outputs and tables |
| `stretch/` | Peak-penalty sweep, what-if queries |
| `docs/` | Report notes, ablations |
| `tests/` | Unit and integration tests |
| `acnportal/` | ACN-Data/ACN-Sim client (clone separately; see Setup) |

## Deliverables (proposal)

- **Midway**: Data loader + format + constraint checker; baseline + evaluation; agent v1 + optimization + visualization.
- **Final**: Full benchmark (5+ days); faithfulness suite; stretch: peak-penalty, what-if; final report.

## Setup

### 1. Clone this repo (and acnportal)

```bash
git clone <this-repo-url>
cd Project
```

The ACN-Sim client lives in `acnportal/` and is not included in this repo. From the project root:

```bash
git clone https://github.com/zach401/acnportal acnportal
```

### 2. Python environment (uv)

From the project root:

```bash
uv venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

### 3. Select the interpreter (Cursor / VS Code)

1. **Cmd+Shift+P** (macOS) or **Ctrl+Shift+P** (Windows/Linux) → **Python: Select Interpreter**.
2. Pick the entry for this project’s venv:
   - **macOS/Linux**: `./.venv/bin/python` or `Python 3.x.x ('.venv': venv)`
   - **Windows**: `.\.venv\Scripts\python.exe`
3. If it’s not listed, choose **Enter interpreter path…** and set:
   - **macOS/Linux**: `<project-root>/.venv/bin/python`
   - **Windows**: `<project-root>\.venv\Scripts\python.exe`

The status bar shows the active interpreter; use it to switch if you have multiple projects open.

### 4. Other

- ACN-Data API token from [ev.caltech.edu](https://ev.caltech.edu) for loading sessions.

## Publishing to GitHub

Before pushing:

- **Secrets**: Store the ACN-Data API token (and any LLM keys) in environment variables or `.env`; never commit them. `.env` is in `.gitignore`.
- **Build**: From project root, `uv pip install -r requirements.txt` and run tests so the repo builds cleanly for others.
- **Artifacts**: `experiments/` outputs (CSV, JSON, plots) are ignored; the folder stays tracked via `.gitkeep`. Add a sample or document expected outputs if useful.

## Reference

Project proposal: `285_Project_Proposal-2.pdf` (see repo or course materials).
