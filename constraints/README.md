# Constraint checker

- **Availability**: `p_i(t) = 0` for `t ∉ [a_i, d_i)`.
- **Per-charger limits**: `0 ≤ p_i(t) ≤ p̄_i`.
- **Site power cap**: `∑_i p_i(t) ≤ P_max(t)`.
- **Energy delivery**: `∑_t p_i(t)∆ + u_i = E_i`, `u_i ≥ 0`.
- Used by both baseline (optional repair) and agent (Validate step).
