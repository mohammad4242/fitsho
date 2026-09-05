# Fitsho Training Template Catalog Replacement

## Scope

This task is limited to the **Training Template Catalog only**.

Do NOT modify the Program Engine logic.

Do NOT modify:

- `workouts/program_engine` generation logic
- `split_selector.py`
- Program Engine rulesets
- workout ranking logic
- workout personalization logic
- injury/safety logic
- recovery logic
- volume-target logic
- equipment filtering logic
- exercise substitution logic
- profile compatibility rules
- SplitType behavior
- workout generator architecture

The goal is only:

1. Remove the existing 49 legacy Fitsho training-template records.
2. Replace them with exactly 17 new canonical training templates defined below.
3. Link every exercise inside those 17 templates to a real existing exercise in Fitsho's Exercise Library.
4. Store complete program guidance/rationale for each template.
5. Make only the minimum backend/database/frontend changes required for the Training Template Catalog itself to work correctly.

---

# 1. Critical deletion rule

The existing **49 Fitsho Training Template records must be physically removed from the database**.

Do not merely set:

```text
is_active = false
```

The 49 old catalog templates must be deleted from `training_program_templates`.

Their owned template days and template slots should be removed through the existing safe cascade behavior.

IMPORTANT:

- These 49 records are **training templates**, not Exercise Library movements.
- Do NOT delete real rows from the `exercises` table just because an old template used them.
- Do NOT delete user workout history.
- Do NOT delete unrelated manually-created/admin-created templates unless they are part of the current Fitsho 49-template seeded catalog.
- Determine the exact legacy 49 template rows from the current repository/database before deleting them.
- Use the current Fitsho seed source metadata and/or exact legacy seed slugs as the ownership boundary.

Final acceptance:

```text
legacy_fitsho_template_count = 0
new_fitsho_template_count = 17
```

There must NOT be:

```text
17 active + 49 inactive
```

There must be exactly 17 canonical Fitsho catalog templates after replacement.

---

# 2. Do not redesign the template architecture

Do NOT introduce a major template architecture refactor for this task.

In particular:

- do not replace the current template model with a new multi-level variant architecture;
- do not redesign Program Engine/template resolution;
- do not introduce a new split-selection system;
- do not alter Program Engine behavior to make these templates selectable.

Use the current Training Template architecture as much as possible.

If the current database model requires one concrete template row per `training_level`, do NOT redesign the entire application merely to solve that.

Instead, preserve the current architecture and implement the 17 approved catalog structures in the least invasive way possible.

The end result that matters for this task is the Training Template Catalog and its 17 approved canonical structures.

If the existing schema mechanically requires internal level-specific seed representation, keep that implementation detail private to the current catalog system and do not alter the Program Engine.

---

# 3. Global Training Template rules

All 17 templates must follow these rules.

## 3.1 Real Exercise Library linkage

Every exercise inside every template must link to a real exercise already present in Fitsho's Exercise Library.

Required:

```text
exercise_id != NULL
exercise.is_active == true
exercise.is_programmable == true
```

Prefer exact canonical slugs listed in this document.

Do NOT:

- create a fake movement;
- create a placeholder movement;
- create a new exercise merely to satisfy a template;
- fuzzy-match a movement name;
- silently change one movement into a different movement;
- use a template-only placeholder if a real exercise exists.

If an exact slug in this document cannot be found in the current Exercise Library:

1. inspect the current Exercise Library;
2. find whether the same exercise exists under another real slug/name;
3. use the real existing library record only if it is clearly the same movement;
4. if no real equivalent exists, stop and report the missing exercise instead of inventing one.

---

## 3.2 Exercise naming

User-facing movement names should come from the linked Exercise Library row.

The template should use the real Fitsho exercise:

```text
exercise_id
slug
name_en
name_fa
```

Do not maintain duplicate fake names that can drift away from the Exercise Library.

---

## 3.3 Exercise order

Mandatory coaching order:

1. Larger muscle groups before smaller muscle groups.
2. Within one muscle group, compound/multi-joint work before isolation work.
3. Do not scatter one muscle's work across the session without a good reason.
4. Keep muscle blocks coherent.

Example Upper order:

```text
Chest
Back
Shoulders
Biceps
Triceps
Core
```

Within chest:

```text
Chest compound
Chest compound
Chest isolation
```

not:

```text
Chest compound
Shoulder
Chest isolation
```

---

## 3.4 Full Body order

For Full Body sessions, do NOT alternate body parts randomly.

Use coherent blocks:

```text
Lower body block
-> Chest block
-> Back block
-> Shoulders
-> Arms/Core
```

Example acceptable:

```text
Squat
Leg Curl
Chest Press
Row
Lat Pulldown
Shoulder Press
```

Example unacceptable:

```text
Squat
Chest Press
Leg Curl
Row
Leg Extension
Lat Pulldown
```

Finish the planned lower-body work before moving to chest.

---

## 3.5 Program realism

Templates must look like real bodybuilding programs written by a professional coach.

Do not design them merely to satisfy validators.

Avoid:

- excessive exercise count;
- excessive direct volume;
- redundant exercises with the same role;
- random exercise variation;
- unnecessary advanced intensity techniques.

Baseline templates use normal straight sets.

No mandatory:

- drop sets
- rest-pause
- supersets
- forced failure

---

# 4. Level-based exercise policy

The current catalog architecture should be used with the following movement philosophy wherever the current model supports level-specific templates/rows.

## First Month

Use simple, stable, general movements.

Prefer:

- Smith/machine for squat-type primary work;
- machine chest presses;
- stable machine/cable rows;
- technically simple movements;
- conservative prescriptions.

Especially:

```text
Smith Chair Squat
Lever Lying Chest Press
Lever Incline Hammer Chest Press
Smith Machine Shoulder Press
```

No specialization template by default.

No advanced intensity techniques.

Target RIR roughly 3.

---

## Beginner

Use stable fundamental movement patterns.

Prefer:

- Smith/machine for primary squat/chest roles;
- machine/cable accessories;
- simple free-weight movements when appropriate;
- technically manageable movements.

Target RIR roughly 2.

---

## Intermediate

Keep the same fundamental movement patterns but move primary work increasingly toward:

- barbell
- dumbbell
- cable

Examples:

```text
Barbell Back Squat
Barbell Bench Press
Dumbbell Incline Bench Press
Barbell Bent-Over Row
Seated Dumbbell Shoulder Press
Cable Lateral Raise
```

Machines remain completely valid for isolation/accessory work.

---

## Advanced

All appropriate modalities are allowed:

- barbell
- dumbbell
- cable
- machine

Choose movements for:

- stimulus quality;
- fatigue cost;
- stability;
- variation;
- practical bodybuilding use.

Advanced does NOT mean mandatory failure or intensity methods.

---

# 5. Canonical real Exercise Library mappings

Before editing the templates, verify these slugs against the current Fitsho Exercise Library.

Use the exact real library row whenever available.

## Lower body

### Smith Chair Squat
```text
fedb-0750-smith-chair-squat
```

### Barbell Back Squat
```text
fedb-1435-barbell-back-squat
```

### Barbell Front Squat
```text
fedb-0042-barbell-front-squat
```

### Leg Press
```text
leg-press
```

### Lever Leg Extension
```text
fedb-0585-lever-leg-extension
```

### Dumbbell Lunge
```text
dumbbell-lunge
```

### Romanian Deadlift
```text
romanian-deadlift
```

### Lever Seated Leg Curl
```text
fedb-0599-lever-seated-leg-curl
```

### Lever Lying Leg Curl
```text
fedb-0586-lever-lying-leg-curl
```

### Glute Bridge
```text
glute-bridge
```

### Lever Standing Calf Raise
```text
fedb-0605-lever-standing-calf-raise
```

### Standing Calf Raise
```text
standing-calf-raise
```

---

## Chest

### Lever Lying Chest Press
```text
fedb-0577-lever-lying-chest-press
```

### Lever Incline Hammer Chest Press
```text
fedb-1299-lever-incline-hammer-chest-press
```

### Barbell Bench Press
```text
fedb-0025-barbell-bench-press
```

### Dumbbell Bench Press
```text
dumbbell-bench-press
```

### Dumbbell Incline Bench Press
```text
fedb-0314-dumbbell-incline-bench-press
```

### Barbell Incline Bench Press
```text
fedb-0047-barbell-incline-bench-press
```

### Pec Deck Fly
```text
fedb-drv-lever-pec-deck-fly-pec-deck-fly
```

### Cable Standing Fly
```text
fedb-1269-cable-standing-fly
```

Never use a fake/simple placeholder `pec-deck-fly` if the real FEDB row exists.

---

## Back

### Lever High Row
```text
fedb-0581-lever-high-row
```

### Barbell Bent-Over Row
```text
barbell-bent-over-row
```

### Seated Cable Row (V-Grip)
```text
fedb-0208-seated-cable-row-v-grip
```

### Dumbbell Hammer Grip Incline Bench Row
```text
fedb-1330-dumbbell-hammer-grip-incline-bench-row
```

### Cable Close Grip Lat Pulldown
```text
fedb-0974-cable-close-grip-lat-pulldown
```

### Cable Straight Arm Pulldown
```text
fedb-0238-cable-straight-arm-pulldown
```

---

## Shoulders

### Smith Machine Shoulder Press
```text
smith-machine-shoulder-press
```

### Seated Dumbbell Shoulder Press
```text
fedb-0289-seated-dumbbell-shoulder-press
```

### Military Press
```text
fedb-0553-military-press
```

### Lever Lateral Raise
```text
fedb-0584-lever-lateral-raise
```

### Cable Lateral Raise
```text
fedb-0178-cable-lateral-raise
```

### Lever Seated Reverse Fly
```text
fedb-0602-lever-seated-reverse-fly
```

### Cable Crossover Reverse Fly
```text
fedb-0154-cable-crossover-reverse-fly
```

---

## Biceps

### Lever Preacher Curl
```text
fedb-0592-lever-preacher-curl
```

### Dumbbell Curl
```text
dumbbell-curl
```

### Hammer Curl
```text
hammer-curl
```

### Barbell Curl
```text
barbell-curl
```

---

## Triceps

### Cable Triceps Pushdown
```text
fedb-1723-cable-triceps-pushdown
```

### Cable Rope Triceps Pushdown
```text
fedb-0200-cable-rope-triceps-pushdown
```

### Cable Rope Overhead Triceps Extension
```text
fedb-0194-cable-rope-overhead-triceps-extension
```

---

## Traps

### Barbell Shrug
```text
fedb-0095-barbell-shrug
```

---

## Core

### Lever Seated Crunch
```text
fedb-1452-lever-seated-crunch
```

### Front Plank
```text
fedb-0464-front-plank
```

### Side Plank
```text
fedb-0705-side-plank
```

---

# 6. Prescription guidelines

Use the current template fields for:

```text
sets
rep_min
rep_max
target_rir
rest_seconds
```

Keep prescriptions simple.

## First Month

Compound:
```text
2–3 sets
8–12 reps
RIR 3
90–120 sec
```

Isolation:
```text
2 sets
10–15 reps
RIR 3
60–75 sec
```

## Beginner

Compound:
```text
3 sets
8–12 reps
RIR 2
90–120 sec
```

Isolation:
```text
2–3 sets
10–15 reps
RIR 2
60–75 sec
```

## Intermediate

Primary compound:
```text
3–4 sets
6–10 reps
RIR 2
120–150 sec
```

Secondary compound:
```text
2–3 sets
8–12 reps
RIR 2
90–120 sec
```

Isolation:
```text
2–3 sets
10–20 reps
RIR 1–2
60–90 sec
```

## Advanced

Primary compound:
```text
3–4 sets
6–10 reps
RIR 1–2
120–150 sec
```

Secondary compound:
```text
2–3 sets
8–12 reps
RIR 1–2
90–120 sec
```

Isolation:
```text
2–3 sets
10–20 reps
RIR 1
60–90 sec
```

Never exceed 4 working sets for one exercise in these catalog templates.

---

# 7. The 17 approved template structures

These are the ONLY approved canonical catalog structures for this replacement.

Do not add additional template families.

---

# T01 — 2-Day Full Body A/B

Canonical structure:

## Day A

Lower body:
1. Smith Chair Squat / Barbell Back Squat depending level
2. Lever Seated Leg Curl

Chest:
3. Lever Lying Chest Press / Barbell Bench Press depending level

Back:
4. Lever High Row / Barbell Bent-Over Row depending level
5. Cable Close Grip Lat Pulldown

Shoulders:
6. Smith Machine Shoulder Press / Seated Dumbbell Shoulder Press depending level

## Day B

Lower body:
1. Leg Press
2. Romanian Deadlift

Chest:
3. Lever Incline Hammer Chest Press / Dumbbell Incline Bench Press depending level

Back:
4. Seated Cable Row (V-Grip)
5. Cable Close Grip Lat Pulldown

Shoulders:
6. Lever Lateral Raise / Cable Lateral Raise depending level

Eligible concept:
- First Month
- Beginner
- Intermediate

Guidance:
- Two full-body sessions for users training twice weekly.
- Finish lower-body block before upper-body work.
- Keep total session length practical.
- Progress through reps before load.
- Keep several recovery days between sessions when possible.

---

# T02 — 3-Day Upper / Lower / Full

## Day 1 — Upper

Chest:
1. Flat Chest Press
2. Incline Chest Press

Back:
3. Row
4. Lat Pulldown

Shoulders:
5. Shoulder Press
6. Lateral Raise

## Day 2 — Lower

Quadriceps:
1. Squat
2. Leg Press

Posterior:
3. Romanian Deadlift
4. Leg Curl

Calves/Core:
5. Calf Raise
6. Core

## Day 3 — Full Body

Lower:
1. Leg Press
2. Leg Curl

Chest:
3. Flat Chest Press

Back:
4. Seated Cable Row
5. Lat Pulldown

Shoulders:
6. Lateral Raise

Eligible concept:
- First Month
- Beginner
- Intermediate
- Advanced

Guidance:
- Balanced 3-day structure.
- Full Body supplies another broad exposure.
- Keep Full Body body-part blocks contiguous.
- Avoid unnecessary extra arm work when session is already complete.
- Level controls exercise difficulty and loading.

---

# T03 — 3-Day Upper / Lower / Upper

## Day 1 — Upper A

Chest:
1. Flat Chest Press
2. Incline Chest Press

Back:
3. Row
4. Lat Pulldown

Shoulders:
5. Shoulder Press
6. Lateral Raise

Arms:
7. Biceps Curl
8. Triceps Pushdown

## Day 2 — Lower

1. Squat
2. Leg Press
3. Romanian Deadlift
4. Leg Curl
5. Calf Raise
6. Core

## Day 3 — Upper B

Chest:
1. Incline Chest Press
2. Flat Chest Press variation

Back:
3. Seated Cable Row
4. Lat Pulldown

Shoulders:
5. Rear Delt Fly
6. Lateral Raise

Arms:
7. Hammer Curl
8. Overhead Triceps Extension

Eligible concept:
- Beginner
- Intermediate
- Advanced

Guidance:
- Upper-priority three-day template.
- Two upper sessions should use planned variation.
- Do not overload the single lower session.
- Keep direct arm work after major upper-body muscles.
- Use only as an upper-priority catalog option.

---

# T04 — 3-Day Lower / Upper / Lower

## Day 1 — Lower A

1. Squat
2. Leg Press
3. Romanian Deadlift
4. Leg Curl
5. Calf Raise
6. Core

## Day 2 — Upper

1. Flat Chest Press
2. Incline Chest Press
3. Row
4. Lat Pulldown
5. Shoulder Press
6. Lateral Raise
7. Biceps Curl
8. Triceps Pushdown

## Day 3 — Lower B

1. Leg Press
2. Dumbbell Lunge
3. Romanian Deadlift
4. Lying Leg Curl
5. Calf Raise
6. Core

Eligible concept:
- Beginner
- Intermediate
- Advanced

Guidance:
- Lower-priority three-day template.
- Two lower sessions must not be identical.
- Compound movements before isolation.
- Upper session remains complete but compact.
- Do not exceed reasonable single-session lower-body volume.

---

# T05 — 4-Day Upper / Lower ×2

## Day 1 — Upper A

1. Flat Chest Press
2. Incline Chest Press
3. Row
4. Lat Pulldown
5. Shoulder Press
6. Lateral Raise

## Day 2 — Lower A

1. Squat
2. Leg Press
3. Romanian Deadlift
4. Leg Curl
5. Calf Raise
6. Core

## Day 3 — Upper B

1. Incline Chest Press
2. Flat Chest Press variation
3. Seated Cable Row
4. Lat Pulldown
5. Rear Delt Fly
6. Lateral Raise

## Day 4 — Lower B

1. Squat/Front Squat depending level
2. Leg Extension
3. Romanian Deadlift
4. Lying Leg Curl
5. Calf Raise
6. Core

Eligible concept:
- First Month
- Beginner
- Intermediate
- Advanced

Guidance:
- Main balanced four-day template.
- Each region receives two weekly sessions.
- A/B sessions should have controlled movement variation.
- Machines remain useful even for experienced levels.
- No advanced techniques required.

---

# T06 — 4-Day 3 Upper + 1 Lower

## Day 1 — Upper A: Chest + Back

1. Flat Chest Press
2. Incline Chest Press
3. Row
4. Lat Pulldown
5. Lateral Raise
6. Triceps Pushdown

## Day 2 — Lower

1. Squat
2. Leg Press
3. Romanian Deadlift
4. Leg Curl
5. Calf Raise
6. Core

## Day 3 — Upper B: Shoulders + Arms

1. Shoulder Press
2. Lateral Raise
3. Rear Delt Fly
4. Biceps Curl
5. Hammer Curl
6. Triceps Pushdown
7. Overhead Triceps Extension

## Day 4 — Upper C: Chest + Back Variation

1. Incline Chest Press
2. Flat Chest Press variation
3. Seated Cable Row
4. Lat Pulldown
5. Biceps Curl
6. Core

Eligible concept:
- Beginner
- Intermediate
- Advanced

Guidance:
- Upper-priority catalog structure.
- Do not make all three upper days identical.
- Dedicated shoulder/arms day prevents excessive chest/back repetition.
- One lower session remains a complete lower-body session.
- Use planned exercise variation.

---

# T07 — 4-Day 3 Lower + 1 Upper

## Day 1 — Lower A: Quad Bias

1. Squat
2. Leg Press
3. Leg Curl
4. Calf Raise
5. Core

## Day 2 — Upper

1. Flat Chest Press
2. Incline Chest Press
3. Row
4. Lat Pulldown
5. Shoulder Press
6. Lateral Raise
7. Biceps Curl
8. Triceps Pushdown

## Day 3 — Lower B: Posterior Bias

1. Romanian Deadlift
2. Lying Leg Curl
3. Glute Bridge
4. Calf Raise
5. Core

## Day 4 — Lower C: Quad + Glute

1. Squat/Leg Press
2. Leg Extension
3. Glute Bridge
4. Calf Raise
5. Core

Eligible concept:
- Beginner
- Intermediate
- Advanced

Guidance:
- Lower-priority catalog structure.
- Rotate quad/hamstring/glute emphasis.
- Do not make all three lower sessions heavy for all lower muscles.
- Keep upper day complete and efficient.
- Use only as a lower-priority template option.

---

# T08 — 4-Day Push / Pull / Quads / Posterior

Eligible:
- Intermediate
- Advanced

## Day 1 — Push

1. Flat Chest Press
2. Incline Chest Press
3. Shoulder Press
4. Lateral Raise
5. Triceps Pushdown
6. Core

## Day 2 — Pull

1. Row
2. Lat Pulldown
3. Biceps Curl
4. Barbell Shrug
5. Core

## Day 3 — Quads

1. Squat
2. Leg Press
3. Leg Extension
4. Leg Curl
5. Calf Raise
6. Core

## Day 4 — Posterior

1. Romanian Deadlift
2. Lying Leg Curl
3. Glute Bridge
4. Dumbbell Lunge
5. Calf Raise
6. Core

Guidance:
- Intermediate/advanced bodybuilding split.
- Push and Pull remain compound-led.
- Quad and posterior lower-body days have distinct purposes.
- Do not mix isolation before later compounds for the same muscle.
- Keep session size practical.

---

# T09 — 5-Day PPL + Upper + Lower

Eligible:
- Intermediate
- Advanced

## Day 1 — Push

1. Flat Chest Press
2. Incline Chest Press
3. Shoulder Press
4. Lateral Raise
5. Triceps Pushdown
6. Core

## Day 2 — Pull

1. Row
2. Lat Pulldown
3. Biceps Curl
4. Hammer Curl
5. Barbell Shrug
6. Core

## Day 3 — Legs

1. Squat
2. Leg Press
3. Romanian Deadlift
4. Leg Curl
5. Calf Raise
6. Core

## Day 4 — Upper

1. Flat Chest Press
2. Seated Cable Row
3. Lat Pulldown
4. Lateral Raise
5. Biceps Curl
6. Triceps Pushdown

## Day 5 — Lower

1. Squat/Leg Press
2. Lying Leg Curl
3. Glute Bridge
4. Calf Raise
5. Core

Guidance:
- Balanced five-day bodybuilding structure.
- PPL gives focused sessions.
- Upper/Lower adds another broad exposure.
- Avoid redundant extra exercises.
- Keep variation purposeful.

---

# T10 — 5-Day Classic Body-Part

Eligible:
- Intermediate
- Advanced

## Day 1 — Chest

1. Flat Chest Press
2. Incline Chest Press
3. Cable/Pec Deck Fly
4. Triceps Pushdown
5. Core

## Day 2 — Back

1. Row
2. Lat Pulldown
3. Seated Cable Row
4. Biceps Curl
5. Core

## Day 3 — Legs

1. Squat
2. Leg Press
3. Romanian Deadlift
4. Leg Curl
5. Calf Raise

## Day 4 — Shoulders

1. Shoulder Press
2. Lateral Raise
3. Rear Delt Fly
4. Barbell Shrug
5. Core

## Day 5 — Arms

1. Biceps Curl
2. Hammer Curl
3. Triceps Pushdown
4. Overhead Triceps Extension
5. Core

Guidance:
- Classic body-part organization.
- Major compounds first on dedicated days.
- Keep direct volume controlled.
- Arm work follows larger-muscle training throughout the week.
- No mandatory intensity methods.

---

# T11 — 5-Day PPL + Upper Priority + Lower Priority

Eligible:
- Intermediate
- Advanced

## Day 1 — Push

1. Flat Chest Press
2. Incline Chest Press
3. Shoulder Press
4. Lateral Raise
5. Triceps Pushdown
6. Core

## Day 2 — Pull

1. Row
2. Lat Pulldown
3. Biceps Curl
4. Hammer Curl
5. Barbell Shrug
6. Core

## Day 3 — Legs

1. Squat
2. Leg Press
3. Romanian Deadlift
4. Leg Curl
5. Calf Raise
6. Core

## Day 4 — Upper Priority

1. Flat Chest Press
2. Incline Chest Press
3. Row
4. Lat Pulldown
5. Lateral Raise
6. Core

## Day 5 — Lower Priority

1. Squat
2. Leg Press
3. Romanian Deadlift
4. Leg Curl
5. Calf Raise
6. Core

Guidance:
- Higher-volume alternative to T09.
- Priority days are meaningful second exposures.
- Do not turn priority into excessive per-session volume.
- Use straightforward bodybuilding prescriptions.
- Maintain compound-before-isolation order.

---

# T12 — 5-Day Chest Specialization

Eligible:
- Intermediate
- Advanced

## Day 1 — Chest + Triceps

Chest:
1. Flat Chest Press
2. Incline Chest Press
3. Chest Fly

Triceps:
4. Triceps Pushdown
5. Overhead Triceps Extension

Core:
6. Core

## Day 2 — Back + Biceps

1. Row
2. Lat Pulldown
3. Biceps Curl
4. Hammer Curl
5. Rear Delt Fly

## Day 3 — Legs

1. Squat
2. Leg Press
3. Romanian Deadlift
4. Leg Curl
5. Calf Raise
6. Core

## Day 4 — Shoulders + Arms

1. Shoulder Press
2. Lateral Raise
3. Rear Delt Fly
4. Biceps Curl
5. Triceps Pushdown
6. Core

## Day 5 — Chest Priority

1. Flat Chest Press
2. Incline Chest Press
3. Chest Fly
4. Core
5. Calf Raise

Guidance:
- Chest receives two direct weekly sessions.
- Keep compounds before fly work.
- Do not exceed sensible direct chest volume.
- Other muscle groups remain trained.
- Use only for a chest-priority catalog option.

---

# T13 — 5-Day Back Specialization

Eligible:
- Intermediate
- Advanced

## Day 1 — Back + Biceps

1. Row
2. Lat Pulldown
3. Seated Cable Row
4. Biceps Curl
5. Hammer Curl
6. Core

## Day 2 — Chest + Triceps

1. Flat Chest Press
2. Incline Chest Press
3. Triceps Pushdown
4. Overhead Triceps Extension
5. Core

## Day 3 — Legs

1. Squat
2. Leg Press
3. Romanian Deadlift
4. Leg Curl
5. Calf Raise
6. Core

## Day 4 — Shoulders + Arms

1. Shoulder Press
2. Lateral Raise
3. Rear Delt Fly
4. Biceps Curl
5. Triceps Pushdown
6. Core

## Day 5 — Back Priority

1. Row
2. Lat Pulldown
3. Cable Straight Arm Pulldown
4. Core
5. Calf Raise

Guidance:
- Back receives two direct weekly sessions.
- Include both horizontal and vertical pulling.
- Straight-arm pulldown is accessory work after compounds.
- Biceps follow back work.
- Use only for a true back-priority catalog option.

---

# T14 — 5-Day Leg Specialization

Eligible:
- Intermediate
- Advanced

## Day 1 — Quads

1. Squat
2. Leg Press
3. Leg Extension
4. Leg Curl
5. Calf Raise
6. Core

## Day 2 — Chest

1. Flat Chest Press
2. Incline Chest Press
3. Chest Fly
4. Triceps Pushdown
5. Core

## Day 3 — Back

1. Row
2. Lat Pulldown
3. Seated Cable Row
4. Biceps Curl
5. Core

## Day 4 — Shoulders + Arms

1. Shoulder Press
2. Lateral Raise
3. Rear Delt Fly
4. Biceps Curl
5. Triceps Pushdown
6. Core

## Day 5 — Posterior Chain

1. Romanian Deadlift
2. Lying Leg Curl
3. Glute Bridge
4. Dumbbell Lunge
5. Calf Raise
6. Core

Guidance:
- Split quad and posterior emphasis.
- Keep lower-body compounds before isolation.
- Hamstrings receive both hinge and curl patterns.
- Do not turn specialization into excessive volume.
- Use only for leg-priority catalog use.

---

# T15 — 6-Day PPL ×2

Eligible:
- Intermediate
- Advanced

## Day 1 — Push A

1. Flat Chest Press
2. Incline Chest Press
3. Shoulder Press
4. Lateral Raise
5. Triceps Pushdown
6. Core

## Day 2 — Pull A

1. Row
2. Lat Pulldown
3. Biceps Curl
4. Hammer Curl
5. Barbell Shrug
6. Core

## Day 3 — Legs A

1. Squat
2. Leg Press
3. Romanian Deadlift
4. Leg Curl
5. Calf Raise
6. Core

## Day 4 — Push B

1. Flat/alternative Chest Press
2. Chest Fly
3. Shoulder Press
4. Lateral Raise
5. Overhead Triceps Extension
6. Core

Chest block must finish before shoulder work.

## Day 5 — Pull B

1. Seated Cable Row / supported row
2. Lat Pulldown
3. Biceps Curl
4. Hammer Curl
5. Barbell Shrug
6. Core

## Day 6 — Legs B

1. Romanian Deadlift
2. Lying Leg Curl
3. Front Squat
4. Glute Bridge
5. Calf Raise
6. Core

Guidance:
- Two planned PPL rotations.
- A/B variation should be purposeful.
- Push B must complete chest before shoulders.
- Posterior work should not place isolation before later same-muscle compounds.
- No mandatory advanced techniques.

---

# T16 — 6-Day Advanced Body-Part

Eligible:
- Advanced

## Day 1 — Chest

1. Flat Chest Press
2. Incline Chest Press
3. Chest Fly
4. Triceps Pushdown
5. Core

## Day 2 — Back

1. Row
2. Lat Pulldown
3. Seated Cable Row
4. Biceps Curl
5. Core

## Day 3 — Quads

1. Squat
2. Leg Press
3. Leg Extension
4. Leg Curl
5. Calf Raise

## Day 4 — Shoulders

1. Shoulder Press
2. Lateral Raise
3. Rear Delt Fly
4. Barbell Shrug
5. Core

## Day 5 — Arms

1. Barbell Curl
2. Hammer Curl
3. Cable Triceps Pushdown
4. Overhead Triceps Extension
5. Core

## Day 6 — Hamstrings + Glutes

1. Romanian Deadlift
2. Lying Leg Curl
3. Glute Bridge
4. Dumbbell Lunge
5. Calf Raise
6. Core

Guidance:
- Advanced body-part catalog option.
- Each day has a clear focus.
- Major compounds before isolation.
- Use all appropriate equipment modalities.
- Do not automatically add drop sets/rest-pause/failure.

---

# T17 — 6-Day Balanced Specialization

Eligible:
- Advanced

## Day 1 — Push

1. Flat Chest Press
2. Incline Chest Press
3. Shoulder Press
4. Lateral Raise
5. Triceps Pushdown
6. Core

## Day 2 — Pull

1. Row
2. Lat Pulldown
3. Biceps Curl
4. Hammer Curl
5. Barbell Shrug
6. Core

## Day 3 — Legs

1. Squat
2. Leg Press
3. Romanian Deadlift
4. Leg Curl
5. Calf Raise
6. Core

## Day 4 — Chest Priority

1. Flat Chest Press
2. Incline Chest Press
3. Chest Fly
4. Triceps Pushdown
5. Core

## Day 5 — Back + Delts Priority

Back:
1. Seated Cable Row / supported row
2. Lat Pulldown
3. Cable Straight Arm Pulldown

Shoulders:
4. Shoulder Press
5. Lateral Raise
6. Rear Delt Fly

Core:
7. Core

## Day 6 — Legs Priority

1. Squat/Front Squat
2. Leg Press
3. Dumbbell Lunge
4. Romanian Deadlift
5. Lying Leg Curl
6. Calf Raise
7. Core

Guidance:
- Advanced high-frequency balanced option.
- Second exposures have clear emphasis.
- Keep chest/back/lower volume controlled.
- Use planned movement variation.
- Do not add mandatory intensity techniques.

---

# 8. Approved catalog distribution

The canonical catalog contains these 17 structures:

```text
T01  2D Full Body A/B

T02  3D Upper / Lower / Full
T03  3D Upper / Lower / Upper
T04  3D Lower / Upper / Lower

T05  4D Upper / Lower ×2
T06  4D 3 Upper + 1 Lower
T07  4D 3 Lower + 1 Upper
T08  4D Push / Pull / Quads / Posterior

T09  5D PPL + Upper + Lower
T10  5D Classic Body-Part
T11  5D PPL + Upper Priority + Lower Priority
T12  5D Chest Specialization
T13  5D Back Specialization
T14  5D Leg Specialization

T15  6D PPL ×2
T16  6D Advanced Body-Part
T17  6D Balanced Specialization
```

Do not add an 18th canonical structure.

Do not keep any of the 49 legacy Fitsho catalog templates.

---

# 9. Program guidance/rationale

Each of the 17 templates must store meaningful bilingual guidance using the current template fields available in the repository.

Where the current schema already supports:

```text
description_en
description_fa
programming_rationale
```

populate them.

Each template should include guidance covering:

1. Structure
2. Exercise order
3. Volume
4. Progression
5. Recovery/safety

Use the specific Guidance section written under T01–T17.

Do not write generic marketing copy.

Do not modify Program Engine progression/recovery rules.

This is descriptive template guidance only.

---

# 10. Minimal backend/catalog work

Inspect the current implementation before editing.

Likely relevant files include:

```text
backend/app/training_templates/seed_data.py
backend/app/training_templates/service.py
backend/app/training_templates/models.py
backend/app/training_templates/catalog_placeholders.py
backend/app/training_templates/admin_service.py
backend/app/admin/schemas.py
backend/app/admin/router.py
```

Only modify files that are actually necessary for catalog replacement.

Do not modify Program Engine files.

Required catalog behavior:

1. Replace old seed definitions with the new approved template catalog.
2. Resolve every template movement to a real Exercise Library row.
3. Do not create template-only placeholders for the new catalog.
4. Physically remove the 49 legacy Fitsho template rows.
5. Seed the new catalog idempotently.
6. Preserve unrelated user/admin templates.
7. Preserve user workout history.
8. Keep the existing data model unless a tiny catalog-only fix is truly required.

---

# 11. Frontend scope

Only modify frontend if required so the Admin Training Template catalog correctly displays/edits the new catalog.

Relevant files may include:

```text
frontend/src/features/admin/AdminTrainingTemplatesPage.tsx
frontend/src/features/admin/AdminTrainingTemplateEditorPage.tsx
frontend/src/features/admin/types.ts
frontend/src/features/admin/api.ts
```

Do not redesign unrelated frontend behavior.

The UI should use linked Exercise Library names/media/data rather than invented template movement names where the current API supports it.

---

# 12. Required tests

Update existing Training Template tests to reflect the new catalog.

Do not modify Program Engine tests unless they fail solely because they directly assert the old catalog data and can be updated without changing engine behavior.

Required tests:

1. New catalog seeds successfully.
2. Seeding is idempotent.
3. All 49 legacy Fitsho template records are physically gone.
4. New canonical catalog contains the approved 17 structures.
5. Every new template slot links to a real exercise.
6. Every linked exercise is active and programmable.
7. No new template slot uses a `fitsho_training_template` placeholder.
8. Every template day has a reasonable number of movements.
9. Program descriptions/guidance are populated.
10. Exercise order follows the rules in this document.
11. Full Body templates preserve coherent body-part blocks.
12. Admin template API still works.
13. Admin frontend tests still pass if frontend was touched.

Do not change engine behavior just to satisfy catalog tests.

---

# 13. Final database audit

After migration/seed, print:

```text
legacy_fitsho_template_count
new_fitsho_template_count
new_template_day_count
new_template_slot_count
unlinked_new_template_slots
new_template_placeholder_slots
inactive_or_nonprogrammable_linked_exercises
```

Required:

```text
legacy_fitsho_template_count = 0
new_fitsho_template_count = 17 canonical catalog structures
unlinked_new_template_slots = 0
new_template_placeholder_slots = 0
inactive_or_nonprogrammable_linked_exercises = 0
```

Again:

Do NOT delete the real Exercise Library movements.

The hard deletion requirement applies to the **49 old Training Template records** and their owned template day/slot records.

---

# 14. Final verification

Run all relevant Training Template catalog tests.

Run backend tests for the areas touched.

Run frontend tests only if frontend code was touched.

Do NOT make unrelated changes until tests pass.

---

# 15. Required final report from Luna

At the end report:

## Legacy removal

```text
number of old Fitsho template rows found
number physically deleted
number remaining
```

Required remaining:

```text
0
```

## New catalog

List all 17 approved structures and their actual database records.

## Exercise linkage

Report:

```text
total new template slots
linked slots
unlinked slots
placeholder slots
```

Required:

```text
unlinked = 0
placeholder = 0
```

## Files changed

List every changed file.

Clearly separate:

```text
Training Template Catalog changes
Database cleanup/migration
Admin API/frontend changes
Tests
```

## Explicit engine confirmation

State:

```text
No Program Engine behavior was changed.
No split selector behavior was changed.
No Program Engine ruleset was changed.
```

If any Program Engine file was modified for any reason, explain why before declaring the task complete.

## Test results

Provide exact commands and pass/fail result.

Do not declare completion until the Training Template Catalog replacement is fully verified.
