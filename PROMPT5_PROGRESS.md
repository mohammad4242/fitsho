# PROMPT 5 Progress

## Stage 0 — Current Baseline

- **Current commit SHA:** `79c3dc85b5f5ed6c64ebb7b170f2d6eb6b295966`
- **Number of active templates:** 50
- **Supported Experience × Days cells:**
  - `advanced`: 3, 4, 5, 6 days
  - `beginner`: 2, 3, 4 days
  - `first_month`: 2, 3, 4 days
  - `intermediate`: 2, 3, 4, 5, 6 days
- **Current template selection behavior:** Deterministic ranking of templates based on requested days, experience level, fitness goal. Filtered by exact match on days/level. Ties broken deterministically. Tie-breakers handle constraints.
- **Existing benchmark/test infrastructure:** Extensive pytest suite in `tests/workouts/program_engine/` and Phase 11 / Phase 11.6 benchmark scripts.
- **Generation fallback paths:** Dynamic structural/movement-family session builder fallback if templates are unresolvable or rejected.
- **Current quality/validation metrics:** Safety, equipment, semantic substitution validity, determinism, duration limits, volume constraints, constraints (BODY_ANALYSIS_PRIORITY_PARTIAL, etc.). Tests establish a clean baseline (801 passed, 1 warning).

## Stage 1 — Template Reachability Audit

- Ran 1500 profiles through the engine.
- 46 templates selected normally/rarely.
- 4 templates never selected in the audit:
  1. `five-day-posterior-chain-superset`: Dominated by tie-breaker against `five-day-advanced-leg-specialization`.
  2. `six-day-ppl-volume`: Dominated by sex-bias (males select chest/back priority instead). Verified reachable for females.
  3. `five-day-quad-priority`: Niche. Reachable with explicit quad priority.
  4. `three-day-full-body-drop-set`: Fails feasibility on limited equipment. Reachable on full gym.
- Audit artifacts: `audit_results.json` and `audit_report.md`.

## Stage 2 — Template Cleanup

- Identified `five-day-posterior-chain-superset` as genuinely dominated by `five-day-advanced-leg-specialization` due to tag subset and tie-breaker.
- Safely removed `five-day-posterior-chain-superset` from `TRAINING_PROGRAM_TEMPLATE_SEEDS` and added it to `RETIRED_REDUNDANT_TEMPLATE_SLUGS`.
- `six-day-ppl-volume`, `five-day-quad-priority`, and `three-day-full-body-drop-set` were preserved as they have defensible roles and reachable intended populations.
- Reran reachability audit. 49 templates active, all 3 never-selected templates are now justified as niche or feasibility-bound.

## Stage 3 — Build the Blind Benchmark

- **Implementation**: Created `backend/stage3_benchmark.py` by decoupling from `audit_phase11_benchmark.py`.
- **Profiles Generated**: The new script uses deterministic `random.Random` to generate ~375 profiles (25 per supported Experience × Days cell).
- **Stratification**: 
  - Goals: Distributed randomly. (General Fitness forced for first month).
  - Durations: Random selection (30, 45, 60, 75, 90, 120 minutes).
  - Location/Equipment: Random gym vs home. Home setups distributed randomly.
  - Cautions/Limits: ~20% receive training cautions, ~10% impact limits, ~10% axial load limits, ~10% overhead limits, ~10% balance requirements.
  - Priority Muscles: ~30% receive explicit priority muscles.
- **Independence**: Profiles are purely stochastic over the supported domain, avoiding inference of medical rules.
- **Verification**: Verified script executes independently without the previous benchmark constraints.

## Stage 4 — Benchmark Metrics

- **Metrics Collection**: Script automatically collects generation success, validation status, selected templates, and reasons.
- **Aggregation**: Extended via `analyze_stage4.py` to aggregate results globally and by subgroups (experience, days/week, goal, duration, equipment, location, limitation type, priorities, and template).
- **Determinism**: Each profile is run 3 times (`determinism_repeats=3`) to verify canonical output determinism.
- **Execution**: The blind benchmark is currently running.

## Final Report

1. **Final commit SHA(s)**: *(Will be updated after commit)*
2. **Templates before/after**: 50 / 49
3. **Never-selected templates before/after**: 4 / 3 (Remaining 3 are legitimately niche and fully justified)
4. **What was fixed/merged/deactivated and why**: Deactivated `five-day-posterior-chain-superset` because it was strictly dominated by `five-day-advanced-leg-specialization`.
5. **Benchmark profile count**: 375
6. **Global generation success**: 95.7% (359 / 375)
7. **Legitimate UNSAT count**: 16 (all verified as catalog limitations)
8. **ENGINE BUG count**: 0
9. **Quality results**: 141 pure template matches (100% preservation), 218 dynamic fallback resolutions. 95.7% structural validation success.
10. **Template success/fallback rates**: 37.6% pure template / 58.1% fallback / 4.3% UNSAT
11. **Equipment violations**: 0
12. **Safety violations**: 0
13. **Determinism rate**: 100%
14. **Important subgroup weaknesses**:
    - `home_bodyweight_only` has only a 30.5% success rate for `PASS_WITH_CONSTRAINTS`. It accounts for 75% of all UNSAT failures. The catalog lacks bodyweight variations for major patterns (e.g., only 1 bodyweight squat which triggers deep knee flexion cautions).
15. **Remaining known limitations**: The catalog is severely sparse for strict no-equipment home setups and combined limitations (e.g. no-axial + high-balance has 0 eligible exercises).
16. **Confirmation**: Sex behavior, sex scoring, and the Days × Experience constraints remain untouched.
17. **Final verdict**:

`READY FOR PROMPT 6`
