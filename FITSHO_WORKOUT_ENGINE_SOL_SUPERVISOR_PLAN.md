# FITSHO Workout Engine Repair — Sol Architect/Supervisor Workflow

## Mission

You are the **architect and technical supervisor**, not the primary implementer.

Your main objective is to complete the workout-engine repair while **materially reducing Sol token/usage consumption**.

Use Sol for:
- architecture,
- task decomposition,
- review,
- integration decisions,
- verification,
- final acceptance.

Delegate implementation work to **Luna agents** in small, independent, narrowly scoped tasks.

Do not spend Sol context reading large unrelated parts of the repository. Read only the minimum files needed to make architectural decisions or review Luna's work.

Continue until the entire repair is complete. Ask the user only if there is a **genuine blocking ambiguity** that cannot be resolved from:
1. `AGENTS.md`,
2. the current codebase,
3. existing rulesets,
4. existing tests,
5. this specification.

---

## Required Workflow

1. Read `AGENTS.md`.
2. Read this file completely.
3. Inspect only the current workout-engine files/tests needed to understand the current state.
4. Build a **short execution map**.
5. Split the work into small Luna tasks.
6. Give each task to a Luna agent.
7. After every Luna task:
   - inspect its diff,
   - inspect/update tests,
   - run the smallest relevant verification,
   - reject incomplete or architecture-breaking fixes.
8. If a task is incomplete or introduces regression, create a new corrective Luna task.
9. Repeat until all acceptance criteria in this document are satisfied.
10. Run the full final verification.
11. Re-run the targeted profile regressions and the second 10-profile batch.
12. Do not report completion unless the final evidence is actually green.

### Delegation rule

Prefer one Luna task per narrow concern, for example:

- session-size/duration policy,
- semantic duplicate detection,
- opener ordering,
- 4-day upper-priority split,
- structured injury/limitation input,
- wrist-safe generation fallback,
- recovery spacing,
- lower-back safety metadata,
- final coach-quality gate,
- regression harness/report correctness.

Do not give one Luna agent the entire engine repair as one giant task.

---

# Core Product Goal

The Fitsho engine must produce a program that is not merely schema-valid or safety-valid.

It must also look like a **coherent program written by a competent trainer**.

A program must not be accepted only because:
- all requested days exist,
- every exercise is technically allowed,
- validation has no low-level exception.

The final program must also satisfy:
- sensible session size,
- sensible session duration,
- meaningful muscle coverage,
- sensible exercise ordering,
- no pointless exercise-family duplication,
- sensible weekly split structure,
- realistic recovery spacing,
- user priorities,
- safety constraints,
- equipment constraints,
- deterministic behavior.

---

# Critical Bugs to Fix

## 1. Session size and duration are currently unreliable

The engine currently produces both severe underfill and severe overfill.

Observed examples from the second 10-profile report:

- 45-minute session with only **2 exercises / ~19 minutes**.
- 45-minute sessions with only **3 exercises / ~34 minutes**.
- 75-minute training day with only **3 exercises / ~22 minutes**.
- 60-minute session with **10 exercises / ~80 minutes**.

These must not be accepted as normal successful programs.

### User-approved session-size targets

These are **quality targets**, not a requirement that every session have exactly the same number of exercises.

Use actual duration, sets, rest, exercise type, level, goal, safety, and available catalog capacity.

Preferred targets:

- **30 min:** usually 3–4 meaningful exercises.
- **45 min:** usually around 5 meaningful exercises.
- **60 min:** usually around 6 meaningful exercises.
- **75 min:** usually 7–8 meaningful exercises.
- **90 min:** usually 8–9 meaningful exercises.

Do not force exactly 5 exercises for every duration.

A constrained session may legitimately be smaller, but only if:
- the limitation is real,
- the engine cannot safely fill more useful work,
- the reason is explicit in the trace/quality result.

A longer session must not become a junk-volume dump just to fill time.

### Required behavior

The planner must combine:
- duration policy,
- useful workload,
- session capacity,
- minimum useful exercise count,
- maximum useful exercise count,
- muscle-volume limits,
- recovery,
- safety.

A session that is grossly underfilled or overfilled must be:
1. repaired, or
2. explicitly marked constrained/unsatisfied when safe useful work cannot be added.

It must not silently pass as an optimized program.

### Important ambiguity rule

Do **not** silently invent or change:
- maximum exercises per session,
- maximum direct sets per muscle per session,
- hard weekly set caps.

First inspect the existing ruleset and tests.

If the existing per-muscle daily set cap or session exercise cap fundamentally conflicts with these duration targets and there is no clearly correct architecture-consistent value, this is a valid blocking ambiguity: **ask the user** before changing that standard.

---

## 2. Semantic duplicates / redundant exercise families are still leaking through

The engine must prevent meaningless same-session duplicates such as:

- Barbell Squat + generic Squat,
- Dumbbell Squat + Bodyweight Squat when they serve the same programming role,
- Deep Push-Up + Push-Up in the same ordinary chest session,
- multiple near-identical push-up variants in one session,
- RDL + a near-identical stiff-leg deadlift variation when the role is effectively the same.

Do not solve this with display-name string matching.

Use canonical exercise semantics and/or a dedicated curated family/role layer.

Relevant signals may include:
- movement pattern,
- primary muscle,
- secondary muscles,
- muscle focus,
- body position,
- laterality,
- substitution group,
- equipment/load characteristics,
- explicit programming family/role metadata.

### Preserve meaningful distinctions

Do not overcorrect.

These may be valid together when they have genuinely different roles:
- Squat + Lunge,
- Squat + Hip Hinge,
- Flat Press + Incline Press,
- Compound press + isolation fly,
- primary hinge + hip extension,
- distinct unilateral/bilateral work when intentionally programmed.

### Final invariant

The final validator/coach-quality gate must catch semantic redundancy even if it was introduced by:
- template adaptation,
- volume repair,
- duration repair,
- fallback construction,
- substitutions.

A template must **not** automatically override this rule merely because a duplicate slot existed in the template.

If a template contains redundant roles, repair or reject that template construction unless the distinction is genuinely meaningful.

---

## 3. Explicit opener / primer ordering rules

The previous generic `PRIMARY_WORKING_COMPOUND` approach is too broad.

The user's intended behavior is explicit:

### Chest day
If a **push-up-family** exercise is selected for a session that meaningfully trains chest, that push-up should be the **first working exercise**.

Do not select multiple ordinary push-up variants in the same session just to satisfy this.

### Back day
If a **pull-up-family** exercise is selected for a session that meaningfully trains back/lats, that pull-up should be the **first working exercise**.

### Leg day
If the session contains both:
- a **leg-extension primer** (for example machine/band knee extension), and
- a **squat-family** exercise,

then the leg-extension primer should appear **before the squat**.

The purpose is to use it as an opener/primer before the squat.

Do not apply this rule if the leg-extension movement is contraindicated for the user's knee/safety constraints.

### Architecture requirement

Implement these as semantic programming roles/families, not brittle checks against Persian or English display names.

For example, an architecture may define concepts equivalent to:
- `PUSH_UP_FAMILY`,
- `PULL_UP_FAMILY`,
- `LEG_EXTENSION_PRIMER`,
- `SQUAT_FAMILY`,
- `SESSION_OPENER`.

Sol should choose the smallest architecture-consistent implementation after inspecting current metadata.

Do not mark every upper-body compound as an opener.

---

## 4. Four-day upper-body priority split must work

The earlier issue remains a required regression:

For a 4-day user whose explicit priorities are strongly upper-body, for example:
- chest,
- back/lats,
- shoulders,

the engine must have a real candidate topology equivalent to:

- Upper
- Lower
- Upper
- Upper specialization

or another clearly justified **3 upper / 1 lower** structure.

The priority-scoring layer cannot solve this if the split topology itself does not exist.

### Requirements

- The topology must exist in dynamic generation.
- Template selection must not silently defeat the topology when the explicit priorities strongly support it.
- Recovery spacing must still be valid.
- It must preserve 4 requested training days.
- The three upper sessions must not be placed on unsafe consecutive calendar days when recovery exposure says they need separation.

Add/retain a regression test based on the original upper-priority 4-day profile.

---

## 5. Wrist injury / structured caution must adapt instead of failing unnecessarily

Original regression:

A home/bodyweight user with structured wrist caution may have no safe normal push candidate.

The engine should not automatically fail if a useful safe program can still be created.

### Required behavior

When a required pattern is unavailable specifically because a **structured safety restriction** removed the candidates:

- never bypass the safety restriction,
- never select a wrist-loading exercise anyway,
- safely relax that required slot when justified,
- rebalance useful volume toward safe lower-body/core/other available work,
- preserve the requested number of resistance-training days when feasible,
- expose a clear reason code.

If the catalog truly cannot create enough safe useful work, fail honestly.

Do not generate junk filler merely to force success.

---

## 6. Injury/limitation input must be structured, not arbitrary free text

Arbitrary injury prose must not be converted into unstable/uncomputable generation constraints.

### Product behavior

New user input for workout safety/limitations must be **selection-based / structured**.

Do not allow arbitrary free-text injury text to become a hidden generation input.

Existing legacy database text may be preserved for history/display if needed, but it must not be transformed into an unstable `ProgramGenerationRequest` limitation that causes random generation rejection.

Do not add NLP keyword parsing as a shortcut.

### Critical report inconsistency to fix

The second 10-profile report is internally inconsistent around the legacy free-text injury case:
- the summary describes a professional-review rejection,
- while the detailed profile contains a generated program / successful result.

The regression/report pipeline must have one authoritative outcome.

The final report must never say:
- "rejected" in summary while showing a generated successful program in detail,
- or "10 optimized successes" while also claiming one of the ten was rejected.

Fix the harness/report path if needed, not only the engine.

---

## 7. Recovery must account for real direct and indirect muscle exposure

The recovery system must continue to use actual scheduled weekdays and actual muscle exposure.

Do not replace it with simplistic focus-string rules.

### Required behavior

- Same muscle needs realistic recovery.
- Direct and secondary exposure both matter.
- Week-boundary spacing matters.
- Upper/lower layouts should alternate when the topology permits it.
- For 4/5/6-day programs, heavy chest exposure and meaningful shoulder exposure should not be scheduled in a way that violates shoulder recovery.
- Chest pressing should contribute secondary shoulder/triceps exposure when metadata supports it.
- Light accessory exposure may still be allowed on consecutive days if the ruleset classifies it as light.

If the requested split cannot satisfy recovery on the default weekdays, first attempt weekday repair.

Do not reduce the requested training-day count as a hidden fallback.

---

## 8. Lower-back safety metadata must be reliable

The original lower-back regression must remain fixed.

Unsupported bent-over rows, heavy axial loading, or similar lower-back-demanding movements must not pass simply because their explicit caution tag is missing.

Audit:
- axial loading inference,
- body position,
- supported vs unsupported row semantics,
- caution derivation,
- actual exercise metadata.

Prefer metadata/semantic fixes over raw exercise-name checks.

Supported/seated/chest-supported alternatives should remain available when safe.

---

## 9. Full-body and mixed sessions must cover what they claim to cover

A session or weekly plan must not be labeled balanced/full-body while silently omitting a major required area without explanation.

Example:
A 2-day home/bodyweight program should not be described as balanced full-body if there is effectively no back/pull training unless:
- no safe/equipment-valid pull option exists,
- and that limitation is explicitly reported.

### Required behavior

Validate:
- major movement-pattern coverage,
- major muscle coverage,
- requested priorities,
- weekly balance.

Do not add unsafe or equipment-invalid exercises just to satisfy coverage.

If true catalog/equipment limitations make balanced coverage impossible, expose the constraint honestly.

---

## 10. Weekly split distribution must be coherent

Do not allow a weekly plan where:
- one day has 2 exercises,
- another day has 10,
- one nominal training day contains only two calf exercises plus abs,
- while useful work could have been distributed more coherently across the week.

The planner should rebalance sessions before accepting the final plan.

### Quality expectation

Each requested resistance-training day should represent a meaningful session unless a real constraint prevents it.

A 5-day plan should not contain a vestigial 20-minute "day" merely to satisfy the number 5.

Use:
- split topology,
- weekly volume,
- session duration,
- recovery,
- priorities

together when distributing work.

---

## 11. Final Coach Quality Gate

Add or strengthen a final **program-level quality gate** after all construction/repair stages.

This gate must review the final weekly program, not only isolated low-level constraints.

It should reject or trigger repair for at least:

- gross session underfill,
- gross session overfill,
- invalid duration,
- semantic duplicate families,
- opener-order violations,
- missing meaningful weekly coverage,
- incoherent day distribution,
- recovery violation,
- unavailable equipment,
- blocked caution/safety violation,
- requested day-count mismatch,
- priority topology failure when a supported topology is feasible.

Do not create a giant list of magic constants inside the validator.

Use ruleset-owned thresholds and reusable semantic policies.

The same final invariants must apply to:
- dynamic generation,
- template generation,
- fallback construction,
- repaired programs.

---

# Second 10-Profile Batch — Required Regression Evidence

Use the second report as regression evidence.

Do not merely check "program generated successfully".

The new regression must check actual coach-quality invariants.

At minimum, cover these failures:

### Batch2 User 2
Observed:
- chest day contains `Deep Push-Up` + another push-up in the same session,
- neither follows the intended single-opener rule,
- leg day contains two squat-family movements and leg extension after them.

Required:
- at most one ordinary push-up-family working variant in that chest session,
- if selected, it is the first working exercise,
- no meaningless duplicate squat family,
- if leg extension + squat both exist and safe, leg extension precedes squat.

### Batch2 User 3
Observed strength leg day contains:
- Barbell Squat,
- Dumbbell Squat,
- multiple closely related hinge/deadlift roles.

Required:
- preserve strength specificity,
- remove redundant same-role work,
- keep genuinely distinct squat / hinge / lunge roles,
- no semantic duplicate leakage.

### Batch2 User 4
Observed:
- 60-minute session,
- 10 exercises,
- ~80-minute estimate.

Required:
- repair to a coherent 60-minute session,
- preferred session size around 6 useful movements unless a justified exception exists.

### Batch2 User 5
Observed:
- 45-minute days with only 3 or 4 exercises and ~33–34 minutes.

Required:
- fill useful session capacity when safe useful work exists,
- do not accept avoidable underfill.

### Batch2 User 6
Observed:
- multiple push-up-family variants in one session,
- questionable "balanced" coverage.

Required:
- remove redundant push-up family,
- verify actual full-body weekly coverage,
- if pull work is impossible due true equipment/catalog limitations, report the constraint instead of pretending coverage is complete.

### Batch2 User 8
Observed:
- 75-minute plan contains a fifth day of only 3 exercises / ~22 minutes.

Required:
- no vestigial training day when useful work can be redistributed,
- 75-minute sessions should normally support roughly 7–8 useful movements when compatible with volume/recovery/safety.

### Batch2 User 9
Observed:
- `Deep Push-Up` + another push-up in one chest session.

Required:
- semantic duplicate family prevention,
- single push-up opener rule.

### Batch2 User 10
Observed:
- 45-minute day with only 2 exercises / ~19 minutes,
- report summary/detail safety outcome inconsistency.

Required:
- no avoidable 2-exercise training day,
- one authoritative safety/generation outcome across engine, tests, and report.

---

# Original Regression Requirements — Must Not Be Lost

Do not focus only on Batch2.

The following earlier requirements are still mandatory:

1. Push-up and pull-up opener behavior.
2. Real 4-day 3-upper/1-lower option for strong upper priorities.
3. No Barbell Squat + generic Squat same-session redundancy.
4. Structured wrist caution should safely adapt rather than fail when safe useful alternatives exist.
5. Limitation/injury generation input should be structured/selection-only.
6. Same-muscle recovery must be enforced.
7. Chest/shoulder indirect recovery must be accounted for.
8. Requested training-day count must be preserved when feasible.
9. Lower-back loading semantics must protect lower-back caution profiles.
10. Session duration must respect the official duration policy.
11. Templates and dynamic generation must obey the same final invariants.
12. Determinism must be preserved.
13. No unavailable equipment may be selected.
14. No safety rule may be weakened merely to improve generation success.

---

# Testing Strategy

Sol must delegate focused test work to Luna agents.

## Rule: reproduce before trusting a fix

For each major bug:
1. create or identify a regression that demonstrates the bad behavior,
2. verify the test would fail against the bad behavior,
3. implement the repair,
4. verify the regression passes,
5. run neighboring tests.

Do not accept tests that only assert:
- `program is not None`,
- `is_success == True`,
- day count only.

Tests must assert the actual quality invariant.

Examples:
- exercise count / duration target,
- semantic family uniqueness,
- opener position,
- split topology,
- safe caution filtering,
- weekly coverage,
- recovery,
- report consistency.

---

# Suggested Luna Task Decomposition

Sol may adjust the exact order after inspecting HEAD, but keep tasks small.

### Luna Task A — Baseline and failing regressions
- Reproduce the Batch2 failures as targeted tests.
- Do not implement broad fixes yet.
- Return failing tests and root-cause locations.

### Luna Task B — Session capacity and duration
- Fix avoidable 2/3-exercise underfill.
- Fix 10-exercise / 80-minute overfill.
- Integrate user-approved duration-to-session-size quality targets.
- Preserve ruleset ownership of thresholds.

### Luna Task C — Semantic exercise-family policy
- Strengthen near-equivalent detection.
- Prevent push-up-family duplicates.
- Prevent squat-family duplicates.
- Prevent other same-role duplicates without blocking meaningful variation.
- Cover dynamic, template, repair, fallback paths.

### Luna Task D — Opener/primer ordering
- Push-up first on chest sessions when selected.
- Pull-up first on back sessions when selected.
- Leg-extension primer before squat when both selected and safe.
- Do not broadly elevate every compound.

### Luna Task E — Split and priority topology
- Verify/fix 4-day 3U/1L upper specialization.
- Ensure templates cannot silently override explicit upper priority.

### Luna Task F — Safety adaptations
- Wrist caution safe relaxation/rebalance.
- Structured limitation input only.
- Legacy free-text behavior.
- Lower-back metadata/axial loading.

### Luna Task G — Recovery
- Direct + secondary exposure.
- Chest/shoulder adjacency.
- Week boundary.
- Weekday repair.
- No hidden day-count reduction.

### Luna Task H — Weekly balance and full-body coverage
- Fix vestigial days.
- Rebalance weekly work.
- Validate claimed full-body/balanced coverage.

### Luna Task I — Final coach-quality gate
- Centralize final invariants.
- Apply to dynamic/template/fallback/repair output.
- Make reasons observable.

### Luna Task J — Harness/report integrity
- Ensure the 10-profile runner uses the production generation/validation path.
- Ensure report summary equals detailed outcomes.
- Regenerate Batch2 report after fixes if the repo contains the report pipeline.

### Luna Task K — Full verification
- Backend tests/checks.
- Frontend tests/checks if affected.
- Re-run original regressions.
- Re-run Batch2 profile regression.
- Review final diff.

---

# Sol Review Checklist After Each Luna Task

Before accepting a Luna task, Sol must check:

- Did it solve the intended root cause or just special-case the sample?
- Did it hard-code exercise display names?
- Did it weaken safety?
- Did it reduce requested training days?
- Did it create new magic constants outside the ruleset?
- Does the behavior apply to both template and dynamic paths where relevant?
- Is the regression test meaningful?
- Could the fix create junk volume just to fill duration?
- Could the fix eliminate legitimate exercise variety?
- Did it alter unrelated features?

If any answer is bad, create a corrective Luna task.

---

# Final Verification

Read commands from `AGENTS.md` first and use them as authoritative.

At minimum, when applicable, run the repository's full checks equivalent to:

## Backend

```bash
cd backend
uv sync
ruff check
ruff format --check
mypy
pytest
```

## Frontend

```bash
cd frontend
npm install
npm run lint
npm run test
npm run build
```

If the frontend was not changed, Sol may avoid unnecessary repeated frontend context during development, but the final verification should follow project policy from `AGENTS.md`.

---

# Final Acceptance Criteria

Do not declare completion until all of these are true:

- No avoidable 2-exercise / 19-minute requested training day.
- No avoidable 3-exercise / ~22-minute day inside a 75-minute plan.
- No 10-exercise / 80-minute session for a 60-minute request.
- 60-minute sessions normally center around ~6 useful movements.
- 75-minute sessions normally support ~7–8 useful movements.
- 90-minute sessions normally support ~8–9 useful movements.
- Session-size targets remain quality-aware, not rigid exact counts.
- No meaningless push-up-family duplication in one session.
- No meaningless squat-family duplication in one session.
- No other obvious near-equivalent duplication.
- If push-up is selected on a chest session, it is the first working exercise.
- If pull-up is selected on a back session, it is the first working exercise.
- If safe leg extension + squat are both selected on a leg session, leg extension precedes squat.
- Strong upper priorities can produce a real 3U/1L four-day topology.
- Wrist caution can safely adapt when enough safe useful work exists.
- Free-text legacy injury text does not become an unstable generation constraint.
- Structured safety cautions remain fail-closed.
- Lower-back caution filters or downgrades meaningful lower-back loading.
- Recovery uses direct + secondary exposure.
- Chest/shoulder scheduling respects recovery.
- Week-boundary recovery is valid.
- Requested resistance day count is preserved when feasible.
- Balanced/full-body plans have meaningful actual coverage or an explicit constraint reason.
- No vestigial day exists merely to satisfy day count when useful work can be redistributed.
- Dynamic and template paths obey the same final coach-quality gate.
- The 10-profile report summary matches its detailed outcomes.
- Original regressions remain green.
- Batch2 regressions are green.
- Full backend verification is green.
- Frontend verification is green if required by project policy/changes.
- No unrelated regression is introduced.

---

# Non-Negotiable Engineering Constraints

- Preserve determinism.
- Preserve safety-first behavior.
- Do not bypass eligibility.
- Do not select unavailable equipment.
- Do not silently reduce requested day count.
- Do not hard-code user names/profile IDs.
- Avoid raw exercise-name matching for engine logic.
- Prefer semantic metadata and ruleset-owned policy.
- Do not weaken safety to make tests pass.
- Do not add junk volume only to hit time.
- Do not globally ban legitimate variation because one duplicate example exists.
- Preserve explainability through stable reason codes/decision trace.
- Keep changes scoped to workout generation and directly related profile/report paths.
- Preserve unrelated local/uncommitted work.

---

# Token / Usage Discipline for Sol

This workflow intentionally minimizes Sol usage.

Sol should:

- read only relevant files,
- avoid restating long code,
- avoid verbose explanations,
- delegate implementation to Luna,
- request concise Luna summaries containing:
  - files changed,
  - reason,
  - tests added,
  - commands run,
  - failures remaining.
- review diffs instead of re-reading whole files when possible,
- reuse existing architecture/tests instead of redesigning unrelated subsystems.

Sol should not perform the implementation itself unless a very small integration edit is genuinely more efficient than delegation.

---

# When Sol Is Allowed to Ask the User

Ask only for a real architectural/product ambiguity.

The main anticipated example is:

> Existing hard limits for maximum exercises per session or maximum direct sets per muscle per day conflict with the desired 60/75/90-minute session capacity, and the correct standard cannot be determined from the ruleset, tests, or existing product requirements.

If that happens:
- show the exact existing limit,
- show why it blocks the target,
- ask one concise question.

Otherwise continue autonomously.

---

# Required Final Report From Sol

Keep the final response concise and evidence-based.

Report:

1. Root causes fixed.
2. Luna tasks completed.
3. Important files changed.
4. Original regressions status.
5. Batch2 regression status.
6. Exact verification commands and results.
7. Any remaining known limitation.

Do not say:
- "done",
- "fixed",
- "all tests pass",
- "production ready"

unless the corresponding verification was actually executed and observed successful.

**Continue until the complete repair is implemented, reviewed, and verified.**
