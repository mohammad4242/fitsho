# Fitsho Training Catalog / Program Engine Upgrade — Sol Lead Prompt

You are the **lead engineer (Sol)** for this task.

Your goal is to upgrade the existing Fitsho **17-template training catalog and Program Engine** without replacing the current architecture.

Use **Luna subagents aggressively for low-risk, repetitive, audit, lookup, and test work** so that Sol spends tokens only on architecture, risky logic, integration, and final review.

Do **not** commit or push.

---

## 0. Operating model

### Sol owns
- architecture decisions;
- level-aware palette design;
- Program Engine behavior changes;
- catalog-rule enforcement;
- seed/idempotency strategy;
- admin safety validation;
- advanced-method integration;
- cross-file integration;
- final diff review and regression judgment.

### Delegate to Luna
Use multiple Luna subagents in parallel where possible.

Good Luna tasks:
1. audit all 17 templates and report slot counts, supported levels, tags, methods, prescriptions;
2. verify every requested exercise slug against real active programmable exercises;
3. find placeholder/unprogrammable references;
4. inspect current tests and propose missing cases;
5. audit metadata/tag mismatches;
6. audit seed behavior and admin-overwrite risks;
7. audit 4/5/6-day catalog structures for invalid pure Full Body layouts;
8. draft focused tests after Sol defines expected behavior.

Do not ask Luna to make independent architecture decisions.  
Luna should return concise findings, file paths, and exact symbols/lines to Sol.

### Token discipline
- Read only relevant files.
- Do not repeatedly re-scan the whole repo.
- Prefer targeted search/find.
- Reuse existing abstractions before adding new ones.
- Avoid broad refactors and formatting churn.
- After each phase, summarize findings in <=10 bullets before proceeding.

---

# 1. Non-negotiable architecture

Preserve the current public catalog architecture:

- exactly **17 canonical templates** (`t01` ... `t17`);
- keep `supported_levels`;
- do **not** expand back to ~41 level-specific duplicate templates;
- level differences must be handled inside the current 17-template system through level-aware rendering / palette / ranking / prescription logic.

Public template count must remain 17 unless an existing unrelated test fixture requires otherwise.

---

# 2. First read / scope

Sol must inspect these areas first:

- `backend/app/training_templates/seed_data.py`
- `backend/app/training_templates/models.py`
- `backend/app/training_templates/tags.py`
- `backend/app/training_templates/catalog_placeholders.py`
- `backend/app/training_templates/admin_service.py`
- `backend/app/training_templates/service.py`
- `backend/app/training_templates/seed.py`
- `backend/app/training_templates/engine_reference.py`
- `backend/app/workouts/program_engine/template_selector.py`
- `backend/app/workouts/program_engine/template_scoring.py`
- `backend/app/workouts/program_engine/session_builder.py`
- `backend/app/workouts/program_engine/exercise_ranker.py`
- `backend/app/workouts/program_engine/session_structure.py`
- `backend/app/workouts/program_engine/supplemental_policy.py`
- `backend/app/workouts/program_engine/supersets.py`
- `backend/app/workouts/program_engine/rulesets/resistance_training_v1.py`
- exercise seed / manifest / programming metadata / catalog visibility code;
- relevant tests.

Do not modify unrelated modules.

---

# 3. Phase A — parallel audits (delegate to Luna)

Run these audits in parallel.

## Luna A1 — 17-template audit
For every template `t01`–`t17`, report:
- days/week;
- supported levels;
- focus tags;
- structure focus per day;
- main slot count;
- supplemental/core-like slots;
- prescriptions;
- intensity methods;
- suspicious metadata.

Flag:
- invalid catalog structures;
- repeated prescriptions;
- level-safety problems;
- wrong/missing tags;
- duplicate or near-duplicate sessions.

## Luna A2 — exercise reference audit
Verify all exercise references used by templates and these requested palettes.

Report for each:
- actual persisted slug/id;
- active?;
- `is_programmable`?;
- placeholder?;
- source;
- equipment;
- difficulty / stability / skill metadata when available.

Never invent a replacement. Return the real matching exercise.

## Luna A3 — admin + seed audit
Find:
- where Admin assigns template slot exercises;
- whether inactive/unprogrammable/placeholder exercises can currently be selected;
- whether seeding can overwrite admin edits;
- whether deleted/disabled admin templates or slots can be recreated.

Return the minimal safe fix strategy.

## Luna A4 — tests / catalog-rule audit
Find existing tests for:
- canonical 17 templates;
- template tags;
- seeding;
- admin validation;
- level eligibility;
- session size;
- supplemental work;
- supersets/drop sets.

Also identify where catalog topology rules should be enforced.

Sol reviews all four audit reports before implementation.

---

# 4. Catalog topology rules must be real constraints

Catalog rules must be enforced by code/tests, not documentation only.

At minimum:

- **Do not allow pure 4-day Full Body**
- **Do not allow pure 5-day Full Body**
- **Do not allow pure 6-day Full Body**

High-frequency 4/5/6 day catalogs must use appropriate split structures such as upper/lower, PPL, specialization, body-part rotation, hybrid layouts, etc.

Keep valid lower-frequency Full Body templates where appropriate.

Add a centralized validation function / invariant if one does not already exist.

Validation must run for seeded canonical templates and should be testable independently.

Do not scatter magic conditions across many files.

---

# 5. Level-aware exercise palettes

The 17 templates may support multiple levels, but their resolved exercises must differ by experience level.

## FIRST_MONTH
Strong preference:

`Machine > Smith > Cable > supported/simple Dumbbell > Barbell`

For normal gym profiles, the majority should clearly be Machine / Smith / Cable.

Prefer:
- low stability demand;
- low skill demand;
- supported/seated/lying patterns;
- predictable setup;
- low unnecessary axial loading.

Avoid high-skill free-weight compounds as defaults when safer equivalents exist.

Anchor exercises include:

- `fedb-0750-smith-chair-squat`
- `fedb-0748-smith-machine-leg-press`
- `fedb-0585-lever-leg-extension`
- `fedb-0599-lever-seated-leg-curl`
- real programmable Glute Bridge
- `fedb-0605-lever-standing-calf-raise`
- `fedb-0577-lever-lying-chest-press`
- `fedb-1299-lever-incline-hammer-chest-press`
- `fedb-drv-lever-pec-deck-fly-pec-deck-fly`
- `fedb-0581-lever-high-row`
- `fedb-0974-cable-close-grip-lat-pulldown`
- real programmable Smith Machine Shoulder Press
- `fedb-0584-lever-lateral-raise`
- `fedb-0602-lever-seated-reverse-fly`
- `fedb-0592-lever-preacher-curl`
- `fedb-1723-cable-triceps-pushdown`

These are anchors, not a closed list.

## BEGINNER
Still machine/Smith/cable biased, but less restrictive than First Month.

Allow more simple/stable dumbbell work.

Barbell technical compounds should not be the default when a safer high-quality option exists.

## INTERMEDIATE
No meaningful equipment restriction.

Freely use:
- Barbell
- Dumbbell
- Cable
- Machine
- Smith
- Bodyweight

Free-weight compounds are normal and expected.

Anchors include:
- Barbell Back Squat
- Dumbbell Lunge
- Leg Extension
- Romanian Deadlift
- Seated Leg Curl
- Glute Bridge
- Barbell Bench Press
- Dumbbell Incline Bench Press
- Cable Fly
- Barbell Bent-Over Row
- Seated Cable Row
- Lat Pulldown
- Straight-Arm Pulldown
- Seated Dumbbell Shoulder Press
- Cable Lateral Raise
- Cable Reverse Fly
- Barbell / Hammer / Cable Curl
- Pushdown / Overhead Cable Triceps Extension
- Standing Calf Raise

## ADVANCED
Use the full valid pool.

Must have access to more exercise variation than Intermediate.

Examples:
- Front Squat
- Dumbbell Bench Press
- advanced row variations
- Pull-Up
- EZ-Bar triceps extension
- shrugs
- alternate leg curls / calf raises
- machine/cable/free-weight variants where useful.

Do not make Advanced merely “Intermediate + 1–2 different exercises”.

---

# 6. Templates supporting First Month / Beginner

This is critical.

If one canonical template supports First Month or Beginner, **its shared movement roles and default prescription must remain appropriate for those levels**.

Do not solve level-awareness by keeping an unsafe shared heavy exercise and hoping the engine substitutes it later.

For multi-level templates:
- store/render a safe movement role;
- resolve to level-appropriate candidates;
- keep the public template as one canonical template.

First Month / Beginner must never inherit an advanced default movement just because the same canonical template also supports Intermediate.

---

# 7. Exercise ranking must also be level-aware

Do not only change `seed_data.py`.

The final engine selection must respect experience level.

### First Month
Strong bonus for:
- Machine / Smith / Cable;
- low stability;
- low skill;
- supported body position;
- low setup/fatigue where quality is comparable.

### Beginner
Same direction, weaker strength.

### Intermediate
Mostly neutral equipment preference.

### Advanced
No equipment restriction and no artificial penalty against higher-skill variations when otherwise safe and appropriate.

Safety, injury/caution, available equipment, dislikes, compatibility, and user constraints always override palette preference.

Keep deterministic selection / seeded tie-breaking.

---

# 8. Main session size

Current hard upper bound of 9 may remain.

Normal sessions with sufficient time and candidates should target:

- **7–9 MAIN exercises**
- 8 is a useful default target

Keep 5 only as a constrained fallback for short duration, limited equipment, injuries, or insufficient valid candidates.

Do not pad sessions with redundant filler.

Use `main_exercise_count()`, not raw list length.

---

# 9. Supplemental muscles

These stay supplemental:

- ABS
- OBLIQUES
- LOWER_BACK
- NECK
- FOREARMS

They:
- do not count toward 7–9 main exercises;
- cannot be used to fake main coverage;
- do not appear as main session-title muscles;
- must be placed after all main exercises.

Allow:
- 0 supplemental;
- 1 supplemental;
- 2 supplemental.

Reject >2.

Front Plank / Side Plank are examples of optional supplemental work.

Calves and traps are **not** supplemental.

---

# 10. Exercise order and redundancy

Default order:

1. priority / heavy / technically important compound;
2. other main compounds;
3. secondary compounds;
4. isolation/accessory;
5. safe advanced intensity methods;
6. supplemental work last.

Before adding a near-duplicate movement just to reach 7–9, complete missing movement/muscle coverage.

Use existing:
- movement pattern;
- primary muscle;
- muscle focus;
- substitution group;
- role/priority metadata.

Redundancy is allowed only when justified by specialization, volume, or deliberate advanced variation.

Add an explicit reason code when deliberate redundancy is used.

---

# 11. Prescription quality for all 17 templates

The 17 templates must not remain mostly generic:

`3 x 8–12 / RIR 2`

Create professional, role-aware, level-aware prescription diversity.

Use existing prescription architecture where possible.

Vary intelligently by:
- movement role;
- exercise type;
- goal;
- level;
- template structure;
- intensity method.

Examples of reasonable differentiation:

### Primary compounds
- lower reps;
- longer rest;
- more conservative RIR for novice levels;
- heavier strength ranges where appropriate.

### Secondary compounds
- moderate rep ranges;
- moderate rest.

### Isolation
- higher reps;
- shorter rest;
- lower fatigue cost.

### First Month
- conservative RIR;
- controlled ranges;
- no advanced intensity techniques.

### Beginner
- simple double-progression style;
- no drop sets;
- no programmed advanced supersets.

### Intermediate
- broader rep ranges and more specialization.

### Advanced
- selected supersets/drop sets and higher variation.

Do not hardcode one universal prescription for all templates.

Prescriptions must still respect global set caps and safety policies.

---

# 12. Advanced methods

Reuse the existing method system:

- `STANDARD`
- `SUPERSET`
- `DROP_SET`

Advanced templates should use real intensity methods where suitable.

For appropriate Advanced bodybuilding/hypertrophy templates:
- at least one safe superset pair per week;
- at least one real drop-set slot per week.

Superset:
- reuse the existing safe superset policy;
- prefer biceps+triceps, compatible isolations, low-interference accessory pairs;
- never force heavy squat/RDL/primary strength compounds into supersets.

Drop set:
- prefer machine/cable/stable isolation work;
- never force it onto heavy barbell compounds.

Do not add advanced methods to First Month / Beginner.

---

# 13. Admin exercise validation

Admin must only accept a real exercise that is:

- existing;
- active;
- `is_programmable=True`;
- not a template placeholder;
- compatible with the intended slot constraints.

Reject:
- missing exercise;
- inactive exercise;
- `is_programmable=False`;
- placeholder/template-draft exercises.

Validation must happen server-side, not only in frontend UI.

Return a clear domain/API validation error.

Add focused tests.

---

# 14. Placeholder policy

Prefer real library exercises.

Do not create placeholders when a real matching exercise exists.

Template placeholders must never silently become valid admin/programming selections.

If placeholders remain needed for authoring/catalog drafts:
- keep them explicitly non-programmable;
- ensure Admin and Program Engine reject them as real executable slot exercises.

---

# 15. Metadata/tag correctness

Audit all 17 templates.

Fix incorrect or missing tags.

Example:
- if T03 is effectively Upper Priority but lacks the corresponding focus/priority tag, fix it.

Tags must accurately represent:
- split structure;
- specialization;
- priority emphasis;
- sex-specific intent if any;
- intensity-method presence;
- other existing catalog semantics.

Do not add tags merely to make tests pass.  
Metadata must match actual template content.

Add consistency validation where practical.

---

# 16. Seed must not overwrite Admin edits

Seeding must be safe and idempotent.

After an admin edits or deletes/disables a seeded template/slot, a later normal seed run must not blindly:
- overwrite the admin change;
- recreate a deleted item;
- restore old exercises;
- restore old prescriptions;
- restore removed slots.

Design the smallest reliable approach consistent with the current architecture.

Prefer a policy such as:
- seed creates missing canonical catalog records on initial/bootstrap install;
- later seed runs do not mutate admin-owned records unless an explicit migration/versioned upgrade path is invoked.

If the repo already has ownership/source/version fields, reuse them.

Do not introduce a large migration framework unless necessary.

Required tests:
1. first seed creates canonical catalog;
2. second identical seed is idempotent;
3. admin edit survives reseed;
4. admin deletion/disable survives normal reseed;
5. explicit intended catalog migration behavior is deterministic if you need one.

---

# 17. Slug integrity

For every requested short slug or fedb slug:

- resolve against actual seeded/library records;
- verify active;
- verify programmable;
- verify not placeholder.

Examples requiring verification:
- `dumbbell-lunge`
- `romanian-deadlift`
- `barbell-bent-over-row`
- `dumbbell-bench-press`
- `leg-extension`
- `standing-calf-raise`
- `smith-machine-shoulder-press`

If the persisted identifier differs, use the real canonical record.

Do not create fake aliases unless the architecture already supports them.

---

# 18. Implementation strategy

After audits, Sol should implement in this order:

## Phase B1 — invariants / validation
Sol:
- catalog topology validation;
- admin exercise validation;
- supplemental max=2;
- seed ownership/idempotency behavior.

Use Luna for tests.

## Phase B2 — level-aware palette
Sol:
- introduce the smallest clean level-aware palette abstraction;
- connect it to template rendering and ranking.

Use Luna for slug verification and test fixtures.

## Phase B3 — 17-template content
Delegate Luna to draft:
- per-template prescription improvements;
- tag corrections;
- candidate exercise mappings.

Sol reviews and integrates all 17.

## Phase B4 — session target + redundancy
Sol:
- preferred 7–9 main exercise target;
- keep constrained fallback;
- prevent duplicate filler.

## Phase B5 — advanced methods
Sol:
- real safe supersets/drop sets in Advanced-compatible templates;
- preserve existing safety checks.

## Phase B6 — full regression
Delegate broad test execution and failure triage to Luna.
Sol fixes only meaningful regressions.

---

# 19. Required tests / acceptance

At minimum cover:

### Catalog
- exactly 17 canonical templates;
- no accidental 41-template expansion;
- supported_levels preserved;
- no invalid pure 4/5/6-day Full Body catalog.

### First Month
Normal gym profile:
- clear Machine/Smith/Cable dominance;
- no unnecessary high-skill barbell default;
- 7–9 main exercises when feasible.

### Beginner
Still stable-equipment biased, but freer than First Month.

### Intermediate
Barbell/Dumbbell/Machine/Cable/Smith all available.

### Advanced
- advanced variations appear;
- real superset;
- real drop set.

### Supplemental
- 8 main + 2 supplemental => `main_exercise_count == 8`;
- 0/1/2 supplemental valid;
- 3 invalid;
- supplemental always last.

### Prescription
Across 17 templates, prescriptions are materially diverse by role/level and are not overwhelmingly identical 3×8–12/RIR2.

### Admin
Reject:
- placeholder;
- inactive;
- non-programmable;
- incompatible exercise.

Accept:
- real active programmable compatible exercise.

### Seed
- initial creation works;
- reseed is idempotent;
- admin edits survive;
- admin deletion/disable survives normal reseed.

### Metadata
Known tag mismatches such as T03 are corrected and consistency checks pass.

### Slugs
Every template slot resolves to a real valid exercise or a valid level-aware resolution path.

### Regression
Existing safety, injury, equipment, substitution, recovery, volume, duration, and deterministic-selection behavior must continue to pass.

---

# 20. Final review by Sol

Before saying Done:

1. inspect `git diff`;
2. ensure no unrelated file changed;
3. ensure public canonical template count is still 17;
4. ensure no accidental duplicate level-specific templates were added;
5. ensure all changed template exercise references resolve;
6. ensure placeholders are not executable;
7. ensure seed does not overwrite admin changes;
8. ensure normal sessions prefer 7–9 main exercises;
9. ensure 0–2 supplemental exercises are handled correctly;
10. ensure Advanced methods are real, not metadata-only.

---

# 21. Final output — concise only

Return:

1. files changed;
2. one-line purpose of each;
3. tests run + pass/fail summary;
4. confirmation: `canonical templates = 17`;
5. list of corrected metadata/tag issues;
6. any slug replacements discovered;
7. seed behavior summary;
8. four sample sessions:
   - First Month
   - Beginner
   - Intermediate
   - Advanced

For each sample show only:
- main exercise count;
- supplemental count;
- equipment distribution;
- exercise names;
- for Advanced: superset/drop-set markers.

Do not produce a long narrative.

If something remains unresolved, state it explicitly instead of hiding it.
