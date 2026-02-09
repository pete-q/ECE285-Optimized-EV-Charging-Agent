# Midway Report: Deliverables

**ECE 285 Project — Agentic EV Charging Schedule Assistant**  
**Group #10**: Ryan Luo, Peter Quawas

This document describes **what each file does**, **how it works**, and the **current status** of midway deliverables. It is structured in three parts: **Part I** (completed Phase A), **Part II** (remaining Phase B), and **Part III** (remaining Phase C).

---

## Table of contents

1. [Part I — Completed (Phase A)](#part-i--completed-phase-a)
   - 1.1 [Standardized session format](#11-standardized-session-format-dataformat)
   - 1.2 [Data loader](#12-data-loader-dataloader)
   - 1.3 [Config](#13-config-config)
   - 1.4 [Constraint checker](#14-constraint-checker-constraints)
   - 1.5 [Optimization solver](#15-optimization-solver-optimization)
   - 1.6 [Evaluation metrics](#16-evaluation-metrics-evaluationmetrics)
   - 1.7 [Visualization](#17-visualization-visualization)
   - 1.8 [Phase A script](#18-phase-a-script-scriptsrun_phase_apy)
   - 1.9 [Tests](#19-tests-tests)
   - 1.10 [End-to-end data flow](#110-end-to-end-data-flow-phase-a)
2. [Part II — Remaining: Phase B (Baseline + evaluation)](#part-ii--remaining-phase-b-baseline--evaluation)
3. [Part III — Remaining: Phase C (Agent v1)](#part-iii--remaining-phase-c-agent-v1)
4. [Reference: Midway checklist](#reference-midway-deliverable-checklist)

---

# Part I — Completed (Phase A)

## 1.1 Standardized session format (`data/format/`)

### File: `data/format/schema.py`

**Purpose**  
Defines the single canonical data shape for one day of EV charging sessions. Every other module (loader, checker, solver, baseline, agent) uses these types so that session order, time convention, and units are consistent.

**What it does**
- Exposes two dataclasses and two constants.
- **`Session`** (frozen): One EV visit. Fields: `session_id`, `arrival_idx`, `departure_idx`, `energy_kwh`, `charger_id`, `max_power_kw`. Validation in `__post_init__`: indices non-negative and ordered, energy and max_power positive.
- **`DaySessions`**: One day. Fields: `sessions` (list of `Session`), `n_steps` (number of time steps), `dt_hours` (duration of one step, default 0.25). Validation: `n_steps` and `dt_hours` positive; every session has `departure_idx ≤ n_steps`.
- **`DEFAULT_DT_HOURS`** = 0.25, **`DEFAULT_STEPS_PER_HOUR`** = 4.

**How it works**
- Time is **discrete**: step indices `0 .. n_steps-1`. Charging is allowed only for steps `t` in the half-open interval **[arrival_idx, departure_idx)**.
- Units: power in **kW**, energy in **kWh**. Schedule matrices have shape `(n_sessions, n_steps)` with the same order as `day.sessions`.

**Consumers**  
Loader (output), checker (input), solver (input), metrics (input), visualization (input), baseline/agent (input).

---

## 1.2 Data loader (`data/loader/`)

### File: `data/loader/loader.py`

**Purpose**  
Fetch charging sessions from the Caltech ACN-Data API for a given site and date, and convert them into the project’s standardized format (`DaySessions`). No synthetic data; API key required.

**What it does**
- **`load_sessions(site_id, day_date, api_token=None, n_steps=96, dt_hours=0.25)`**  
  - Reads `ACN_DATA_API_TOKEN` from `api_token` or environment if not provided.  
  - Builds a UTC date range: midnight of `day_date` to midnight of the next day.  
  - Calls the Eve API with a **MongoDB-style JSON** `where` clause: `{"$and": [{"connectionTime": {"$gte": "<RFC1123 start>"}}, {"connectionTime": {"$lte": "<RFC1123 end>"}}]}` (URL-encoded). The ev.caltech.edu API expects this format; the acnportal `DataClient` uses a different string format and is not used.  
  - Sends `GET` to `https://ev.caltech.edu/api/v1/sessions/<site_id>?where=...&sort=connectionTime&max_results=100` with HTTP Basic auth (token as username, empty password).  
  - Handles 401/403 and `_error` in the JSON body; raises `ValueError` with a clear message.  
  - Iterates `_items` and follows `_links.next` for pagination.  
  - For each raw session dict, calls `raw_session_to_standard(...)` and collects `Session` objects.  
  - Returns `DaySessions(sessions=..., n_steps=n_steps, dt_hours=dt_hours)`.

- **`raw_session_to_standard(raw, day_start_utc, dt_hours, n_steps)`**  
  - **Input**: One API session dict (keys: `connectionTime`, `disconnectTime`, `kWhDelivered`, `sessionID`, `spaceID`; optional `maxPower`).  
  - **Helper** `_parse_session_time(value, day_start_utc)`: Converts API time (RFC 1123 string or datetime) to seconds since `day_start_utc`; then converts to step indices.  
  - Converts connection/disconnect times to `arrival_idx` and `departure_idx` (clamped to `[0, n_steps]`).  
  - Reads `kWhDelivered` as requested energy (default 1.0 if missing/zero); uses `DEFAULT_MAX_POWER_KW` (7.0) if max power is missing or invalid.  
  - **Output**: One `Session` instance.

**How it works**
- All times are interpreted relative to **midnight UTC** for the requested calendar day. The API returns sessions whose `connectionTime` falls in that UTC window.
- Session order in `DaySessions` matches the API response order (sorted by `connectionTime` via `sort=connectionTime`).

---

## 1.3 Config (`config/`)

### File: `config/site.py`

**Purpose**  
Central place for site-level constraints and time-of-use (TOU) energy rates. Used by the optimizer, constraint checker, evaluation, and (later) baseline and agent so that all use the same horizon and costs.

**What it does**
- **`SiteConfig`**  
  - **Attributes**: `P_max_kw` (float or array of length `n_steps`), `n_steps`, `dt_hours` (default 0.25).  
  - **Method** `get_P_max_at_step(t)`: Returns the power cap in kW at step `t` (scalar or `P_max_kw[t]`).  
  - Used to enforce: at each time step `t`, total power ≤ P_max(t).

- **`TOUConfig`**  
  - **Attributes**: `rates_per_kwh` (1D array of length `n_steps`; $/kWh per step).  
  - **Property** `n_steps`: `len(rates_per_kwh)`.  
  - Used in the objective: minimize ∑_t c(t) × (total power at t) × dt.

- **`default_tou_rates(n_steps, peak_price=0.45, off_peak_price=0.12)`**  
  - Builds a rate vector of length `n_steps`. Step 0 = midnight. Peak window 4pm–9pm (steps 64–84 for 96 steps) gets `peak_price`; all other steps get `off_peak_price`.  
  - Returns a numpy array; typically wrapped as `TOUConfig(rates_per_kwh=default_tou_rates(day.n_steps))`.

**How it works**
- Callers (solver, checker, scripts) build `SiteConfig` and `TOUConfig` from the same `day.n_steps` and `day.dt_hours` so horizon and step duration are consistent.

---

## 1.4 Constraint checker (`constraints/`)

### File: `constraints/checker.py`

**Purpose**  
Verify that a given schedule (a matrix of power values) satisfies all problem constraints: availability, per-charger limits, site power cap, and energy delivery. Used to validate optimizer output and (later) baseline output.

**What it does**
- **`check(schedule, day, site, dt_hours=None, tol=None)`**  
  - **Inputs**: `schedule` shape `(n_sessions, n_steps)` (kW); `day` (`DaySessions`); `site` (`SiteConfig`); optional `dt_hours` (defaults to `day.dt_hours`); optional `tol` (defaults to `DEFAULT_TOL = 1e-5`).  
  - **Output**: `CheckResult`: `feasible` (bool), `violations` (list of `Violation`), `unmet_energy_kwh` (per-session array), `peak_load_kw` (float).

- **`Violation`** dataclass: `kind` ("availability" | "per_charger" | "site_cap" | "energy"), `session_id`, `time_step`, `message` (string with numeric details for debugging).

**How it works**
- Single pass over sessions and time steps:  
  - For each (session i, step t): read `p = schedule[i, t]`. Accumulate `total_power[t]` and per-session `delivered`.  
  - **Availability**: If `t < arrival_idx` or `t >= departure_idx` and `|p| > tol`, record an availability violation.  
  - **Per-charger**: If `p < -tol` or `p > max_power_kw + tol`, record a per_charger violation.  
  - **Energy**: After the loop over t for session i, compute `unmet_i = energy_kwh - delivered`. If `unmet_i < -tol` (over-delivery) or `unmet_i > tol` (under-delivery), record an energy violation. Store `unmet_energy_kwh[i] = max(0, unmet_i)`.  
- Second pass over t: if `total_power[t] > P_max(t) + tol`, record a site_cap violation.  
- **Feasible** = True iff `len(violations) == 0`. **peak_load_kw** = max of `total_power`.  
- Using `DEFAULT_TOL = 1e-5` avoids treating tiny solver numerical errors as violations (CVXPY typically achieves ~1e-8).

---

## 1.5 Optimization solver (`optimization/`)

### File: `optimization/solver.py`

**Purpose**  
Compute an optimal charging schedule that minimizes TOU energy cost plus a penalty for unmet energy, subject to availability, per-charger limits, site cap, and energy balance. This is the core “optimizer” used by Phase A and (later) by the agent.

**What it does**
- **`solve(day, site, tou, penalty_unmet=1e6)`**  
  - **Inputs**: `day` (`DaySessions`), `site` (`SiteConfig`), `tou` (`TOUConfig`), `penalty_unmet` (M in the objective, $/kWh).  
  - **Output**: `SolveResult`: `schedule` (numpy array, shape `(n_sessions, n_steps)`), `total_cost_usd`, `unmet_energy_kwh` (per session), `peak_load_kw`, `success` (bool), `message` (optional error/status string).

**How it works**
1. **Dimensions**: `n_sessions = len(day.sessions)`, `n_steps = day.n_steps`, `dt = day.dt_hours`, `c = tou.rates_per_kwh`. If `n_sessions == 0` or `n_steps == 0`, return a zero schedule and success.
2. **Variables**: CVXPY variables `p` (shape `(n_sessions, n_steps)`, nonnegative) and `u` (length `n_sessions`, nonnegative). `p[i,t]` = power (kW) to session i at step t; `u[i]` = slack/unmet energy (kWh) for session i.
3. **Objective**: Minimize `∑_t c(t)·(∑_i p[i,t])·dt + penalty_unmet·∑_i u[i]`.
4. **Constraints**:  
   - Availability: for each (i, t) with t outside [arrival_idx, departure_idx), `p[i,t] == 0`; else `p[i,t] <= max_power_kw`.  
   - Site cap: for each t, `∑_i p[i,t] <= site.get_P_max_at_step(t)`.  
   - Energy: for each i, `∑_t p[i,t]*dt + u[i] == sess.energy_kwh`.
5. **Solve**: `cp.Problem(objective, constraints).solve()`. On exception or non-optimal status, return a failed `SolveResult` with message.
6. **Extract**: `schedule = max(p.value, 0)`, `unmet = max(u.value, 0)`. Compute `total_cost_usd` and `peak_load_kw` from the schedule for reporting.

---

## 1.6 Evaluation metrics (`evaluation/metrics/`)

### File: `evaluation/metrics/__init__.py`

**Purpose**  
Provide standard metrics for any schedule: total energy cost, total unmet energy, peak load, % of sessions fully served, and (optionally) % cost reduction versus an uncontrolled (charge-asap) baseline. Used by the Phase A script and will be used by baseline and agent evaluation.

**What it does**
- **`total_cost(schedule, tou, dt_hours)`**  
  - Formula: ∑_t c(t)·(∑_i schedule[i,t])·dt_hours. Returns total cost in $.

- **`total_unmet_kwh(schedule, day, dt_hours)`**  
  - For each session i, delivered = ∑_t schedule[i,t]·dt_hours; unmet = max(0, energy_kwh - delivered). Returns the sum of unmet over all sessions.

- **`peak_load_kw(schedule)`**  
  - Returns max over t of (sum over i of schedule[i,t]).

- **`pct_fully_served(schedule, day, dt_hours)`**  
  - Count of sessions for which delivered ≥ requested (within a small tolerance). Returns 100·count / len(sessions).

- **`charge_asap_schedule(day, site_p_max)`**  
  - Builds an uncontrolled schedule: for each session, from `arrival_idx` to `departure_idx`, charge at `min(max_power_kw, remaining/dt)` until requested energy is met. Returns a schedule array of the same shape. Used only to compute the uncontrolled cost for comparison.

- **`compute_metrics(schedule, day, tou, dt_hours, violation_count=0, uncontrolled_cost_usd=None)`**  
  - Calls the above to fill a **`Metrics`** dataclass: `total_cost_usd`, `total_unmet_kwh`, `peak_load_kw`, `violation_count`, `pct_fully_served`, and (if `uncontrolled_cost_usd` is provided) `cost_reduction_vs_uncontrolled_pct` = 100·(uncontrolled - cost) / uncontrolled.

**How it works**
- All functions assume `schedule` has shape `(n_sessions, n_steps)` with session order matching `day.sessions`. Empty schedules or zero-length days are handled (return 0 or 0.0 as appropriate).

---

## 1.7 Visualization (`visualization/`)

### File: `visualization/plots.py`

**Purpose**  
Produce two kinds of figures for reports and debugging: a schedule heatmap (sessions × time) and a facility load profile (total power vs time). Used by the Phase A script; will be reused for baseline and agent outputs.

**What it does**
- **`plot_schedule(schedule, day, save_path=None)`**  
  - If `schedule` is empty: creates a minimal figure with axes, optionally saves, then closes.  
  - Otherwise: creates a figure and axes, calls `ax.imshow(schedule, aspect="auto", ...)` with colormap `viridis` (rows = sessions, columns = time step; color = power in kW). Adds axis labels and a colorbar. If `save_path` is set, saves the figure (e.g. PNG) and closes it to free memory.

- **`plot_load_profile(schedule, day, save_path=None, title=None)`**  
  - Computes `load_per_t = np.sum(schedule, axis=0)` (total power at each time step). If schedule is empty, uses zeros of length `day.n_steps`.  
  - Plots time step index vs load (line plot). Sets xlabel "Time step", ylabel "Total load (kW)". Optional title; optional save and close.

**How it works**
- Both functions import `matplotlib.pyplot` locally. They do not show the plot interactively; they save to file and close the figure so that batch runs do not accumulate figures.

---

## 1.8 Phase A script (`scripts/run_phase_a.py`)

**Purpose**  
Single entry point to run the full Phase A pipeline from the command line: load sessions from the API, solve, check constraints, compute metrics (including comparison to uncontrolled), print results and any violations, and save schedule and load profile plots.

**What it does**
- **CLI**: `--site` (default `caltech`), `--date` (default yesterday; format YYYY-MM-DD).
- **Environment**: Loads `.env` from project root (for `ACN_DATA_API_TOKEN`). No synthetic data; if the API returns no sessions, the script exits with a clear message.

**How it works (step-by-step)**
1. Parse arguments; resolve `day_date`.
2. Call `load_sessions(site_id, day_date)`. On `ValueError` or `ImportError`, print error and exit.
3. If `len(day.sessions) == 0`, print message suggesting another date and exit.
4. Build `SiteConfig(P_max_kw=50, n_steps=day.n_steps, dt_hours=day.dt_hours)` and `TOUConfig(rates_per_kwh=default_tou_rates(day.n_steps))`.
5. Call `solve(day, site, tou)`. If not `result.success`, print message and exit.
6. Call `check(result.schedule, day, site)`.
7. Compute uncontrolled schedule with `charge_asap_schedule(day, site_p_max)` and its cost with `total_cost(...)`. Call `compute_metrics(..., violation_count=len(check_result.violations), uncontrolled_cost_usd=...)`.
8. Print: Feasible, violations (if any) with kind/session/time/message, then total cost, peak, total unmet, % fully served, % cost reduction vs uncontrolled.
9. If `experiments/` exists, call `plot_schedule` and `plot_load_profile` and save to `experiments/phase_a_schedule.png` and `experiments/phase_a_load.png`.

**Usage**  
From project root with venv active:  
`python -m scripts.run_phase_a --site caltech --date 2019-06-15`

---

## 1.9 Tests (`tests/`)

### File: `tests/test_constraints.py`

**Purpose**  
Unit tests for the constraint checker so that feasible and infeasible schedules are correctly classified and violation types are identified.

**What it does**
- **`test_check_feasible_schedule`**: Builds a small `DaySessions` (2 sessions, 8 steps) and a schedule that satisfies availability, per-charger, site cap, and energy. Asserts `result.feasible` and no violations.
- **`test_check_availability_violation`**: One session; schedule has nonzero power at a time step outside [arrival, departure). Asserts not feasible and at least one violation with `kind == "availability"`.
- **`test_check_per_charger_violation`**: Schedule has power above `max_power_kw` at one step. Asserts violation kind `"per_charger"`.
- **`test_check_site_cap_violation`**: Two sessions; both charge at max in the same window so total power exceeds `P_max`. Asserts violation kind `"site_cap"`.
- **`test_check_energy_violation`**: Schedule delivers zero energy to a session that requested positive energy. Asserts not feasible, positive unmet for that session, and an energy violation.

**How it works**  
Tests construct `Session`, `DaySessions`, and `SiteConfig` by hand and pass a numpy schedule and the checker; they do not call the API or the solver.

---

## 1.10 End-to-end data flow (Phase A)

```
.env (ACN_DATA_API_TOKEN)
        │
        ▼
scripts/run_phase_a.py  ──►  data/loader/loader.py  ──►  DaySessions (list of Session)
        │                              │
        │                              └── raw_session_to_standard() per API item
        │
        ├── config/site.py  ──►  SiteConfig, TOUConfig (default_tou_rates)
        │
        ├── optimization/solver.py  ──►  SolveResult (schedule, cost, unmet, peak)
        │
        ├── constraints/checker.py  ──►  CheckResult (feasible, violations, unmet, peak)
        │
        ├── evaluation/metrics  ──►  charge_asap_schedule(), total_cost(), compute_metrics()
        │
        └── visualization/plots.py  ──►  plot_schedule(), plot_load_profile()  ──►  experiments/*.png
```

---

# Part II — Remaining: Phase B (Baseline + evaluation)

Phase B implements the **direct LLM prompting baseline** and an **evaluation script** that runs it and reports the same metrics as Phase A.

## 2.1 Baseline module (`baseline/`)

### File: `baseline/prompt.py`

| Item | Description |
|------|-------------|
| **Purpose** | Build the single prompt string sent to the LLM so it can output a charging schedule. |
| **Function** | `build_prompt(day, site, tou, instruction=None)` → `str`. |
| **What to implement** | Assemble text that includes: (1) objective (minimize TOU cost), (2) horizon (n_steps, dt_hours), (3) site power cap P_max, (4) a **session table** with columns session_id, arrival_idx, departure_idx, energy_kwh, charger_id, max_power_kw (one row per session, same order as `day.sessions`). Append optional `instruction` (e.g. output format: “One row per session, space-separated power values per time step”). Use a clear, parseable format (e.g. markdown table or CSV-style lines). |
| **Output** | Single string; no API calls. |

### File: `baseline/parse.py`

| Item | Description |
|------|-------------|
| **Purpose** | Convert the LLM’s reply (plain text) into a schedule matrix that the checker and metrics can use. |
| **Function** | `parse_llm_schedule(response_text, day)` → `ParseResult(schedule, success, error_message)`. |
| **What to implement** | Define a format (e.g. “Session 0: p0 p1 p2 …” or CSV rows). Parse numbers from the response into a numpy array of shape `(len(day.sessions), day.n_steps)` (power in kW). On any parse failure, return `ParseResult(schedule=zeros, success=False, error_message="...")`. Handle extra text, newlines, and minor formatting variation. |
| **Output** | `ParseResult` dataclass; schedule order must match `day.sessions`. |

### File: `baseline/run.py`

| Item | Description |
|------|-------------|
| **Purpose** | Single entry point: build prompt, call the LLM, parse response into a schedule. |
| **Function** | `run_baseline(day, site, tou, api_key=None, model="gpt-4o-mini")` → `BaselineResult(schedule, parse_success, raw_response, parse_error)`. |
| **What to implement** | (1) Get `OPENAI_API_KEY` from `api_key` or environment (e.g. after loading `.env`). If missing, return a failed result with a clear parse_error. (2) Call `build_prompt(day, site, tou)`. (3) Call OpenAI API (e.g. `openai` client) with that prompt; read the assistant message. (4) Call `parse_llm_schedule(response_text, day)`. (5) Return `BaselineResult` with the parsed schedule and success/error fields. |
| **Dependencies** | Add `openai` (or chosen client) to `requirements.txt`; document `OPENAI_API_KEY` in `.env.example`. |

### Optional: repair step

If the parsed schedule violates constraints, optionally run one projection/repair (clip to [a_i, d_i), clip to max_power_kw, scale to site cap) and document whether metrics are reported before and/or after repair.

---

## 2.2 Evaluation script for baseline

### File: `scripts/run_baseline.py`

| Item | Description |
|------|-------------|
| **Purpose** | Run the baseline for a given site/date and output the same metrics as Phase A (cost, peak, unmet, % fully served, % cost reduction vs uncontrolled), plus feasibility and violations. |
| **What to implement** | In `main()`: (1) Load `.env` from project root. (2) Parse CLI (`--site`, `--date`, optional `--output`). (3) Call `load_sessions(site_id, day_date)`. (4) Build `SiteConfig` and `TOUConfig` (same as Phase A). (5) Call `run_baseline(day, site, tou)`. (6) Run `check(schedule, day, site)`. (7) Compute uncontrolled schedule and cost; call `compute_metrics(..., violation_count=len(check_result.violations), uncontrolled_cost_usd=...)`. (8) Print or write metrics (e.g. to `experiments/baseline_metrics.json` or CSV). Optionally save schedule or use `--output`. |
| **Reuse** | All metrics and the checker from Phase A; no new metric code. |
| **Reproducibility** | Document in README or script: model name, prompt version, and exact run command (e.g. `python -m scripts.run_baseline --site caltech --date 2019-06-15`). |

---

# Part III — Remaining: Phase C (Agent v1)

Phase C implements the **agentic pipeline** (Plan → Optimize → Validate → Refine → Explain) by wiring existing components and adding thin agent modules and a run script.

## 3.1 Agent modules (`agent/`)

### File: `agent/plan/plan.py`

| Item | Description |
|------|-------------|
| **Purpose** | Turn a user request into a structured plan (day, site, tou, objective) for the optimizer and checker. |
| **Function** | `plan(request, day, site, tou)` → `PlanResult(day, site, tou, objective, raw)`. |
| **What to implement** | For v1: return `PlanResult(day=day, site=site, tou=tou, objective="minimize_cost", raw=None)`. No LLM or parsing required. Later: optionally parse `request` to extract objective or parameters. |

### File: `agent/optimize/call_solver.py`

| Item | Description |
|------|-------------|
| **Purpose** | Call the optimization solver from the agent. |
| **Function** | `optimize(day, site, tou, penalty_unmet=1e6)` → `SolveResult`. |
| **What to implement** | Call `optimization.solver.solve(day, site, tou, penalty_unmet)` and return its result. |

### File: `agent/validate/validate.py`

| Item | Description |
|------|-------------|
| **Purpose** | Run the constraint checker on the agent’s schedule. |
| **Function** | `validate(schedule, day, site)` → `CheckResult`. |
| **What to implement** | Call `constraints.checker.check(schedule, day, site)` and return the result. |

### File: `agent/refine/refine.py`

| Item | Description |
|------|-------------|
| **Purpose** | On solver failure or validation failures, optionally adjust inputs and re-solve. |
| **Function** | `refine(day, site, tou, solve_result, max_retries=1)` → `(DaySessions, SiteConfig, TOUConfig, SolveResult)`. |
| **What to implement** | For v1: return `(day, site, tou, solve_result)` unchanged. Optionally: if `not solve_result.success` and `max_retries > 0`, adjust (e.g. relax bounds) and call the solver again; return the new or same result. |

### File: `agent/explain/explain.py`

| Item | Description |
|------|-------------|
| **Purpose** | Turn numeric results into a short natural-language explanation that uses only computed facts (grounded). |
| **Functions** | `extract_facts(schedule, total_cost_usd, peak_load_kw, total_unmet_kwh, uncontrolled_cost_usd=None)` → `ScheduleFacts`. `generate_explanation(facts, use_llm=False)` → `str`. |
| **What to implement** | **extract_facts**: Build `ScheduleFacts` with the given numbers; if `uncontrolled_cost_usd` is provided, set `cost_reduction_vs_uncontrolled_pct = 100·(uncontrolled - total_cost_usd)/uncontrolled`. **generate_explanation**: For v1 use a template string, e.g. “Total cost $X. Peak load Y kW. Unmet Z kWh. Cost reduction vs uncontrolled: W%.” No LLM required for v1. |

### File: `agent/run.py`

| Item | Description |
|------|-------------|
| **Purpose** | Run the full agent pipeline once: plan → optimize → validate → optionally refine → explain. |
| **Function** | `run_agent(day, site, tou, request="Minimize energy cost for this day.")` → `AgentResult(schedule, total_cost_usd, peak_load_kw, unmet_energy_kwh, feasible, explanation)`. |
| **What to implement** | (1) Call `plan(request, day, site, tou)`; use `plan_result.day`, `.site`, `.tou`. (2) Call `optimize(day, site, tou)`. (3) Call `validate(schedule, day, site)`. (4) If not feasible and max_retries > 0, call `refine(...)` then `optimize` and `validate` again. (5) Compute total cost, peak, total unmet from solver/checker. (6) Optionally compute uncontrolled cost; call `extract_facts` and `generate_explanation`. (7) Return `AgentResult` with schedule, metrics, feasible, and explanation string. |

---

## 3.2 Agent script and visualization

### File: `scripts/run_agent.py`

| Item | Description |
|------|-------------|
| **Purpose** | Run the agent from the command line and optionally save the same plots as Phase A. |
| **What to implement** | (1) Load `.env`. (2) Parse CLI (`--site`, `--date`). (3) Call `load_sessions`, build `SiteConfig` and `TOUConfig` (same as Phase A and run_baseline). (4) Call `agent.run.run_agent(day, site, tou)`. (5) Print explanation and key metrics. (6) Optionally call `plot_schedule` and `plot_load_profile` and save to `experiments/agent_schedule.png` and `experiments/agent_load.png`. |
| **Config** | Use the same site and TOU config as baseline so baseline vs agent comparisons are fair. |

---

## 3.3 Summary for Phase C

- No new optimization or visualization logic: the agent uses the existing solver, checker, and plots.
- Implement the agent modules so that `run_agent(day, site, tou)` returns schedule, metrics, and explanation; then add `run_agent.py` to run it from the CLI and optionally produce plots.

---

# Reference: Midway deliverable checklist

| Deliverable | Status | Notes |
|-------------|--------|--------|
| Data loader, standardized session format, constraint checker | ✅ Done | `data/format/schema.py`, `data/loader/loader.py`, `constraints/checker.py`; loader uses Eve API; checker has violations and tolerance. |
| Prompting baseline implementation and evaluation scripts | 🔲 Phase B | Implement `baseline/prompt.py`, `parse.py`, `run.py`; implement `scripts/run_baseline.py`; reuse Phase A metrics. |
| Agentic pipeline v1 with optimization solver and visualization | ✅ Solver + viz done in Phase A; 🔲 agent wiring | Solver in `optimization/solver.py`; plots in `visualization/plots.py`. Implement agent plan, optimize, validate, refine, explain, run and `scripts/run_agent.py`. |
