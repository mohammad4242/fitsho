# PROMPT 5 — Template Audit + Blind Benchmark

## Mission

Audit and clean the workout-template system, then run a large blind benchmark to determine whether the Fitsho program engine is genuinely stable and high-quality across diverse supported users.

Do not optimize the engine to “pass the benchmark”.
Find real problems, fix only justified defects, and report failures honestly.

---

## Execution Protocol

Start from CURRENT `main` and inspect the repository before making changes.

For every stage:

1. Inspect current implementation/data/tests.
2. Establish evidence before editing.
3. Make the smallest justified change.
4. Run focused tests.
5. Run relevant broader tests.
6. Review the diff for unrelated changes.
7. Commit.
8. Push.
9. Verify the remote commit.
10. Update `PROMPT5_PROGRESS.md`.
11. Continue automatically to the next stage.

Do not stop between stages.

Ask me only if a genuinely blocking ambiguity remains after inspecting the repository.
Otherwise continue autonomously until the entire workflow is complete.

---

# Global Invariants

Do NOT change:

- sex scoring, sex bias, `_sex_score`, sex constants, sex reason codes, or sex behavior
- the supported Days × Experience matrix
- unrelated duration rules
- unrelated volume rules
- recovery rules
- supplemental-muscle architecture
- cardio architecture
- existing safety constraints
- equipment safety requirements
- Unified Substitution Engine architecture unless a benchmark exposes a real defect

Never weaken validation or safety merely to increase benchmark success.

Do not artificially force templates to be selected.

---

# Stage 0 — Current Baseline

Inspect CURRENT main.

Record:

- current commit SHA
- number of active templates
- supported Experience × Days cells
- current template selection behavior
- existing benchmark/test infrastructure
- generation fallback paths
- current quality/validation metrics

Run the current relevant program-engine tests and establish a clean baseline.

Do not assume old template counts or old never-selected counts are still correct.

---

# Stage 1 — Template Reachability Audit

Run a deterministic audit of every active template.

For each template determine:

- selected normally
- selected rarely
- never selected
- infeasible
- dominated by another template
- duplicated/redundant
- metadata mismatch
- goal mismatch
- experience/day mismatch
- exercise/catalog feasibility problem
- structurally valid but legitimately niche

Trace WHY each never/rarely selected template behaves that way.

Produce a machine-readable audit plus concise human-readable report.

Do not change templates yet.

---

# Stage 2 — Template Cleanup

Using Stage 1 evidence, fix only clearly justified template defects.

Allowed actions when supported by evidence:

- correct wrong metadata
- correct template structure/reference metadata
- merge genuine duplicates
- deactivate/remove genuinely dominated or useless templates
- preserve legitimate niche templates even if rarely selected

Do NOT manipulate template scores or selection logic just to make every template appear in the benchmark.

After every meaningful change, rerun the reachability audit.

Goal:
Every remaining active template must have a defensible role and reachable intended population, or a clearly documented reason for being intentionally niche.

---

# Stage 3 — Build the Blind Benchmark

Create a deterministic blind benchmark with approximately 300–500 diverse profiles.

Profiles must be generated independently of the expected engine output.

Stratify across the supported product space, including:

- all supported Experience × Days combinations
- primary goals
- 30 / 45 / 60 / 75 / 90 / 120 minute sessions
- gym and home training
- varied equipment inventories
- bodyweight-only / dumbbells / bands / bench / pull-up bar combinations where relevant
- priority muscles
- no priority muscles
- explicit computable limitations/constraints
- lower-back / knee / shoulder / wrist / balance / ROM constraints where supported
- different training ages
- realistic profile variation

Do not infer medical rules from free-text limitations.

Use deterministic seeds and make the benchmark reproducible.

---

# Stage 4 — Benchmark Metrics

For every profile capture at minimum:

- generation success / UNSAT
- validation status
- quality status
- selected template
- template success vs dynamic fallback
- reason for template rejection/fallback
- exercise count
- duration fit
- weekly volume validity
- session sequencing validity
- recovery validity
- equipment violations
- safety/constraint violations
- duplicate/redundancy violations
- substitution metrics
- movement-family fallback usage
- template structure preservation
- determinism

Aggregate results globally AND by subgroup:

- experience
- days/week
- goal
- session duration
- equipment setup
- home vs gym
- limitation type
- priority-muscle state
- template

Run every profile at least twice for determinism verification.

---

# Stage 5 — Analyze Failures

Classify every meaningful failure into:

- legitimate UNSAT
- catalog limitation
- template defect
- substitution defect
- selection/ranking defect
- duration/volume interaction
- validation issue
- ENGINE BUG
- quality issue

Do not hide legitimate UNSAT.

Do not repair unrelated architecture unless the benchmark proves a real defect.

For every proposed code change:
identify the failing subgroup/profile first, explain the root cause, then make the smallest safe fix.

After each fix:
rerun focused regressions before rerunning the full benchmark.

---

# Stage 6 — Final Blind Benchmark

After cleanup/fixes, rerun the full benchmark from scratch.

Required hard acceptance:

- 0 equipment violations
- 0 safety/constraint violations
- 0 unexplained semantic substitution violations
- 100% determinism
- 0 ENGINE BUG
- no regression in supported Days × Experience behavior
- no benchmark-specific hacks
- no artificial template-selection forcing

Every remaining UNSAT must have an explainable legitimate constraint/catalog cause.

Template selection should be diverse where appropriate, but template diversity itself is NOT a pass criterion.

Quality must be evaluated by program correctness, not by forcing every template to win.

---

# Stage 7 — Final Review

Perform a final architecture/code review.

Confirm:

- active templates are justified
- dead/dominated templates are fixed, removed, or explicitly justified
- template selection remains deterministic
- Unified Substitution Engine is still the authoritative replacement system
- safety/equipment eligibility remains hard
- fallback behavior remains intentional
- benchmark is reproducible
- no unrelated behavioral regressions were introduced

Run:

- focused template tests
- full program-engine tests
- full backend pytest
- affected mypy
- Ruff on changed files
- `git diff --check`

Review the final diff manually.

---

# Final Report

Return a concise report containing:

1. final commit SHA(s)
2. templates before/after
3. never-selected templates before/after
4. what was fixed/merged/deactivated and why
5. benchmark profile count
6. global generation success
7. legitimate UNSAT count
8. ENGINE BUG count
9. quality results
10. template success/fallback rates
11. equipment violations
12. safety violations
13. determinism rate
14. important subgroup weaknesses
15. remaining known limitations
16. confirmation that sex behavior and Days × Experience were untouched
17. final verdict:

`READY FOR PROMPT 6`

or

`NOT READY FOR PROMPT 6`

If NOT READY, clearly state the exact blockers.

Do not restate this plan before starting.
Inspect CURRENT main and begin Stage 0 immediately.
