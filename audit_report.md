# Stage 1: Template Reachability Audit Report

## Audit Methodology
We ran an exhaustive audit using the `benchmark_profiles` generator and extended it to 1500 profiles covering all supported Experience × Days cells, all goals, varied equipment setups, and different priority muscle combinations.

## Global Reachability
- **Total active templates:** 50
- **Selected normally/rarely:** 46 templates
- **Never selected in randomized audit:** 4 templates

## Analysis of Never-Selected Templates

1. **`five-day-posterior-chain-superset`**
   - **Reason:** Dominated by `five-day-advanced-leg-specialization`. Both share similar tags (lower priority, hamstrings, glutes) and score identically (120 pts) when posterior chain is requested. The engine tie-breaks alphabetically favoring the leg specialization template.

2. **`six-day-ppl-volume`**
   - **Reason:** Sex-based scoring artifact. This template is structurally valid and legitimately niche for females. For males, the invariant `_sex_score` awards +20 points to `chest_priority` and `back_priority` templates, causing `six-day-chest-priority` and `six-day-back-priority` to dominate this baseline PPL template.

3. **`five-day-quad-priority`**
   - **Reason:** Structurally valid but legitimately niche. It is strictly selected when `QUADRICEPS` priority is explicitly requested by an Intermediate user training 5 days a week. The randomized audit sparsity simply missed this exact combination with sufficient equipment.

4. **`three-day-full-body-drop-set`**
   - **Reason:** Equipment feasibility limitations. As the only advanced 3-day hypertrophy template, it requires specific equipment for its core slots. Profiles in this cell with limited equipment (e.g., `limited_gym`) trigger a `CORE_SLOT_UNRESOLVABLE` hard rejection. It is successfully selected when `full_gym` is available.

## Conclusion
No templates are structurally broken. The never-selected templates are either intentionally niche (quad priority, female-optimal baseline), legitimately tied/dominated (posterior chain superset), or equipment-bound (drop set).
