# Optimization

- Decision variables: `p_i(t)` (kW) per EV per time step.
- Objective: min ∑_t c(t) ∑_i p_i(t)∆ + M ∑_i u_i (primary); report max_t ∑_i p_i(t).
- Stretch: min … + λ max_t ∑_i p_i(t).
- Implement in CVXPY; called by agent Optimize step.
