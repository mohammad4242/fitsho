# Fitsho Default Program Library Implementation Task

Work on the **Fitsho** project.

## Goal

Complete the Fitsho **Default Program Library** with the approved **25 workout programs**, and link every exercise in every program to the real corresponding exercise in the existing Fitsho **Exercise Library**.

This task is **not about changing the Program Engine**.

Do not modify automatic program-selection logic unless it is technically unavoidable for compatibility with the existing architecture.

The primary scope of this task is:

- Default Program Library
- Training Templates
- Default program definitions
- Program days
- Program exercise prescriptions
- Correct linking between Program Exercises and Exercise Library records

---

# Step 0 — Non-Negotiable Rules

1. Do not create any new workout Structure.

2. Do not create any new Level.

3. Do not create fake or duplicate Exercise records.

4. Do not link exercises using fuzzy matching based only on Persian or English display names.

5. Every Program Exercise must reference an existing Exercise Library record, preferably through a stable slug or the project's canonical FK/reference mechanism.

6. If one of the requested exercise slugs does not actually exist in the current database/seed data:
   - investigate why,
   - find the closest real Exercise with the same movement pattern and intended muscle target,
   - use the replacement only when necessary,
   - clearly report the replacement in the final report.

7. Every program must exactly comply with Fitsho's existing Training Template structures.

8. Do not violate the current `supported_levels` configuration of any template.

9. Do not create unsupported template-level combinations just to increase the number of programs.

10. The workout designs below have already been approved.
    Do not arbitrarily redesign:
    - day structures,
    - day ordering,
    - primary movement selection,
    - or overall program structure.

11. Before editing code, inspect the current schema, models, services, seed logic, and Training Template implementation.

12. Follow the existing Fitsho architecture.
    Do not introduce a parallel architecture for default programs.

13. Prevent duplicate programs.
    If equivalent default programs already exist, update/replace them idempotently rather than inserting duplicates.

14. Create a database migration only if the schema truly requires it.
    Do not create a migration merely to seed these programs.

15. Do not format unrelated files.

16. Do not perform unrelated refactors.

17. Do not add new dependencies unless absolutely necessary.

18. Run all relevant tests before finishing.

---

# Step 1 — Inspect the Existing Architecture First

Before making any edits, inspect at least the following areas:

```text
backend/app/training_templates/
```

Also locate and inspect:

- Training Template models
- Training Template schemas
- `seed_data.py`
- Default Program Library seed/service logic
- Exercise model
- Exercise Library lookup/link mechanism
- Program model
- Program Day model
- Program Exercise model
- Exercise relationships
- Level enums
- Structure enums
- Day type enums
- `supported_levels`
- existing seed/idempotency mechanisms

Determine exactly how Default Programs are currently stored.

Answer these implementation questions from the codebase before editing:

- Are `TrainingTemplate` and `Program` separate entities?
- How are days represented?
- How are exercises attached to a day?
- Does `ProgramExercise` use:
  - `exercise_id`,
  - `exercise_slug`,
  - another FK,
  - or only plain text?
- Where are:
  - sets,
  - reps,
  - RIR,
  - rest,
  - movement role,
  stored?

Then implement the approved programs according to the **existing architecture**.

Do not create a separate system.

---

# Step 2 — Final Program Matrix

The final Default Program Library for this task must contain exactly:

# **25 Programs**

---

## 2 Training Days — 3 Programs

### Template

`Full Body A/B`

### Supported Levels

1. First Month
2. Beginner
3. Intermediate

Do **not** create an Advanced 2-day Full Body program.

Expected count:

```text
3
```

---

## 3 Training Days — 10 Programs

### Template 1

`Upper / Lower / Full`

Levels:

- First Month
- Beginner
- Intermediate
- Advanced

Count:

```text
4
```

### Template 2

`Upper / Lower / Upper`

Levels:

- Beginner
- Intermediate
- Advanced

Do not create First Month.

Count:

```text
3
```

### Template 3

`Lower / Upper / Lower`

Levels:

- Beginner
- Intermediate
- Advanced

Do not create First Month.

Count:

```text
3
```

Total:

```text
10
```

---

## 4 Training Days — 12 Programs

### Template 1

`Upper / Lower / Upper / Lower`

Levels:

- First Month
- Beginner
- Intermediate
- Advanced

Count:

```text
4
```

### Template 2

`3 Upper + 1 Lower`

Levels:

- Beginner
- Intermediate
- Advanced

Do not create First Month.

Count:

```text
3
```

### Template 3

`3 Lower + 1 Upper`

Levels:

- Beginner
- Intermediate
- Advanced

Do not create First Month.

Count:

```text
3
```

### Template 4

`Push / Pull / Quads / Posterior`

Levels:

- Intermediate
- Advanced

Do not create:

- First Month
- Beginner

Count:

```text
2
```

Total:

```text
12
```

---

## Final Expected Count

```text
2-day programs:  3
3-day programs: 10
4-day programs: 12

TOTAL: 25
```

Before considering the task complete, add an assertion or test that confirms the expected count is exactly:

```text
25
```

---

# Step 3 — Level Philosophy

Preserve the following exercise-selection philosophy.

## First Month

Prioritize:

- machines,
- Smith machine exercises,
- stable movement paths,
- low skill requirements,
- lower coordination requirements.

Avoid unnecessarily complex free-weight movements.

Primary goals:

- adaptation,
- technique learning,
- movement confidence,
- basic coordination.

---

## Beginner

Machines remain important, but progressively introduce:

- dumbbells,
- cables,
- simple free-weight patterns.

Free barbell work should still be relatively limited compared with Intermediate programming.

---

## Intermediate

Introduce more major free-weight compounds, including:

- barbell movements,
- dumbbell compounds,
- cable accessories,
- machine accessories.

The program should reflect higher technical readiness.

---

## Advanced

Advanced programming does **not** require exotic exercises.

Exercise selection may remain similar to Intermediate.

The main progression should come through:

- prescription,
- training volume,
- intensity,
- lower RIR,
- progression demand.

---

# Step 4 — Standard Prescription Rules

The program definitions below use:

```text
P = Primary
S = Secondary
I = Isolation
```

---

## First Month / Beginner

### Primary — P

```text
Sets: 3
Reps: 8-12
Target RIR: approximately 3
```

### Secondary — S

```text
Sets: 3
Reps: 8-12
Target RIR: approximately 3
```

### Isolation — I

```text
Sets: 3
Reps: 10-15
Target RIR: approximately 3
```

If the existing Fitsho prescription system intentionally uses `8-12` for some Beginner isolation exercises for consistency, preserve the existing architecture/convention and report the difference.

---

## Intermediate

### Primary — P

```text
Sets: 3
Reps: 6-10
Target RIR: approximately 2
```

### Secondary — S

```text
Sets: 3
Reps: 8-12
Target RIR: approximately 2
```

### Isolation — I

```text
Sets: 3
Reps: 10-15
Target RIR: approximately 2
```

---

## Advanced

### Primary — P

```text
Sets: 4
Reps: 5-8
Target RIR: approximately 1
```

### Secondary — S

```text
Sets: 3
Reps: 8-12
Target RIR: approximately 2
```

### Isolation — I

```text
Sets: 3
Reps: 10-15
Target RIR: approximately 2
```

If Fitsho stores repetition ranges as separate fields such as:

```text
min_reps
max_reps
```

map these values correctly.

If Fitsho uses another field name for RIR, use the existing model instead of creating a new field.

---

# Step 5 — Approved Exercise Slug Map

Use the following real Fitsho Exercise Library exercises whenever possible.

| Exercise | Slug |
|---|---|
| Smith Chair Squat | `fedb-0750-smith-chair-squat` |
| Barbell Back Squat | `fedb-1435-barbell-back-squat` |
| Barbell Front Squat | `fedb-0042-barbell-front-squat` |
| Horizontal Leg Press | `fedb-2611-lever-horizontal-leg-press` |
| Leg Extension | `fedb-0585-lever-leg-extension` |
| Seated Leg Curl | `fedb-0599-lever-seated-leg-curl` |
| Lying Leg Curl | `fedb-0586-lever-lying-leg-curl` |
| Dumbbell Deadlift | `fedb-0300-dumbbell-deadlift` |
| Dumbbell Lunge | `fedb-0336-dumbbell-lunge` |
| Rear Decline Bridge / Glute Bridge | `fedb-0668-rear-decline-bridge` |
| Standing Calf Raise Machine | `fedb-0605-lever-standing-calf-raise` |
| Lever Lying Chest Press | `fedb-0577-lever-lying-chest-press` |
| Lever Incline Hammer Chest Press | `fedb-1299-lever-incline-hammer-chest-press` |
| Barbell Bench Press | `fedb-0025-barbell-bench-press` |
| Dumbbell Incline Bench Press | `fedb-0314-dumbbell-incline-bench-press` |
| Lever High Row | `fedb-0581-lever-high-row` |
| Barbell Bent-Over Row | `owner-e0c26a271aac-barbell-bent-over-row` |
| Seated Cable Row | `owner-2a5de4dc7ba3-seated-cable-row` |
| Cable Close-Grip Lat Pulldown | `fedb-0974-cable-close-grip-lat-pulldown` |
| Smith Seated Shoulder Press | `fedb-0765-smith-seated-shoulder-press` |
| Military Press | `fedb-0553-military-press` |
| Lever Lateral Raise | `fedb-0584-lever-lateral-raise` |
| Cable Lateral Raise | `fedb-0178-cable-lateral-raise` |
| Lever Seated Reverse Fly | `fedb-0602-lever-seated-reverse-fly` |
| Lever Preacher Curl | `fedb-0592-lever-preacher-curl` |
| Seated Alternating Dumbbell Curl | `fedb-0285-seated-alternating-dumbbell-curl` |
| Dumbbell Cross-Body Hammer Curl | `fedb-0298-dumbbell-cross-body-hammer-curl` |
| Cable Triceps Pushdown | `fedb-1723-cable-triceps-pushdown` |
| Cable Rope Triceps Pushdown | `fedb-0200-cable-rope-triceps-pushdown` |
| Cable Rope Overhead Triceps Extension | `fedb-0194-cable-rope-overhead-triceps-extension` |
| Barbell Shrug | `fedb-0095-barbell-shrug` |

## Important

Before creating or updating the programs, validate that every referenced slug exists.

Do not silently skip missing exercises.

Do not create replacement Exercise records.

---

# Step 6 — Exact Definition of the 25 Programs

---

## Program 01

### 2 Day — Full Body A/B — First Month

#### Day A

1. Smith Chair Squat — `P`
2. Seated Leg Curl — `S`
3. Lever Lying Chest Press — `P`
4. Lever High Row — `P`
5. Cable Close-Grip Lat Pulldown — `S`
6. Smith Seated Shoulder Press — `S`

#### Day B

1. Horizontal Leg Press — `P`
2. Rear Decline Bridge — `P`
3. Lever Incline Hammer Chest Press — `P`
4. Lever High Row — `P`
5. Cable Close-Grip Lat Pulldown — `S`
6. Lever Lateral Raise — `I`

---

## Program 02

### 2 Day — Full Body A/B — Beginner

#### Day A

1. Smith Chair Squat — `P`
2. Seated Leg Curl — `S`
3. Lever Lying Chest Press — `P`
4. Lever High Row — `P`
5. Cable Close-Grip Lat Pulldown — `S`
6. Smith Seated Shoulder Press — `S`

#### Day B

1. Horizontal Leg Press — `P`
2. Dumbbell Deadlift — `P`
3. Dumbbell Incline Bench Press — `P`
4. Seated Cable Row — `P`
5. Cable Close-Grip Lat Pulldown — `S`
6. Cable Lateral Raise — `I`

---

## Program 03

### 2 Day — Full Body A/B — Intermediate

#### Day A

1. Barbell Back Squat — `P`
2. Seated Leg Curl — `S`
3. Barbell Bench Press — `P`
4. Barbell Bent-Over Row — `P`
5. Cable Close-Grip Lat Pulldown — `S`
6. Military Press — `S`

#### Day B

1. Horizontal Leg Press — `P`
2. Dumbbell Deadlift — `P`
3. Dumbbell Incline Bench Press — `P`
4. Seated Cable Row — `P`
5. Cable Close-Grip Lat Pulldown — `S`
6. Cable Lateral Raise — `I`

---

## Program 04

### 3 Day — Upper / Lower / Full — First Month

#### Upper

1. Lever Lying Chest Press — `P`
2. Lever Incline Hammer Chest Press — `S`
3. Lever High Row — `P`
4. Cable Close-Grip Lat Pulldown — `S`
5. Smith Seated Shoulder Press — `P`
6. Lever Lateral Raise — `I`

#### Lower

1. Smith Chair Squat — `P`
2. Horizontal Leg Press — `P`
3. Rear Decline Bridge — `P`
4. Seated Leg Curl — `S`
5. Lever Standing Calf Raise — `I`

#### Full

1. Horizontal Leg Press — `P`
2. Seated Leg Curl — `S`
3. Lever Lying Chest Press — `P`
4. Lever High Row — `P`
5. Cable Close-Grip Lat Pulldown — `S`
6. Lever Lateral Raise — `I`

---

## Program 05

### 3 Day — Upper / Lower / Full — Beginner

#### Upper

1. Lever Lying Chest Press — `P`
2. Dumbbell Incline Bench Press — `S`
3. Lever High Row — `P`
4. Cable Close-Grip Lat Pulldown — `S`
5. Smith Seated Shoulder Press — `P`
6. Cable Lateral Raise — `I`

#### Lower

1. Smith Chair Squat — `P`
2. Horizontal Leg Press — `P`
3. Dumbbell Deadlift — `P`
4. Seated Leg Curl — `S`
5. Lever Standing Calf Raise — `I`

#### Full

1. Horizontal Leg Press — `P`
2. Seated Leg Curl — `S`
3. Lever Lying Chest Press — `P`
4. Seated Cable Row — `P`
5. Cable Close-Grip Lat Pulldown — `S`
6. Cable Lateral Raise — `I`

---

## Program 06

### 3 Day — Upper / Lower / Full — Intermediate

#### Upper

1. Barbell Bench Press — `P`
2. Dumbbell Incline Bench Press — `S`
3. Barbell Bent-Over Row — `P`
4. Cable Close-Grip Lat Pulldown — `S`
5. Military Press — `P`
6. Cable Lateral Raise — `I`

#### Lower

1. Barbell Back Squat — `P`
2. Horizontal Leg Press — `P`
3. Dumbbell Deadlift — `P`
4. Seated Leg Curl — `S`
5. Lever Standing Calf Raise — `I`

#### Full

1. Horizontal Leg Press — `P`
2. Seated Leg Curl — `S`
3. Barbell Bench Press — `P`
4. Seated Cable Row — `P`
5. Cable Close-Grip Lat Pulldown — `S`
6. Cable Lateral Raise — `I`

---

## Program 07

### 3 Day — Upper / Lower / Full — Advanced

Use the **same exercise selection and exercise order as Program 06**.

Apply the **Advanced prescription**.

---

## Program 08

### 3 Day — Upper / Lower / Upper — Beginner

#### Upper A

1. Lever Lying Chest Press — `P`
2. Dumbbell Incline Bench Press — `S`
3. Lever High Row — `P`
4. Cable Close-Grip Lat Pulldown — `S`
5. Smith Seated Shoulder Press — `P`
6. Cable Lateral Raise — `I`
7. Lever Preacher Curl — `I`
8. Cable Triceps Pushdown — `I`

#### Lower

1. Smith Chair Squat — `P`
2. Horizontal Leg Press — `P`
3. Dumbbell Deadlift — `P`
4. Seated Leg Curl — `S`
5. Lever Standing Calf Raise — `I`

#### Upper B

1. Dumbbell Incline Bench Press — `P`
2. Lever Lying Chest Press — `S`
3. Seated Cable Row — `P`
4. Cable Close-Grip Lat Pulldown — `S`
5. Lever Seated Reverse Fly — `I`
6. Cable Lateral Raise — `I`
7. Dumbbell Cross-Body Hammer Curl — `I`
8. Cable Rope Triceps Pushdown — `I`

---

## Program 09

### 3 Day — Upper / Lower / Upper — Intermediate

#### Upper A

1. Barbell Bench Press — `P`
2. Dumbbell Incline Bench Press — `S`
3. Barbell Bent-Over Row — `P`
4. Cable Close-Grip Lat Pulldown — `S`
5. Military Press — `P`
6. Cable Lateral Raise — `I`
7. Seated Alternating Dumbbell Curl — `I`
8. Cable Triceps Pushdown — `I`

#### Lower

1. Barbell Back Squat — `P`
2. Horizontal Leg Press — `P`
3. Dumbbell Deadlift — `P`
4. Seated Leg Curl — `S`
5. Lever Standing Calf Raise — `I`

#### Upper B

1. Dumbbell Incline Bench Press — `P`
2. Barbell Bench Press — `S`
3. Seated Cable Row — `P`
4. Cable Close-Grip Lat Pulldown — `S`
5. Lever Seated Reverse Fly — `I`
6. Cable Lateral Raise — `I`
7. Dumbbell Cross-Body Hammer Curl — `I`
8. Cable Rope Overhead Triceps Extension — `I`

---

## Program 10

### 3 Day — Upper / Lower / Upper — Advanced

Use the **same exercise selection and order as Program 09**.

Apply the **Advanced prescription**.

---

## Program 11

### 3 Day — Lower / Upper / Lower — Beginner

#### Lower A

1. Smith Chair Squat — `P`
2. Horizontal Leg Press — `P`
3. Dumbbell Deadlift — `P`
4. Seated Leg Curl — `S`
5. Lever Standing Calf Raise — `I`

#### Upper

1. Lever Lying Chest Press — `P`
2. Dumbbell Incline Bench Press — `S`
3. Lever High Row — `P`
4. Cable Close-Grip Lat Pulldown — `S`
5. Smith Seated Shoulder Press — `P`
6. Cable Lateral Raise — `I`
7. Lever Preacher Curl — `I`
8. Cable Triceps Pushdown — `I`

#### Lower B

1. Horizontal Leg Press — `P`
2. Dumbbell Lunge — `S`
3. Dumbbell Deadlift — `P`
4. Lying Leg Curl — `S`
5. Lever Standing Calf Raise — `I`

---

## Program 12

### 3 Day — Lower / Upper / Lower — Intermediate

#### Lower A

1. Barbell Back Squat — `P`
2. Horizontal Leg Press — `P`
3. Dumbbell Deadlift — `P`
4. Seated Leg Curl — `S`
5. Lever Standing Calf Raise — `I`

#### Upper

1. Barbell Bench Press — `P`
2. Dumbbell Incline Bench Press — `S`
3. Barbell Bent-Over Row — `P`
4. Cable Close-Grip Lat Pulldown — `S`
5. Military Press — `P`
6. Cable Lateral Raise — `I`
7. Seated Alternating Dumbbell Curl — `I`
8. Cable Triceps Pushdown — `I`

#### Lower B

1. Horizontal Leg Press — `P`
2. Dumbbell Lunge — `S`
3. Dumbbell Deadlift — `P`
4. Lying Leg Curl — `S`
5. Lever Standing Calf Raise — `I`

---

## Program 13

### 3 Day — Lower / Upper / Lower — Advanced

Use the **same exercise selection and order as Program 12**.

Apply the **Advanced prescription**.

---

## Program 14

### 4 Day — Upper / Lower / Upper / Lower — First Month

#### Upper A

1. Lever Lying Chest Press — `P`
2. Lever Incline Hammer Chest Press — `S`
3. Lever High Row — `P`
4. Cable Close-Grip Lat Pulldown — `S`
5. Smith Seated Shoulder Press — `P`
6. Lever Lateral Raise — `I`

#### Lower A

1. Smith Chair Squat — `P`
2. Horizontal Leg Press — `P`
3. Rear Decline Bridge — `P`
4. Seated Leg Curl — `S`
5. Lever Standing Calf Raise — `I`

#### Upper B

1. Lever Incline Hammer Chest Press — `P`
2. Lever Lying Chest Press — `S`
3. Lever High Row — `P`
4. Cable Close-Grip Lat Pulldown — `S`
5. Lever Seated Reverse Fly — `I`
6. Lever Lateral Raise — `I`

#### Lower B

1. Smith Chair Squat — `P`
2. Leg Extension — `I`
3. Rear Decline Bridge — `P`
4. Lying Leg Curl — `S`
5. Lever Standing Calf Raise — `I`

---

## Program 15

### 4 Day — Upper / Lower / Upper / Lower — Beginner

#### Upper A

1. Lever Lying Chest Press — `P`
2. Dumbbell Incline Bench Press — `S`
3. Lever High Row — `P`
4. Cable Close-Grip Lat Pulldown — `S`
5. Smith Seated Shoulder Press — `P`
6. Cable Lateral Raise — `I`

#### Lower A

1. Smith Chair Squat — `P`
2. Horizontal Leg Press — `P`
3. Dumbbell Deadlift — `P`
4. Seated Leg Curl — `S`
5. Lever Standing Calf Raise — `I`

#### Upper B

1. Dumbbell Incline Bench Press — `P`
2. Lever Lying Chest Press — `S`
3. Seated Cable Row — `P`
4. Cable Close-Grip Lat Pulldown — `S`
5. Lever Seated Reverse Fly — `I`
6. Cable Lateral Raise — `I`

#### Lower B

1. Smith Chair Squat — `P`
2. Leg Extension — `I`
3. Dumbbell Deadlift — `P`
4. Lying Leg Curl — `S`
5. Lever Standing Calf Raise — `I`

---

## Program 16

### 4 Day — Upper / Lower / Upper / Lower — Intermediate

#### Upper A

1. Barbell Bench Press — `P`
2. Dumbbell Incline Bench Press — `S`
3. Barbell Bent-Over Row — `P`
4. Cable Close-Grip Lat Pulldown — `S`
5. Military Press — `P`
6. Cable Lateral Raise — `I`

#### Lower A

1. Barbell Back Squat — `P`
2. Horizontal Leg Press — `P`
3. Dumbbell Deadlift — `P`
4. Seated Leg Curl — `S`
5. Lever Standing Calf Raise — `I`

#### Upper B

1. Dumbbell Incline Bench Press — `P`
2. Barbell Bench Press — `S`
3. Seated Cable Row — `P`
4. Cable Close-Grip Lat Pulldown — `S`
5. Lever Seated Reverse Fly — `I`
6. Cable Lateral Raise — `I`

#### Lower B

1. Barbell Front Squat — `P`
2. Leg Extension — `I`
3. Dumbbell Deadlift — `P`
4. Lying Leg Curl — `S`
5. Lever Standing Calf Raise — `I`

---

## Program 17

### 4 Day — Upper / Lower / Upper / Lower — Advanced

Use the **same exercise selection and order as Program 16**.

Apply the **Advanced prescription**.

---

## Program 18

### 4 Day — 3 Upper + 1 Lower — Beginner

#### Upper A — Chest / Back

1. Lever Lying Chest Press — `P`
2. Dumbbell Incline Bench Press — `S`
3. Lever High Row — `P`
4. Cable Close-Grip Lat Pulldown — `S`
5. Cable Lateral Raise — `I`
6. Cable Triceps Pushdown — `I`

#### Lower

1. Smith Chair Squat — `P`
2. Horizontal Leg Press — `P`
3. Dumbbell Deadlift — `P`
4. Seated Leg Curl — `S`
5. Lever Standing Calf Raise — `I`

#### Upper B — Shoulders / Arms

1. Smith Seated Shoulder Press — `P`
2. Cable Lateral Raise — `I`
3. Lever Seated Reverse Fly — `I`
4. Lever Preacher Curl — `I`
5. Dumbbell Cross-Body Hammer Curl — `I`
6. Cable Triceps Pushdown — `I`
7. Cable Rope Triceps Pushdown — `I`

#### Upper C — Chest / Back

1. Dumbbell Incline Bench Press — `P`
2. Lever Lying Chest Press — `S`
3. Seated Cable Row — `P`
4. Cable Close-Grip Lat Pulldown — `S`
5. Lever Preacher Curl — `I`

---

## Program 19

### 4 Day — 3 Upper + 1 Lower — Intermediate

#### Upper A

1. Barbell Bench Press — `P`
2. Dumbbell Incline Bench Press — `S`
3. Barbell Bent-Over Row — `P`
4. Cable Close-Grip Lat Pulldown — `S`
5. Cable Lateral Raise — `I`
6. Cable Triceps Pushdown — `I`

#### Lower

1. Barbell Back Squat — `P`
2. Horizontal Leg Press — `P`
3. Dumbbell Deadlift — `P`
4. Seated Leg Curl — `S`
5. Lever Standing Calf Raise — `I`

#### Upper B

1. Military Press — `P`
2. Cable Lateral Raise — `I`
3. Lever Seated Reverse Fly — `I`
4. Seated Alternating Dumbbell Curl — `I`
5. Dumbbell Cross-Body Hammer Curl — `I`
6. Cable Triceps Pushdown — `I`
7. Cable Rope Overhead Triceps Extension — `I`

#### Upper C

1. Dumbbell Incline Bench Press — `P`
2. Barbell Bench Press — `S`
3. Seated Cable Row — `P`
4. Cable Close-Grip Lat Pulldown — `S`
5. Seated Alternating Dumbbell Curl — `I`

---

## Program 20

### 4 Day — 3 Upper + 1 Lower — Advanced

Use the **same exercise selection and order as Program 19**.

Apply the **Advanced prescription**.

---

## Program 21

### 4 Day — 3 Lower + 1 Upper — Beginner

#### Lower A — Quads

1. Smith Chair Squat — `P`
2. Horizontal Leg Press — `P`
3. Seated Leg Curl — `S`
4. Lever Standing Calf Raise — `I`

#### Upper

1. Lever Lying Chest Press — `P`
2. Dumbbell Incline Bench Press — `S`
3. Lever High Row — `P`
4. Cable Close-Grip Lat Pulldown — `S`
5. Smith Seated Shoulder Press — `P`
6. Cable Lateral Raise — `I`
7. Lever Preacher Curl — `I`
8. Cable Triceps Pushdown — `I`

#### Lower B — Posterior

1. Dumbbell Deadlift — `P`
2. Lying Leg Curl — `S`
3. Rear Decline Bridge — `P`
4. Lever Standing Calf Raise — `I`

#### Lower C — Quads / Glutes

1. Horizontal Leg Press — `P`
2. Leg Extension — `I`
3. Rear Decline Bridge — `P`
4. Lever Standing Calf Raise — `I`

---

## Program 22

### 4 Day — 3 Lower + 1 Upper — Intermediate

#### Lower A

1. Barbell Back Squat — `P`
2. Horizontal Leg Press — `P`
3. Seated Leg Curl — `S`
4. Lever Standing Calf Raise — `I`

#### Upper

1. Barbell Bench Press — `P`
2. Dumbbell Incline Bench Press — `S`
3. Barbell Bent-Over Row — `P`
4. Cable Close-Grip Lat Pulldown — `S`
5. Military Press — `P`
6. Cable Lateral Raise — `I`
7. Seated Alternating Dumbbell Curl — `I`
8. Cable Triceps Pushdown — `I`

#### Lower B

1. Dumbbell Deadlift — `P`
2. Lying Leg Curl — `S`
3. Rear Decline Bridge — `P`
4. Lever Standing Calf Raise — `I`

#### Lower C

1. Horizontal Leg Press — `P`
2. Leg Extension — `I`
3. Rear Decline Bridge — `P`
4. Lever Standing Calf Raise — `I`

---

## Program 23

### 4 Day — 3 Lower + 1 Upper — Advanced

Use the **same exercise selection and order as Program 22**.

Apply the **Advanced prescription**.

---

## Program 24

### 4 Day — Push / Pull / Quads / Posterior — Intermediate

#### Push

1. Barbell Bench Press — `P`
2. Dumbbell Incline Bench Press — `S`
3. Military Press — `P`
4. Cable Lateral Raise — `I`
5. Cable Triceps Pushdown — `I`

#### Pull

1. Barbell Bent-Over Row — `P`
2. Cable Close-Grip Lat Pulldown — `P`
3. Seated Alternating Dumbbell Curl — `I`
4. Barbell Shrug — `I`

#### Quads

1. Barbell Back Squat — `P`
2. Horizontal Leg Press — `P`
3. Leg Extension — `I`
4. Seated Leg Curl — `S`
5. Lever Standing Calf Raise — `I`

#### Posterior

1. Dumbbell Deadlift — `P`
2. Lying Leg Curl — `S`
3. Rear Decline Bridge — `P`
4. Dumbbell Lunge — `S`
5. Lever Standing Calf Raise — `I`

---

## Program 25

### 4 Day — Push / Pull / Quads / Posterior — Advanced

Use the **same exercise selection and order as Program 24**.

Apply the **Advanced prescription**.

---

# Step 7 — Program Naming

Program Cards should use short, consistent names.

The visible card should primarily represent:

```text
Structure + Level
```

Examples:

```text
Full Body A/B — First Month
Full Body A/B — Beginner
Upper / Lower / Full — Intermediate
ULUL — Advanced
```

However, follow Fitsho's existing naming conventions if they already exist.

If the project has separate:

- internal key,
- internal title,
- display title,

then:

- keep the display title user-friendly,
- keep internal identifiers deterministic,
- keep identifiers stable across seed runs.

Do not use random IDs for seeded program identity when a deterministic identifier is more appropriate.

---

# Step 8 — Exercise Library Linking

This is one of the most important parts of the task.

Program exercises must **not** become independent copies of Exercise Library exercises.

The desired relationship should conceptually remain:

```text
Program
  -> Day
      -> ProgramExercise
          -> Exercise Library Exercise
```

Use the existing Fitsho relationship implementation.

If `ProgramExercise` already has an `exercise_id` or equivalent FK/reference, populate it.

If it also stores snapshot/display fields because the current schema requires them, keep the existing behavior, but the Exercise Library must remain the source of truth for the exercise identity.

Do not unnecessarily duplicate:

- exercise name,
- media,
- equipment,
- muscles,
- instructions,
- exercise metadata.

Exercise Library must remain the canonical source of truth.

---

# Step 9 — Required Validation

Create new validation tests or extend existing tests to verify all of the following.

## Program Count

1. Exactly **25** approved Default Programs exist for this matrix.

## Uniqueness

2. No duplicate default programs exist.

## Structure Compatibility

3. Every program references a valid Training Template / Structure.

4. Every program level is included in that template's `supported_levels`.

## Day Validation

5. Every program contains the correct number of training days.

6. Day ordering exactly matches the approved structure.

## Exercise Linking

7. Every Program Exercise links to a real Exercise Library Exercise.

8. No referenced exercise slug remains unresolved.

9. No inactive or non-programmable Exercise is used if the project has those restrictions.

## Prescription

10. Prescription values match the correct level and movement role.

## Unsupported Combinations

11. No `First Month` program exists for:

```text
Upper / Lower / Upper
Lower / Upper / Lower
3 Upper + 1 Lower
3 Lower + 1 Upper
Push / Pull / Quads / Posterior
```

12. No `Beginner` program exists for:

```text
Push / Pull / Quads / Posterior
```

13. No `Advanced` program exists for:

```text
2 Day Full Body A/B
```

## Seed Idempotency

14. Running the seed process multiple times must not create duplicate programs or duplicate program-day-exercise relationships.

Prefer existing integration/database test infrastructure when available.

---

# Step 10 — Scope Review Before Finishing

Before finishing, inspect:

```bash
git diff
git status
```

Confirm that:

- no unrelated files were modified,
- no broad formatting changes were introduced,
- Program Engine behavior was not unintentionally changed,
- Exercise Library data was not deleted or renamed,
- no unnecessary migration was created,
- no unnecessary dependency was added,
- no unrelated refactor was performed.

If unrelated modifications already existed before this task, do not claim them as your changes.

Do not revert unrelated pre-existing user changes.

---

# Step 11 — Testing

At minimum, run the relevant tests for:

- `training_templates`
- Default Program Library
- program seeding
- program/exercise linking
- seed idempotency
- related schemas/models
- template-level compatibility

Then run as much of the relevant backend test suite as reasonably possible.

If a test fails:

1. investigate the real reason,
2. fix the implementation when appropriate,
3. do not simply change a test expectation to make the suite green unless the specification itself requires that expectation to change.

---

# Step 12 — Final Report

At the end, provide a concise but complete implementation report.

Include:

1. Files changed.

2. Where the 25 Default Programs are defined or seeded.

3. How Program Exercises are linked to Exercise Library records.

4. Whether all 25 programs were successfully validated.

5. Whether all requested exercise slugs resolved successfully.

6. If any slug was replaced, provide:

```text
Requested slug -> Actual used slug -> Reason
```

7. Tests executed and their results.

8. Whether any schema or migration was changed.

9. Whether Program Engine logic was changed.

10. Final `git diff` / scope summary.

Also provide a summary table with exactly **25 rows**:

| Days | Structure | Level | Program Created |
|---|---|---|---|

Do not declare the task complete until:

- implementation is complete,
- exercise references resolve,
- the supported-level matrix is valid,
- the expected program count is 25,
- and the relevant tests pass.
