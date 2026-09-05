# Fitsho Workout Engine — Quality & Safety Repair Task

You are working in the **Fitsho** repository (`mohammad4242/fitsho`). Treat this as an end-to-end engineering task, not a code-suggestion task.

## Operating mode

Read `AGENTS.md` first, inspect the current working tree, preserve unrelated/uncommitted changes, and then continue autonomously through diagnosis, implementation, regression tests, and verification.

**Do not ask routine implementation questions.** Ask the user only when there is a genuine blocking ambiguity that cannot be resolved from this specification, the repository, or existing tests. Otherwise make the smallest architecture-consistent decision and continue until the task is complete.

Do not stop after writing code. Do not claim success from static inspection. Run the relevant tests and final verification commands, fix failures, rerun them, and only finish when the required behavior is proven.

The PDF observations below were produced from an earlier end-to-end run. **Current HEAD may already contain partial fixes.** Before changing a subsystem, reproduce the relevant behavior on current HEAD. If a defect is already fixed, keep or add a focused regression test proving it and move to the next defect. Do not duplicate existing mechanisms unnecessarily.

---

## Goal

Improve the deterministic workout-program engine so that it behaves like a competent strength coach under the following invariants:

1. Important working compounds such as push-ups and pull-ups are performed early, not buried after accessory/isolation work.
2. Explicit muscle priorities materially influence the split topology, not only weekly set counts. A 4-day athlete with strongly upper-body priorities must be able to receive a safe **3 upper / 1 lower** specialization layout when that is the best fit.
3. One session must not contain semantically redundant variants such as **Barbell Squat + Squat** with no meaningful training-role difference.
4. Structured injuries/cautions should first cause safe adaptation and redistribution. Example: bodyweight-only + wrist caution should prefer a lower-body/core-biased program instead of failing merely because horizontal/vertical pushing is unavailable.
5. Injury/limitation input must be **structured selection only**. Arbitrary free-text limitation text must not be converted into an uncomputable safety object that automatically rejects program generation.
6. Recovery must reflect both direct and indirect muscle stress. Canonical upper/lower plans should alternate upper and lower training days where feasible; moderate/high stress to the same muscle should have adequate calendar recovery; and a heavy chest session must not be followed immediately by a direct shoulder session when the shoulder has already received meaningful pressing stress.
7. Existing hard safety, equipment, duration, volume, and exact-day-count constraints must remain intact.

Do not solve these issues with Persian/English exercise-name string matching. Use semantic metadata and existing engine abstractions.

---

## Reference profiles from the 10-profile end-to-end report

Recreate these as regression fixtures if the repository does not already contain equivalent fixtures. Use the engine enums/types rather than display strings.

1. **User 1 — Maryam**: 26F, 165 cm, 62 kg, fat loss, beginner / 4 months, 3 days, gym, knee caution, priorities glutes + abs/core, 45 min, 6 weeks, moderate.
2. **User 2 — Reza**: 34M, 182 cm, 88 kg, hypertrophy, intermediate / 30 months, 4 days, gym, priorities chest + back + shoulders, 60 min, 8 weeks, moderate.
3. **User 3 — Sara**: 22F, 158 cm, 50 kg, first month / 0 months, 2 days, home with adjustable dumbbells, balanced priorities, 45 min, 4 weeks, light.
4. **User 4 — Kamran**: 44M, 176 cm, 84.5 kg, recomposition, intermediate / 18 months, 3 days, gym, lower-back caution, priorities back + biceps, 60 min, 6 weeks, moderate.
5. **User 5 — Niloofar**: 38F, 170 cm, 67 kg, weight loss, beginner / 2 months, 3 days, home, bodyweight only, wrist caution, priorities quadriceps + glutes, 45 min, 4 weeks, moderate.
6. **User 6 — Pejman**: 29M, 188 cm, 94 kg, strength, advanced / 60 months, 5 days, gym, priorities chest + quadriceps + back, 75 min, 8 weeks, vigorous/heavy.
7. **User 7 — Farnaz**: 30F, 168 cm, 59 kg, hypertrophy, intermediate / 20 months, 5 days, gym, shoulder caution, priorities glutes + hamstrings + shoulders, 60 min, 6 weeks, moderate.
8. **User 8 — Amirhossein**: 51M, 173 cm, 79 kg, fat loss, beginner / 3 months, 3 days, gym, selected neck + lower-back cautions, balanced priorities, 45 min, 6 weeks, light. The old profile also contained free text describing acute lumbar disc injury and cervical stenosis; the old engine rejected solely because this free text was mapped to a non-computable limitation. The new product behavior is defined below: workout generation is driven by structured selections and true structured red flags, not arbitrary free text.
9. **User 9 — Mahsa**: 24F, 162 cm, 55.5 kg, recomposition, advanced / 48 months, 4 days, gym, priorities glutes + back + abs/core, 75 min, 8 weeks, vigorous/heavy.
10. **User 10 — Alireza**: 20M, 175 cm, 64 kg, first month / 0 months, 3 days, home with adjustable dumbbells, priorities chest + biceps, 45 min, 4 weeks, moderate.

Important report regressions to reproduce:

- User 2: a 4-day upper-priority profile did not have a 3-upper/1-lower split available; one reported day was also estimated around 79 minutes for a 60-minute request.
- User 3: a push-up appeared in the middle of the workout; one 45-minute session was reported around 69 minutes.
- User 4: the same lower session contained **Barbell Squat** and **Squat**. Also audit the lower-back caution because unsupported bent-over rowing/heavy axial-loading movements appeared in this profile.
- User 5: generation failed with `CONSTRAINT_UNSATISFIED`, including unavailable required push-pattern slots under bodyweight-only + wrist caution.
- User 8: generation failed with `STATUS_SAFETY_REJECTED_PROGRAM` / `LIMITATION_REQUIRES_COMPUTABLE_CONSTRAINTS` because free-text `physical_limitations` was converted to an unstable/uncomputable limitation.
- User 9: the same lower session again contained **Barbell Squat + Squat**, proving the redundancy is systemic rather than user-specific. Consecutive lower/glute-heavy exposures also need recovery review.
- User 10: push-up was correctly early in some sessions; preserve that good behavior. Use it as a positive ordering regression.

---

# Confirmed code-level root causes to verify on current HEAD

Do not blindly trust these notes if current HEAD has moved; verify each against the code before editing.

## A. Four-day split topology is missing the required upper specialization option

Inspect:

- `backend/app/workouts/program_engine/split_selector.py`
- `backend/app/workouts/program_engine/priority_allocation.py`
- `backend/app/workouts/program_engine/enums.py`
- `backend/app/workouts/program_engine/template_selector.py`
- `backend/app/workouts/program_engine/template_scoring.py`
- `backend/app/training_templates/seed_data.py`
- `backend/app/training_templates/tags.py`

At the inspected revision, `generate_split_candidates(4)` exposed balanced 2U/2L-style options, full-body variants, PHUL, and body-part rotation, but no 4-day 3-upper/1-lower specialization topology. `PriorityAllocationPolicy` can score or distribute priority volume over **existing** focuses, but it cannot invent a split that is absent from the candidate set.

There is already a `SplitType.UPPER_LOWER_SPECIALIZATION` used by a higher-day layout. Prefer reusing it for 4 days if the semantics stay clear; otherwise introduce a narrowly named split type and update all serializers/ruleset complexity/tests consistently.

### Required behavior

For 4 training days, when explicit priorities are predominantly upper-body — especially the exact User-2 case `{chest, back, shoulders}` with no lower-body priority — the engine must have a safe 3-upper/1-lower candidate and should rank/select it when it improves priority frequency without violating recovery, duration, or lower-body minimum coverage.

A valid conceptual layout is:

`upper -> lower -> upper -> upper-specialization`

The calendar scheduler/recovery repair must place those upper sessions far enough apart; do **not** simply put two hard upper sessions on consecutive calendar days.

Do not globally force 3U/1L for every chest priority. A single upper priority that is already adequately served by 2U/2L can remain balanced. The exact User-2 profile, however, must select the upper-specialization topology when the catalog can safely construct it.

Also verify the **template-first** path. If a balanced reference template always wins before generated splits, fix the template coverage/scoring or add/retag the appropriate reference template so that explicit priority topology is not silently defeated by template selection.

### Tests

Add focused tests to `test_priority_allocation.py` and/or the most appropriate split/template test modules:

- 4-day `{chest, back, shoulders}` -> 3 upper exposures / 1 lower exposure and the specialization split is ranked above balanced alternatives when constructible.
- Lower-body-priority or balanced 4-day profiles do not inherit an upper bias.
- Selected weekdays satisfy the final recovery invariant.
- An end-to-end `generate_program(...)` test proves the result, not only `rank_split_candidates(...)`.

---

## B. Semantic duplicate exercises are penalized, not reliably prohibited

Inspect:

- `backend/app/workouts/program_engine/session_builder.py`
- `backend/app/workouts/program_engine/exercise_semantics.py`
- `backend/app/workouts/program_engine/session_structure.py`
- `backend/app/workouts/program_engine/validation.py`
- `backend/app/exercises/models.py`
- exercise candidate construction in `backend/app/workouts/service.py`

At the inspected revision, session selection has concepts such as `_role_repeated(...)` and `_session_role_limit(...)`, but repeated roles are often only a ranking penalty and the generic role limit can still allow two near-equivalent squat compounds. The existing semantic model already includes useful fields such as movement pattern, primary muscle, muscle focus, exercise type, secondary muscles, body position, laterality, and `substitution_group`.

### Required behavior

Introduce one centralized, deterministic **near-equivalent exercise redundancy** policy. Reuse `exercise_semantics.py` rather than scattering ad-hoc checks.

The policy must distinguish:

- **Invalid redundancy:** Barbell Squat + generic Squat in the same session when both represent the same bilateral squat training role with no meaningful focus difference.
- **Valid diversity:** squat + lunge; squat + knee extension; flat press + incline press when metadata expresses a meaningful focus/role difference; horizontal pull variants with genuinely distinct roles.

Use semantic metadata. `substitution_group` should be a strong signal, but first inspect whether any real groups are overly broad. A safe implementation can combine substitution family with role-signature fields such as primary muscle, movement pattern, muscle focus, exercise type, laterality/body position, etc. Do not make every repeated movement pattern illegal.

Prevent the duplicate during selection **and** validate final sessions so late duration/volume/template repairs cannot reintroduce it. Add an explainable reason/error code for a rejected/repaired semantic duplicate.

### Tests

Add regressions that:

- build candidates equivalent to `Barbell Squat` and `Squat` and prove that only one can remain in a single session;
- prove a complementary quad movement can replace the redundant second squat;
- prove distinct chest roles still coexist when metadata justifies them;
- run User 4 and User 9-like end-to-end fixtures and assert no semantically redundant pair exists in any workout day;
- prove deterministic output is unchanged by reversing candidate catalog order.

Do not weaken existing exact-ID or substitution safety rules.

---

## C. Push-up / pull-up ordering lacks a semantic “important working compound” tier

Inspect:

- `backend/app/workouts/program_engine/session_structure.py`
- `backend/app/workouts/program_engine/session_builder.py`
- `backend/app/workouts/program_engine/exercise_semantics.py`
- `backend/app/workouts/program_engine/exercise_ranker.py`

At the inspected revision, final ordering distinguishes broad phases such as compound vs isolation and strength-primary reasons, but non-strength sessions do not have a robust semantic tier for a demanding bodyweight working compound. Therefore a push-up can end up after several other movements even when it is serving as the main horizontal press.

### Required behavior

Create an explicit semantic ordering concept such as `primary_working_compound`, `key_compound`, or an equivalent internal role/reason code.

Do **not** detect push-ups or pull-ups from their names. Use existing metadata such as:

- `exercise_type == COMPOUND`
- movement pattern
- bodyweight/equipment
- selected required-slot role
- skill/fatigue/stability data
- template slot/adaptation role where applicable

When a push-up/pull-up is selected as a primary working movement, it should normally be in the **first 1–2 main resistance exercises**, before isolation/accessory work. Preserve higher-priority primary strength lifts and explicit template intent where it is semantically justified. A movement intentionally tagged/selected as an accessory/finisher must not be forcibly promoted solely because it is bodyweight.

Ordering hierarchy should remain understandable, for example:

1. primary strength/key working compounds;
2. other main compounds;
3. secondary/accessory compounds;
4. isolation work;
5. optional core/supplemental work.

Preserve strict chest-before-triceps and back-before-direct-biceps rules already covered by tests.

### Tests

Extend `backend/tests/workouts/program_engine/test_session_structure.py` and/or `test_selection_sessions.py`:

- working push-up appears within first 2 main exercises;
- working pull-up appears within first 2 main exercises;
- neither is left behind isolation work after finalization or late repair;
- strength primary lift still outranks a non-primary push-up when appropriate;
- an explicitly accessory/finisher bodyweight movement is not incorrectly promoted if such a semantic role exists.

Use User 3 as the negative regression and User 10 as a positive regression.

---

## D. Wrist caution + bodyweight-only can fail because required push slots remain hard requirements

Inspect:

- `backend/app/workouts/program_engine/session_builder.py`
- `backend/app/workouts/program_engine/engine.py`
- `backend/app/workouts/program_engine/eligibility.py`
- `backend/app/workouts/candidate_selector.py`
- `backend/app/workouts/program_engine/validation.py`
- `backend/tests/workouts/program_engine/test_coach_quality_regressions.py`

The code already contains a structured **required-slot relaxation/recovery** mechanism for cases where a caution removes all candidates for a required role (there is existing knee-caution coverage around `RECOVERY_APPLIED_REQUIRED_SLOT_RELAXATION`). Reuse/generalize that architecture instead of bypassing safety.

In the old User-5 output, the engine exhausted alternatives because full-body/upper structures demanded horizontal/vertical push slots, while bodyweight-only + wrist caution removed safe wrist-loaded push movements.

### Required behavior

If a required movement pattern is unavailable **because structured safety filtering removed every candidate for that slot**, the engine may relax that required pattern and rebalance the plan, provided enough safe resistance training remains to build a useful program.

For the exact User-5 profile:

- Prefer a safe **lower-body + glute + core bias** across the week.
- Include a light/small upper-body component only if actual safe exercises exist with the declared equipment.
- Never fabricate a pull-up when no pull-up bar is available.
- Never re-enable a wrist-loading exercise merely to satisfy a slot.
- Do not reduce the requested 3 resistance-training days merely to make construction easier.
- Do not fail only because horizontal/vertical pushing is unavailable if the safe lower/core catalog has enough capacity to create three quality sessions.

Preserve the existing behavior that a missing required slot with **no structured safety reason** remains a real construction failure.

Plumb the relaxed requirement into validation using the engine's existing `relaxed_required_pattern_groups`/reason-code mechanism rather than disabling global movement-pattern validation.

Use explainable reason codes. Prefer existing naming conventions; examples of the intended meaning are:

- required pattern relaxed because of structured limitation;
- program rebalanced toward safe lower body;
- wrist-loaded push omitted because of wrist caution.

### Tests

Add a User-5-like test with bodyweight-only equipment and wrist caution:

- `generate_program(...)` returns a valid 3-day program if the safe lower/core test catalog is sufficient;
- every selected exercise is equipment-compatible;
- every selected exercise is disjoint from blocked wrist-loading caution tags;
- no unavailable pull-up-bar movement is selected;
- the relaxed required push-pattern group is visible in trace/metrics/reason codes;
- all sessions still meet minimum quality/exercise-count rules or emit an existing explicit constrained-quality warning where the ruleset allows it.

Keep the existing test that an ordinary missing required pattern is rejected when no safety-driven relaxation is justified.

---

## E. Free-text `physical_limitations` is directly converted to an uncomputable safety limitation

Inspect end-to-end:

- `backend/app/profile/models.py`
- `backend/app/profile/schemas.py`
- `backend/app/profile/enums.py`
- `backend/app/workouts/service.py`, especially `_to_program_request(...)`
- `backend/app/workouts/program_engine/schemas.py`
- `backend/app/workouts/program_engine/safety.py`
- `backend/app/workouts/candidate_selector.py`
- Alembic revisions
- `frontend/src/features/profile/ProfileFormFields.tsx`
- `frontend/src/features/profile/types.ts`
- `frontend/src/features/profile/profileValidation.ts`
- public onboarding training questions and profile API serialization
- Persian/English i18n strings and related tests

At the inspected revision, `physical_limitations` is a free-text profile field. `_to_program_request(...)` sanitizes non-empty text and constructs a `Limitation(..., stable=False)` object. The safety gate then rejects unstable/non-computable limitations with `LIMITATION_REQUIRES_COMPUTABLE_CONSTRAINTS`. This is the direct cause of the User-8 behavior.

### Product decision — implement this, do not ask again

**New injury/limitation input is selection-only.**

- New UI/API flows must not ask the user for arbitrary free-text injury/limitation text.
- Workout generation must derive computable constraints from structured `training_cautions` and other already-structured safety inputs.
- Keep genuine structured `red_flags` / medical-review gates as hard safety rules. Do not weaken them.
- Do not use keyword NLP to infer medical safety from legacy prose.
- Do not add an “Other + free text” backdoor that recreates the same failure mode.

### Legacy data policy

Avoid destructive data loss.

If `physical_limitations` already contains user data, the safest default is:

1. stop exposing/accepting it as a new workout-generation input;
2. stop mapping it into `ProgramGenerationRequest.injuries_and_limitations`;
3. preserve the legacy database value for compatibility/audit unless the repository's migration conventions make a safe, tested migration/removal clearly preferable;
4. generation must not reject solely because legacy text exists;
5. if a user must re-confirm limitations in structured form, make that explicit through structured selection, not implicit text parsing.

If the column can be cleanly deprecated without a destructive migration, prefer that smaller change. Do not drop stored text merely to make tests pass.

The public guided training flow already uses structured caution buttons; make the profile/edit flow consistent with it.

If `TrainingCaution.OTHER` remains, it must have a defined conservative structured behavior and must not invite a free-text explanation. Prefer explicit additional caution choices if the existing product taxonomy needs expansion.

### Tests

Backend:

- a profile with structured lower-back/neck cautions produces the corresponding computable constraints;
- legacy non-empty `physical_limitations` alone no longer creates `Limitation(stable=False)` and no longer triggers `LIMITATION_REQUIRES_COMPUTABLE_CONSTRAINTS`;
- a real structured red flag still rejects exactly as before;
- create/update schemas no longer require or encourage new arbitrary limitation prose according to the chosen backward-compatible API design.

Frontend:

- profile/onboarding injury UI contains only structured selections;
- no free-text limitation textarea is rendered;
- caution selection serializes correctly;
- Persian and English labels remain complete;
- existing profile-edit/onboarding tests are updated without removing unrelated coverage.

User-8 regression:

- with the legacy free-text field present in stored data but no structured red flag, generation must not fail **solely** because of that text;
- structured neck/lower-back cautions must still filter unsafe exercises normally.

---

## F. Recovery logic needs an explicit indirect-stress and split-spacing quality invariant

Inspect:

- `backend/app/workouts/program_engine/recovery.py`
- `backend/app/workouts/program_engine/split_selector.py`
- `backend/app/workouts/program_engine/validation.py`
- `backend/app/workouts/program_engine/rulesets/resistance_training_v1.py`
- exercise secondary-muscle metadata / semantic derivation
- `backend/tests/workouts/program_engine/test_recovery_exposure_load.py`
- `backend/tests/workouts/program_engine/test_coach_quality_regressions.py`

Current code already classifies direct/secondary exposure and can repair weekdays. Do not replace this with a simplistic “never train the same body region on consecutive workout rows” rule.

The likely remaining gap is that indirect synergist stress is only as good as secondary-muscle metadata and exposure thresholds. If chest pressing does not encode enough shoulder/triceps exposure, a chest day followed by a direct shoulder day may look artificially safe.

### Required behavior

Hard invariant:

- Moderate/high meaningful exposure to the same muscle must satisfy the ruleset recovery gap on the actual **calendar weekdays**, including the week boundary.
- A heavy chest pressing session that gives meaningful anterior-shoulder/shoulder secondary exposure must not be followed the next calendar day by a direct moderate/high shoulder session.
- Similar logic applies to other obvious synergist chains when represented by metadata, without inventing blanket body-part bans.

Scheduling preference:

- For canonical upper/lower splits, arrange workout focuses in an alternating upper/lower sequence when counts allow.
- For 4-day 3U/1L specialization, literal alternation is impossible; use calendar spacing so the three upper exposures still recover.
- PPL and other valid splits should remain valid when their actual muscle-stress exposure satisfies recovery.

Audit exercise metadata needed for this to work. Compound chest presses/push-ups should expose shoulders/triceps as appropriate; pulls should expose biceps where appropriate; lower-body compounds should expose glutes/hamstrings/quads accurately. Prefer metadata fixes/invariants over hard-coded exercise-name rules.

If existing secondary-set credit and thresholds already catch the case once metadata is correct, do not add a redundant conflict matrix. If a small focus-level pre-ranking heuristic is still needed to avoid obviously bad candidates before exercise construction, keep it a **preference**; final actual-exercise recovery validation remains authoritative.

### Tests

Extend recovery tests with at least:

- chest press with shoulder as a secondary muscle + direct shoulder moderate work the next calendar day -> invalid;
- same sessions with a full recovery day between them -> valid;
- consecutive moderate/high glute/lower exposures -> invalid;
- genuinely light accessory exposure can remain consecutive when below the ruleset threshold;
- `repair_recovery_weekdays(...)` rearranges weekdays without deleting a requested resistance session;
- a 4-day upper/lower plan alternates focus and passes recovery;
- the new 4-day upper-specialization plan passes recovery across the week boundary;
- User-9-like end-to-end program has no consecutive moderate/high repeated lower/glute exposure.

Do not merely assert focus labels. Compute actual direct + secondary exposure from the selected exercises.

---

# Additional report-level quality audits to include

These are directly related to the same failures and should be checked while touching the engine.

## 1. Session duration

The report contained sessions materially over the requested duration. Current HEAD already has `duration_policy.py` and validation logic, so first reproduce before changing it.

Use `get_session_duration_policy(...)` as the source of truth. Do **not** reinterpret the requested duration as an exact hard minute if the official policy intentionally provides tolerance/warm-up/cardio allowance.

Acceptance rule: no successful session may exceed the official policy's maximum total duration except an already-defined, explicitly justified extension that validation recognizes. Add regression coverage for the User-2/User-3-like cases if not already covered by duration tests.

## 2. Lower-back caution metadata

User 4 received an unsupported bent-over barbell row and heavy squat-like work despite a lower-back caution in the report. Audit whether the current catalog/semantic derivation correctly marks such unsupported trunk-loading or high axial-loading movements.

Do not filter by names such as “bent over”, “barbell row”, or Persian display text. Use `LOWER_BACK_LOADING`, axial-load metadata, support/body-position/stability semantics, or improve the catalog metadata so the existing caution filter can work.

Chest-supported/seated rows should remain available when otherwise safe.

Add at least one positive and one negative lower-back-caution eligibility regression.

---

# Implementation protocol

Follow this order so each change has a proven cause and does not hide another failure.

## Phase 0 — Baseline and reproduction

1. Read `AGENTS.md` and relevant engine architecture.
2. Run `git status` and do not reset/discard unrelated changes.
3. Run the existing focused engine tests before modifications.
4. Recreate targeted fixtures for Users 2, 3, 4, 5, 8, 9, and 10 using current engine types and the current exercise catalog/test catalog.
5. Record which old defects still reproduce on current HEAD and which are already fixed.
6. For every still-reproducing defect, write a failing regression test **before** the production fix.

A report from an older engine version is evidence, not permission to force current code to fail the same way.

## Phase 1 — Semantic exercise identity and ordering

Implement the centralized near-duplicate policy and key-compound ordering first. These affect session construction and can change later recovery/duration behavior.

Run:

```bash
cd backend
pytest tests/workouts/program_engine/test_exercise_semantics.py -q
pytest tests/workouts/program_engine/test_session_structure.py -q
pytest tests/workouts/program_engine/test_selection_sessions.py -q
pytest tests/workouts/program_engine/test_coach_quality_regressions.py -q
```

Fix all regressions before continuing.

## Phase 2 — Four-day upper specialization / priority-aware topology

Add or reuse the 4-day specialization split, integrate it into priority scoring and the template path, then prove User 2 end-to-end.

Run the relevant split, priority, template, volume, recovery, and golden tests. At minimum include:

```bash
pytest tests/workouts/program_engine/test_priority_allocation.py -q
pytest tests/workouts/program_engine/test_recovery_exposure_load.py -q
```

Also run whichever existing split/template test modules you touched.

## Phase 3 — Safety-driven slot relaxation for User 5

Generalize the existing structured-caution required-slot recovery mechanism to the wrist/bodyweight case without weakening eligibility.

Prove:

- safe lower/core program succeeds when capacity exists;
- blocked wrist-loading exercises remain blocked;
- ordinary non-safety missing-slot failures still fail.

Run selection, coach-quality, validation, duration/capacity, and golden engine tests.

## Phase 4 — Structured-only limitation input

Update backend profile -> workout request mapping and frontend/profile UI/API flow. Handle legacy data conservatively.

Run backend profile/workout service tests plus frontend profile/public-onboarding/API tests.

Do not finish this phase until a stored legacy `physical_limitations` string is proven unable to trigger the old uncomputable-limitation rejection by itself.

## Phase 5 — Recovery and metadata quality

Fix only the minimum missing pieces after reproducing current behavior. Prefer correct secondary-muscle/caution metadata and the existing exposure model over duplicated scheduling rules.

Prove chest -> shoulder next-day overlap and lower/glute overlap behavior through actual exercise exposure tests.

## Phase 6 — 10-profile regression

Create one deterministic end-to-end regression module or benchmark scenario that runs all 10 reference profiles against a deterministic catalog/seeded catalog.

Do not assert exact exercise names everywhere; that makes the engine brittle. Assert **invariants**:

- requested resistance day count is preserved unless a pre-existing hard medical/red-flag policy explicitly forbids generation;
- all exercises are active, programmable, safe for structured cautions, and equipment-compatible;
- no session contains semantic near-duplicates;
- key working bodyweight compounds are early;
- official duration policy is respected;
- weekly volume stays inside hard limits;
- explicit priority metrics show measurable emphasis/frequency;
- recovery spacing is valid across the whole 7-day cycle;
- no chest-heavy -> direct shoulder-heavy next-day violation;
- no lower/glute repeated moderate/high exposure without required gap;
- generated program remains deterministic for the same seed/input/catalog.

Expected special cases:

- **User 5:** should succeed if the current safe catalog has enough lower/core capacity after wrist-safe relaxation. If it still cannot, the test must prove the exact remaining hard impossibility rather than accepting a generic construction failure.
- **User 7:** do not force success by weakening shoulder safety. It may remain a structured, explainable rejection if its requested shoulder priority/volume cannot be safely satisfied after legitimate adaptations.
- **User 8:** legacy prose alone must not cause rejection; true structured red flags still must.

---

# Non-negotiable engineering constraints

- Keep generation deterministic.
- Keep safety fail-closed for **structured red flags and actual hard contraindications**.
- Do not bypass `filter_eligible_exercises(...)` to satisfy a layout.
- Do not select unavailable equipment.
- Do not reduce requested resistance-training day count as a hidden fallback.
- Do not hard-code exercise display names, Persian text, or English substrings in engine logic.
- Reuse existing ruleset configuration instead of scattering magic numbers.
- New recovery thresholds/credits must be ruleset-owned and tested.
- Preserve reason codes / decision trace explainability; add reason codes for new adaptations and repairs.
- Keep template-generated and dynamically generated programs under the same final quality invariants.
- Do not solve duplicate exercises only in one construction path; late repairs and templates must also be validated.
- Do not solve recovery only from focus labels; final selected exercise exposure is authoritative.
- Do not remove a failing test just because behavior changed. Update it only when this specification intentionally changes the product rule, and add the replacement assertion.
- Do not make destructive schema migrations merely for convenience.
- Keep changes scoped to workout/profile behavior described here.

---

# Final verification

Use the repository's real commands from `AGENTS.md`.

Backend:

```bash
cd backend
uv sync
ruff check
ruff format --check
mypy
pytest
```

If the test database is required, use the repository's documented PostgreSQL/test setup and run migrations exactly as the project expects. Do not skip database tests and then report the backend as green.

Frontend:

```bash
cd frontend
npm install
npm run lint
npm run test
npm run build
```

If dependencies are already installed, do not waste time reinstalling unnecessarily.

After the full suites pass, rerun the targeted 10-profile regression and print a concise invariant summary for each profile.

Before reporting completion, inspect the final diff and verify that no unrelated files, generated secrets, `.env`, media, caches, or accidental binary artifacts are included.

---

# Definition of done

Do not finish until all of the following are true:

- [ ] User-2-like 4-day chest/back/shoulder priority can select a safe 3-upper/1-lower specialization layout end-to-end.
- [ ] Working push-ups/pull-ups are early main exercises and are not buried behind isolation work.
- [ ] Barbell Squat + semantically equivalent Squat cannot coexist in one session without an explicit meaningful semantic distinction.
- [ ] User-5-like wrist-caution/bodyweight-only profile adapts toward lower/core instead of failing on a safely relaxable push requirement when safe capacity exists.
- [ ] New limitation/injury UX is selection-only; no arbitrary free-text limitation field drives workout generation.
- [ ] Legacy free-text limitation data alone cannot create `LIMITATION_REQUIRES_COMPUTABLE_CONSTRAINTS` rejection.
- [ ] Structured red flags and structured caution filters remain enforced.
- [ ] Upper/lower layouts alternate where feasible, and all final schedules satisfy actual muscle-exposure recovery.
- [ ] Heavy chest exposure cannot be followed the next day by meaningful direct shoulder work when recovery rules require a gap.
- [ ] User-9-like consecutive lower/glute stress is either rescheduled or reduced to a recovery-valid exposure.
- [ ] Official session duration limits are respected.
- [ ] Lower-back caution no longer allows semantically high-risk unsupported trunk-loading movements merely because metadata was incomplete.
- [ ] Exact requested training-day count remains intact for successful programs.
- [ ] New targeted regressions pass.
- [ ] Full backend tests, Ruff, formatting check, and mypy pass.
- [ ] Frontend lint, tests, and build pass.
- [ ] Final 10-profile regression passes the defined invariants.

## Final response format

When finished, report:

1. the root cause for each defect;
2. the exact files changed;
3. the behavior implemented;
4. the targeted tests added/updated;
5. the exact verification commands run and their pass/fail result;
6. the final 10-profile regression summary, explicitly mentioning Users 2, 4, 5, 8, and 9;
7. any remaining genuine limitation.

Do not say “done”, “fixed”, or “all tests pass” unless you actually ran the commands and observed successful output in this session.
