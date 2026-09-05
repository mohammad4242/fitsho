# Fitsho — Add 24 Approved 5-Day and 6-Day Default Programs

## Mission

Work on the **Fitsho** project and extend the existing **Default Program Library** by adding exactly:

- **12 approved 5-day programs**
- **12 approved 6-day programs**

Total new approved programs:

```text
24
```

The existing **2-day, 3-day, and 4-day programs must remain completely unchanged**.

This is a controlled library-expansion task. Do not redesign the existing 2/3/4-day catalog, do not change Program Engine behavior, and do not perform unrelated refactors.

---

# 0. Non-Negotiable Rules

1. Read this entire file before making any code change.
2. Execute the task step by step in the order defined here.
3. Existing **2-day, 3-day, and 4-day programs are frozen**. Their slugs, names, levels, structures, day order, exercises, exercise order, sets, reps, RIR, rest, intensity methods, and metadata must remain unchanged.
4. Before editing, create a machine-checkable snapshot/signature of every existing 2/3/4-day default program. After implementation, verify the snapshot is identical.
5. Add exactly **24 approved new program variants** defined in this document.
6. Do not delete existing 5-day or 6-day structures/programs unless an exact equivalent already exists and the existing architecture requires an idempotent update rather than duplication.
7. Reuse existing 5-day/6-day canonical structures when they are semantically identical.
8. When a required new 5-day/6-day structure does not currently exist, add it using the project's existing Training Template architecture.
9. Do not create a parallel Program Library architecture.
10. Do not create fake exercises.
11. Do not duplicate Exercise Library records.
12. Every Program Exercise must resolve to a real, active, programmable Exercise Library record.
13. Prefer exact stable slugs/FKs. Do not rely on fuzzy display-name matching.
14. If a requested exercise slug does not exist, inspect the current Exercise Library, find the exact intended exercise if it exists under another stable slug, use that real record, report the substitution, and never silently invent an exercise.
15. Preserve the Exercise Library as the canonical source of truth.
16. Do not copy exercise metadata such as media, instructions, equipment, and muscles into a second source of truth unless the existing schema intentionally stores snapshots.
17. Do not modify Program Engine selection logic unless absolutely required to make the new library entries visible through the existing generic mechanism. If no engine change is required, do not touch it.
18. No unrelated formatting.
19. No unrelated refactoring.
20. No dependency changes unless technically unavoidable.
21. No database migration unless the current schema genuinely cannot represent the approved programs.
22. Do not weaken tests to make the task pass.
23. Do not stop at planning or analysis. Complete the implementation, validation, tests, and final scope review.

---

# 1. Inspect Existing Architecture

Before making any edits, inspect the current implementation of:

```text
backend/app/training_templates/
backend/app/exercises/
```

Also identify:

- Training Program / Training Template models
- level-specific default program representation
- `seed_data.py`
- template/service seed logic
- `supported_levels`
- structure identifiers
- program identifiers
- Program Day representation
- Program Exercise representation
- exercise FK / slug linkage
- RIR storage
- sets/reps storage
- rest storage
- intensity method representation
- superset group representation
- drop-set representation
- existing idempotency logic
- Default Program Library API
- admin program-library UI/data contract
- related tests

Determine the correct implementation path from the codebase.

Do not invent a second architecture.

---

# 2. Freeze the Existing 2/3/4-Day Catalog

Before editing any seed/template data, generate a deterministic signature for every existing program where:

```text
days_per_week in {2, 3, 4}
```

The signature should include at minimum:

```text
program/template identity
canonical structure identity
level
day count
day order
day names
exercise identity
exercise order
sets
rep_min
rep_max
target_rir
rest_seconds
intensity_method
superset_group
```

After all work is finished:

```text
BEFORE_2_3_4_SIGNATURE == AFTER_2_3_4_SIGNATURE
```

must be true.

If not, the task is not complete.

Do not "fix" any existing 2/3/4-day content during this task.

---

# 3. Final Approved Matrix

## 5-Day

Six base structures × two levels:

```text
Intermediate
Advanced
```

Approved 5-day structures:

1. Classic Body-Part
2. Split + Weak Point
3. Upper-Priority Iranian Split
4. Upper / Lower + Specialty
5. FST-7 / Arms Priority
6. Professional Split + Compound Day

Total:

```text
6 × 2 = 12 programs
```

## 6-Day

Six base structures × two levels:

```text
Intermediate
Advanced
```

Approved 6-day structures:

1. PPL A/B
2. Upper / Lower ×3
3. FitClub Hybrid
4. Arnold Split
5. Classic Six Body-Part
6. Ronnie Double Exposure

Total:

```text
6 × 2 = 12 programs
```

Required approved additions:

```text
5-day = 12
6-day = 12
TOTAL NEW APPROVED PROGRAMS = 24
```

Add a test that asserts exactly 24 approved additions from this specification exist.

---

# 4. Mandatory Pyramid Prescription Rules

This revision intentionally standardizes the approved **5-day and 6-day Default Programs** around a descending-repetition pyramid.

This is a **Fitsho catalog programming rule**, not a claim that `12/10/8/6` is the only scientifically valid hypertrophy method.

The research basis supports:
- multi-set resistance training,
- hypertrophy across a broad useful repetition range,
- adequate weekly volume,
- and longer recovery for demanding compound exercises.

Iranian bodybuilding examples also commonly use descending-repetition prescriptions such as `12/10/10/8`, `12/10/8`, and other pyramid patterns.

For this task, use the exact rules below for consistency.

## 4.1 Hard Minimum-Repetition Rule

No working set in these 24 programs may prescribe fewer than:

```text
6 reps
```

Forbidden examples:

```text
5 reps
4 reps
3 reps
1–5 reps
4×5–8
```

The lowest normal working-set target allowed is:

```text
6 reps
```

## 4.2 Main Large-Muscle Pyramid

Large muscle groups for this task:

```text
Chest
Back
Lower body: quadriceps / hamstrings / glutes
```

For a day/block focused on one of these large muscle groups:

### First two non-superset compound exercises

Use:

```text
Set 1: 12 reps
Set 2: 10 reps
Set 3: 8 reps
Set 4: 6 reps

Prescription: 4×12/10/8/6
```

Load should generally increase as repetitions decrease, while preserving the target RIR and clean technique.

Examples:

```text
پرس سینه هالتر       4×12/10/8/6
پرس بالا سینه دمبل   4×12/10/8/6

زیربغل هالتر خم      4×12/10/8/6
لت سیمکش             4×12/10/8/6

اسکوات               4×12/10/8/6
پرس پا               4×12/10/8/6
```

Count each large muscle group independently on mixed days.

Example:

```text
Chest + Back day
```

The first two eligible chest compounds and the first two eligible back compounds may each use the four-set pyramid.

### Important Superset Exception

If an exercise is explicitly part of an approved superset, the **3-round superset rule takes priority** over the 4-set rule.

Do not turn a superset exercise into four rounds merely because it is one of the first two exercises for a large muscle.

## 4.3 Later Large-Muscle Compound Exercises

After the first two large-muscle compound movements in a block, later compound/accessory compounds should generally use:

```text
3×12/10/8
```

Example:

```text
Set 1: 12
Set 2: 10
Set 3: 8
```

## 4.4 Large-Muscle Isolation / Machine Accessories

Isolation or smaller accessory movements for large muscle groups should generally use:

```text
3×12/10/10
```

Examples include:

```text
کراس‌اور سیمکش
جلوپا دستگاه
پشت پا دستگاه
پول‌داون دست صاف
```

## 4.5 Smaller Muscle Groups

For:

```text
Shoulders
Biceps
Triceps
Calves
```

use **mostly 3 working sets**.

### Main movement

Use:

```text
3×12/10/8
```

Examples:

```text
پرس سرشانه
جلو بازو هالتر
پشت بازو سیمکش
```

### Secondary / isolation movement

Use:

```text
3×12/10/10
```

Examples:

```text
نشر جانب
فلای معکوس
جلو بازو چکشی
جلو بازو لاری
پشت بازو بالای سر
ساق
```

Do not automatically make small-muscle exercises four sets merely because the athlete is Advanced.

## 4.6 Superset Rule — Exactly 3 Rounds

Every approved superset in this specification must be performed for exactly:

```text
3 rounds
```

Each exercise in the pair uses:

```text
Round 1: 12 reps
Round 2: 10 reps
Round 3: 8 reps

Equivalent prescription: 3×12/10/8
```

Execution:

```text
Exercise A
0–15 sec transition
Exercise B
then the prescribed recovery
```

Do not create 4-round supersets.

## 4.7 Drop-Set Rule

Drop sets remain only where explicitly approved.

The normal exercise prescription still follows its pyramid pattern.

Only after the **final normal working set**:

```text
reduce load approximately 20–30%
minimal/no rest
perform approximately 8–12 additional reps
```

No drop-set extension may intentionally prescribe fewer than 6 reps.

Do not apply drop sets to heavy barbell primary compounds.

## 4.8 FST-7 Exception

Program 10 remains the explicit FST-7 exception.

For an FST-7 movement use exactly:

```text
7 sets
12 / 10 / 10 / 10 / 8 / 8 / 8 reps
30–60 sec recovery as specified
```

All repetitions remain >= 8.

Do not apply the ordinary 3-set small-muscle rule to an exercise explicitly marked FST-7.

## 4.9 Core / Timed Exercises

Timed core exercises are not converted to rep pyramids.

Use the specified duration, but use:

```text
3 working sets
```

unless the existing prescription model requires a semantically equivalent duration representation.

## 4.10 Rest Guidance

For demanding four-set large-muscle pyramids:

```text
Intermediate:
- major chest/back compound: generally 120 sec
- demanding squat/hinge: generally 120–150 sec

Advanced:
- four-set major compound: generally 150 sec
```

For later compounds:

```text
approximately 90–120 sec
```

For small-muscle and isolation work:

```text
approximately 60–90 sec
```

For supersets:

```text
minimal transition between paired exercises
then the specified recovery after the pair
```

## 4.11 RIR

The pyramid does **not** mean that every final set must reach failure.

Use the existing RIR rules later in this document.

The load increase from `12 → 10 → 8 → 6` must be chosen so the target RIR can still be respected.

## 4.12 Research / Programming Rationale

This prescription rule was chosen after reviewing both Iranian programming examples and resistance-training evidence.

Useful references reviewed for this revision include:

```text
FitClub Iran — examples of descending-set prescriptions:
https://fitclub.ir/blog/fitness-program/

MrGym Iran — 5-day program examples using more sets for main large-muscle compounds and generally fewer sets for accessory work:
https://mrgym.ir/workout/

PubMed — resistance-training prescription network meta-analysis:
https://pubmed.ncbi.nlm.nih.gov/37414459/

PubMed — set-volume systematic review:
https://pubmed.ncbi.nlm.nih.gov/30063555/

PubMed — weekly volume and hypertrophy systematic review:
https://pubmed.ncbi.nlm.nih.gov/35291645/
```

Interpretation for Fitsho:

- `12/10/8/6` is a valid pyramid organization, not a unique physiological law.
- Multiple set structures can build muscle.
- For this catalog, the pyramid is being used deliberately for consistency, progressive loading, and user readability.
- Larger muscle-group sessions receive more four-set compound work.
- Smaller muscle-group exercises are mostly three-set movements to prevent unnecessary volume inflation in 5- and 6-day schedules.

---

# 5. Intensity Technique Definitions

Use the project's existing intensity-method representation.

## Standard

Normal working sets using the listed recovery.

## Superset — `SS`

```text
Exercise A
0–15 sec transition
Exercise B
then prescribed recovery
```

Use one shared `superset_group` or the project's equivalent.

## Drop Set — `DS`

Only on the **final working set** of the specified exercise:

```text
normal final set
reduce load ~20–30%
minimal/no rest
perform ~8–12 additional reps
```

Do not apply drop sets to heavy barbell compounds in this specification.

## FST-7

For this task, treat FST-7 only as a high-density isolation prescription:

```text
7 working sets
12 / 10 / 10 / 10 / 8 / 8 / 8 reps
30–60 sec rest
```

Do not encode unsupported marketing claims.

If Fitsho has no explicit `FST7` intensity enum:
- do not change schema merely for the label,
- encode the approved 7-set prescription with the supported representation,
- retain a programming note only if architecture supports it,
- report how it was represented.

---

# 6. Exercise Library Requirement

Every exercise must link to a real current Fitsho Exercise Library record.

Preferred identities to validate:

| Persian Display Name | Preferred Fitsho Identity |
|---|---|
| پرس سینه هالتر | `fedb-0025-barbell-bench-press` |
| پرس سینه دمبل | `dumbbell-bench-press` |
| پرس بالا سینه دمبل | `fedb-0314-dumbbell-incline-bench-press` |
| پرس سینه دستگاه | `fedb-0577-lever-lying-chest-press` |
| پرس بالا سینه هامر دستگاه | `fedb-1299-lever-incline-hammer-chest-press` |
| کراس‌اور سیمکش | `fedb-1269-cable-standing-fly` |
| زیربغل هالتر خم | `owner-e0c26a271aac-barbell-bent-over-row` |
| قایقی سیمکش | `owner-2a5de4dc7ba3-seated-cable-row` |
| زیربغل High Row دستگاه | `fedb-0581-lever-high-row` |
| لت سیمکش دست جمع | `fedb-0974-cable-close-grip-lat-pulldown` |
| پول‌داون دست صاف | `fedb-0238-cable-straight-arm-pulldown` |
| پرس سرشانه هالتر / نظامی | `fedb-0553-military-press` |
| پرس سرشانه اسمیت | `fedb-0765-smith-seated-shoulder-press` |
| نشر جانب سیمکش | `fedb-0178-cable-lateral-raise` |
| نشر جانب دستگاه | `fedb-0584-lever-lateral-raise` |
| نشر جانب دمبل | `dumbbell-lateral-raise` |
| فلای معکوس دستگاه | `fedb-0602-lever-seated-reverse-fly` |
| شراگ هالتر | `fedb-0095-barbell-shrug` |
| جلو بازو هالتر | `fedb-0031-barbell-curl` |
| جلو بازو سیمکش | `fedb-0229-cable-standing-inner-curl` |
| جلو بازو لاری دستگاه | `fedb-0592-lever-preacher-curl` |
| جلو بازو دمبل تناوبی | `fedb-0285-seated-alternating-dumbbell-curl` |
| جلو بازو چکشی دمبل | `fedb-0298-dumbbell-cross-body-hammer-curl` |
| پشت بازو سیمکش | `fedb-1723-cable-triceps-pushdown` |
| پشت بازو طناب | `fedb-0200-cable-rope-triceps-pushdown` |
| پشت بازو طناب بالای سر | `fedb-0194-cable-rope-overhead-triceps-extension` |
| اسکوات هالتر پشت | `fedb-1435-barbell-back-squat` |
| اسکوات جلو هالتر | `fedb-0042-barbell-front-squat` |
| پرس پا دستگاه | `fedb-2611-lever-horizontal-leg-press` |
| جلوپا دستگاه | `fedb-0585-lever-leg-extension` |
| پشت پا نشسته دستگاه | `fedb-0599-lever-seated-leg-curl` |
| پشت پا خوابیده دستگاه | `fedb-0586-lever-lying-leg-curl` |
| لانج دمبل | `fedb-0336-dumbbell-lunge` |
| پل باسن | `fedb-0668-rear-decline-bridge` |
| ساق ایستاده | `fedb-0605-lever-standing-calf-raise` |
| پلانک | `fedb-0464-front-plank` |
| پلانک بغل | `fedb-0705-side-plank` |
| ددلیفت رومانیایی | verify current real `romanian-deadlift` record |

Important:
- `romanian-deadlift`, `dumbbell-bench-press`, and `dumbbell-lateral-raise` may be owner/seed identities rather than `fedb-*`.
- Resolve their actual current stable records before linking.
- Never create duplicate exercises merely because another slug style exists.
- If a preferred identity does not exist, use the real equivalent already in Fitsho and report it.

---

# 7. Naming and Stable Identity

Each approved program must be a distinct level-specific Default Program entry.

Use deterministic identifiers.

Conceptual examples:

```text
5D Classic Body-Part — Intermediate
5D Classic Body-Part — Advanced
6D Arnold Split — Intermediate
6D Arnold Split — Advanced
```

For new structures, use deterministic canonical slugs. Suggested names if no equivalent exists:

```text
5d-classic-body-part
5d-split-weak-point
5d-upper-priority-iranian
5d-upper-lower-specialty
5d-fst7-arms-priority
5d-professional-compound

6d-ppl-ab
6d-upper-lower-x3
6d-fitclub-hybrid
6d-arnold-split
6d-classic-body-part
6d-ronnie-double-exposure
```

Do not blindly create these if an equivalent stable structure already exists. Reuse current canonical identities when semantically identical.

---

# 8. Approved 5-Day Programs

## Program 01 — Classic Body-Part — Intermediate

Day order:

```text
Chest / Back / Shoulders / Arms / Legs
```

### Chest
1. پرس سینه هالتر — `4×12/10/8/6` — `120s`
2. پرس بالا سینه دمبل — `4×12/10/8/6` — `120s`
3. پرس سینه دستگاه — `3×12/10/8` — `120s`
4. کراس‌اور سیمکش — `3×12/10/10` — `60s`

### Back
1. زیربغل هالتر خم — `4×12/10/8/6` — `120s`
2. لت سیمکش دست جمع — `4×12/10/8/6` — `120s`
3. High Row دستگاه — `3×12/10/8` — `120s`
4. پول‌داون دست صاف — `3×12/10/10` — `60s`

### Shoulders
1. پرس سرشانه هالتر — `3×12/10/8` — `90s`
2. نشر جانب سیمکش — `3×12/10/10` — `60s`
3. فلای معکوس دستگاه — `3×12/10/10` — `60s`
4. شراگ هالتر — `3×12/10/10` — `60s`

### Arms
1. جلو بازو هالتر — `3×12/10/8` — `60s`
2. جلو بازو لاری — `3×12/10/10` — `60s`
3. پشت بازو سیمکش — `3×12/10/8` — `60s`
4. پشت بازو طناب بالای سر — `3×12/10/10` — `60s`
5. جلو بازو چکشی — `3×12/10/10` — `60s`

### Legs
1. اسکوات هالتر پشت — `4×12/10/8/6` — `150s`
2. پرس پا — `4×12/10/8/6` — `120s`
3. ددلیفت رومانیایی — `3×12/10/8` — `120s`
4. پشت پا نشسته — `3×12/10/10` — `60s`
5. ساق ایستاده — `3×12/10/10` — `60s`

Intensity: Standard only.

---

## Program 02 — Classic Body-Part — Advanced

### Chest
1. پرس سینه هالتر — `4×12/10/8/6` — `150s`
2. پرس بالا سینه هامر — `4×12/10/8/6` — `150s`
3. پرس سینه دمبل — `3×12/10/8` — `120s`
4. کراس‌اور — `3×12/10/10` — `75s` — final set `DS`

### Back
1. زیربغل هالتر خم — `4×12/10/8/6` — `150s`
2. لت — `4×12/10/8/6` — `150s`
3. قایقی — `3×12/10/8` — `120s`
4. پول‌داون دست صاف — `3×12/10/10` — `75s`

### Shoulders
1. پرس سرشانه اسمیت — `3×12/10/8` — `120s`
2. نشر جانب دمبل — `3×12/10/10` — `75s`
3. فلای معکوس — `3×12/10/10` — `75s`
4. شراگ — `3×12/10/10` — `75s`

### Arms
1. جلو بازو هالتر — `3×12/10/8` — `90s`
2. جلو بازو سیمکش — `3×12/10/8` — `SS-A`
3. پشت بازو طناب — `3×12/10/8` — `SS-A`
4. پشت بازو بالای سر — `3×12/10/8` — `90s`
5. جلو بازو چکشی — `3×12/10/10` — `75s`

SS-A recovery after pair: `90s`.

### Legs
1. اسکوات جلو — `4×12/10/8/6` — `150s`
2. پرس پا — `4×12/10/8/6` — `150s`
3. ددلیفت رومانیایی — `3×12/10/8` — `120s`
4. پشت پا خوابیده — `3×12/10/10` — `75s`
5. لانج دمبل — `3×12/10/8 each leg` — `120s`
6. ساق — `3×12/10/10` — `75s`

---

## Program 03 — Split + Weak Point — Intermediate

Day order:

```text
Chest + Triceps
Back + Biceps
Legs
Shoulders + Core
Weak Point / Light Full Body
```

### Day 1
1. پرس سینه هالتر — `4×12/10/8/6` — `120s`
2. بالا سینه دمبل — `4×12/10/8/6` — `120s`
3. کراس‌اور — `3×12/10/10` — `60s`
4. پشت بازو سیمکش — `3×12/10/8` — `60s`
5. پشت بازو بالای سر — `3×12/10/10` — `60s`

### Day 2
1. زیربغل هالتر — `4×12/10/8/6` — `120s`
2. لت — `4×12/10/8/6` — `120s`
3. قایقی — `3×12/10/8` — `120s`
4. جلو بازو هالتر — `3×12/10/8` — `60s`
5. چکشی — `3×12/10/10` — `60s`

### Day 3
1. اسکوات — `4×12/10/8/6` — `150s`
2. RDL — `4×12/10/8/6` — `150s`
3. پرس پا — `3×12/10/8` — `120s`
4. پشت پا خوابیده — `3×12/10/10` — `60s`
5. ساق — `3×12/10/10` — `60s`

### Day 4
1. پرس سرشانه هالتر — `3×12/10/8` — `90s`
2. نشر جانب سیمکش — `3×12/10/10` — `60s`
3. فلای معکوس — `3×12/10/10` — `60s`
4. پلانک — `3×45–60 sec` — `60s`
5. پلانک بغل — `3×30–45 sec each side` — `60s`

### Day 5
1. پرس سینه دمبل — `4×12/10/8/6` — `120s`
2. High Row — `4×12/10/8/6` — `120s`
3. پل باسن — `4×12/10/8/6` — `120s`
4. لانج — `4×12/10/8/6 each leg` — `120s`
5. نشر جانب دستگاه — `3×12/10/10` — `60s`

---

## Program 04 — Split + Weak Point — Advanced

### Day 1
1. پرس سینه هالتر — `4×12/10/8/6` — `150s`
2. بالا سینه هامر — `4×12/10/8/6` — `150s`
3. کراس‌اور — `3×12/10/10` — `75s`
4. پشت بازو طناب — `3×12/10/8` — `90s`
5. پشت بازو بالای سر — `3×12/10/10` — `75s`

### Day 2
1. High Row — `4×12/10/8/6` — `150s`
2. لت — `4×12/10/8/6` — `150s`
3. قایقی — `3×12/10/8` — `120s`
4. جلو بازو هالتر — `3×12/10/8` — `90s`
5. جلو بازو سیمکش — `3×12/10/10` — `75s`

### Day 3
1. اسکوات جلو — `4×12/10/8/6` — `150s`
2. RDL — `4×12/10/8/6` — `150s`
3. پرس پا — `3×12/10/8` — `120s`
4. پشت پا خوابیده — `3×12/10/10` — `75s`
5. ساق — `3×12/10/10` — `75s`

### Day 4
1. پرس اسمیت — `3×12/10/8` — `120s`
2. نشر جانب دمبل — `3×12/10/10` — `75s`
3. فلای معکوس — `3×12/10/10` — `75s`
4. شراگ — `3×12/10/10` — `75s`
5. پلانک — `3×45–60 sec` — `60s`

### Day 5
1. پرس سینه دمبل — `4×12/10/8/6` — `150s`
2. زیربغل هالتر — `4×12/10/8/6` — `150s`
3. پل باسن — `4×12/10/8/6` — `150s`
4. لانج — `4×12/10/8/6 each leg` — `150s`
5. نشر جانب سیمکش — `3×12/10/10` — `75s` — final set `DS`

---

## Program 05 — Upper-Priority Iranian Split — Intermediate

Day order:

```text
Chest + Triceps
Shoulders + Biceps
Legs + Core
Upper Chest + Biceps
Back + Core
```

### Day 1
1. پرس سینه هالتر — `4×12/10/8/6` — `120s`
2. بالا سینه دمبل — `4×12/10/8/6` — `120s`
3. کراس‌اور — `3×12/10/10` — `60s`
4. پشت بازو سیمکش — `3×12/10/8` — `60s`
5. پشت بازو بالای سر — `3×12/10/10` — `60s`

### Day 2
1. پرس اسمیت — `3×12/10/8` — `90s`
2. نشر جانب سیمکش — `3×12/10/10` — `60s`
3. فلای معکوس — `3×12/10/10` — `60s`
4. جلو بازو لاری — `3×12/10/8` — `60s`
5. جلو بازو چکشی — `3×12/10/10` — `60s`

### Day 3
1. اسکوات پشت — `4×12/10/8/6` — `150s`
2. پرس پا — `4×12/10/8/6` — `120s`
3. پشت پا نشسته — `3×12/10/10` — `60s`
4. ساق — `3×12/10/10` — `60s`
5. پلانک — `3×45 sec` — `60s`

### Day 4
1. بالا سینه دمبل — `4×12/10/8/6` — `120s`
2. پرس سینه دستگاه — `4×12/10/8/6` — `120s`
3. کراس‌اور — `3×12/10/10` — `60s`
4. جلو بازو سیمکش — `3×12/10/8` — `60s`
5. جلو بازو دمبل تناوبی — `3×12/10/10` — `60s`

### Day 5
1. زیربغل هالتر — `4×12/10/8/6` — `120s`
2. لت — `4×12/10/8/6` — `120s`
3. قایقی — `3×12/10/8` — `120s`
4. پول‌داون دست صاف — `3×12/10/10` — `60s`
5. پلانک بغل — `3×30–45 sec` — `60s`

---

## Program 06 — Upper-Priority Iranian Split — Advanced

### Day 1
1. پرس سینه — `4×12/10/8/6` — `150s`
2. بالا سینه هامر — `4×12/10/8/6` — `150s`
3. کراس‌اور — `3×12/10/10` — `75s`
4. پشت بازو طناب — `3×12/10/8` — `90s`
5. پشت بازو بالای سر — `3×12/10/10` — `75s`

### Day 2
1. پرس نظامی — `3×12/10/8` — `120s`
2. نشر جانب دستگاه — `3×12/10/10` — `75s`
3. فلای معکوس — `3×12/10/10` — `75s`
4. جلو بازو هالتر — `3×12/10/8` — `90s`
5. چکشی — `3×12/10/10` — `75s`

### Day 3
1. اسکوات جلو — `4×12/10/8/6` — `150s`
2. پرس پا — `4×12/10/8/6` — `150s`
3. RDL — `3×12/10/8` — `120s`
4. پشت پا خوابیده — `3×12/10/10` — `75s`
5. ساق — `3×12/10/10` — `75s`

### Day 4
1. بالا سینه دمبل — `4×12/10/8/6` — `150s`
2. پرس سینه دستگاه — `4×12/10/8/6` — `150s`
3. کراس‌اور — `3×12/10/10` — `75s` — final set `DS`
4. جلو بازو لاری — `3×12/10/8` — `90s`
5. جلو بازو سیمکش — `3×12/10/10` — `75s`

### Day 5
1. زیربغل هالتر — `4×12/10/8/6` — `150s`
2. High Row — `4×12/10/8/6` — `150s`
3. لت — `3×12/10/8` — `120s`
4. پول‌داون دست صاف — `3×12/10/10` — `75s`
5. پلانک — `3×45–60 sec` — `60s`

---

## Program 07 — Upper / Lower + Specialty — Intermediate

Day order:

```text
Upper A
Lower A
Upper B
Lower B
Arms + Delts Specialty
```

### Upper A
1. پرس سینه — `4×12/10/8/6` — `120s`
2. زیربغل هالتر — `4×12/10/8/6` — `120s`
3. لت — `4×12/10/8/6` — `120s`
4. پرس نظامی — `3×12/10/8` — `90s`
5. جلو بازو هالتر — `3×12/10/8` — `60s`
6. پشت بازو سیمکش — `3×12/10/8` — `60s`

### Lower A
1. اسکوات پشت — `4×12/10/8/6` — `150s`
2. RDL — `4×12/10/8/6` — `150s`
3. پرس پا — `3×12/10/8` — `120s`
4. پشت پا نشسته — `3×12/10/10` — `60s`
5. ساق — `3×12/10/10` — `60s`

### Upper B
1. بالا سینه دمبل — `4×12/10/8/6` — `120s`
2. قایقی — `4×12/10/8/6` — `120s`
3. High Row — `4×12/10/8/6` — `120s`
4. نشر جانب — `3×12/10/10` — `60s`
5. لاری — `3×12/10/8` — `60s`
6. پشت بازو بالای سر — `3×12/10/8` — `60s`

### Lower B
1. اسکوات جلو — `4×12/10/8/6` — `150s`
2. پل باسن — `4×12/10/8/6` — `120s`
3. لانج — `3×12/10/8 each leg` — `120s`
4. پشت پا خوابیده — `3×12/10/10` — `60s`
5. ساق — `3×12/10/10` — `60s`

### Specialty
1. پرس اسمیت — `3×12/10/8` — `90s`
2. نشر جانب دستگاه — `3×12/10/10` — `60s`
3. فلای معکوس — `3×12/10/10` — `60s`
4. جلو بازو هالتر — `3×12/10/8` — `60s`
5. پشت بازو طناب — `3×12/10/8` — `60s`
6. چکشی — `3×12/10/10` — `60s`

---

## Program 08 — Upper / Lower + Specialty — Advanced

### Upper A
1. پرس سینه — `4×12/10/8/6` — `150s`
2. زیربغل هالتر — `4×12/10/8/6` — `150s`
3. لت — `4×12/10/8/6` — `150s`
4. پرس نظامی — `3×12/10/8` — `120s`

### Lower A
1. اسکوات پشت — `4×12/10/8/6` — `150s`
2. RDL — `4×12/10/8/6` — `150s`
3. پشت پا نشسته — `3×12/10/10` — `75s`
4. ساق — `3×12/10/10` — `75s`

### Upper B
1. بالا سینه هامر — `4×12/10/8/6` — `150s`
2. قایقی — `4×12/10/8/6` — `150s`
3. پرس سینه دمبل — `4×12/10/8/6` — `150s`
4. High Row — `4×12/10/8/6` — `150s`
5. نشر جانب — `3×12/10/10` — `75s`

### Lower B
1. اسکوات جلو — `4×12/10/8/6` — `150s`
2. پرس پا — `4×12/10/8/6` — `150s`
3. پل باسن — `3×12/10/8` — `120s`
4. پشت پا خوابیده — `3×12/10/10` — `75s`
5. لانج — `3×12/10/8 each leg` — `120s`

### Specialty
1. پرس اسمیت — `3×12/10/8` — `120s`
2. فلای معکوس — `3×12/10/10` — `75s`
3. نشر جانب — `3×12/10/10` — `75s` — final set `DS`
4. جلو بازو سیمکش — `3×12/10/8` — `SS-A`
5. پشت بازو طناب — `3×12/10/8` — `SS-A`
6. چکشی — `3×12/10/8` — `90s`

SS-A recovery after pair: `90s`.

---

## Program 09 — FST-7 / Arms Priority — Intermediate

Day order:

```text
Chest + Biceps
Back + Triceps
Legs
Shoulders + Calves
Arms
```

No FST-7 technique in Intermediate.

### Day 1
1. پرس سینه دمبل — `4×12/10/8/6` — `120s`
2. بالا سینه دمبل — `4×12/10/8/6` — `120s`
3. کراس‌اور — `3×12/10/10` — `60s`
4. جلو بازو دمبل — `3×12/10/8` — `60s`
5. لاری — `3×12/10/10` — `60s`

### Day 2
1. High Row — `4×12/10/8/6` — `120s`
2. لت — `4×12/10/8/6` — `120s`
3. پول‌داون دست صاف — `3×12/10/10` — `60s`
4. پشت بازو سیمکش — `3×12/10/8` — `60s`
5. پشت بازو بالای سر — `3×12/10/10` — `60s`

### Day 3
1. اسکوات — `4×12/10/8/6` — `150s`
2. پرس پا — `4×12/10/8/6` — `120s`
3. RDL — `3×12/10/8` — `120s`
4. جلوپا — `3×12/10/10` — `60s`
5. پشت پا خوابیده — `3×12/10/10` — `60s`
6. ساق — `3×12/10/10` — `60s`

### Day 4
1. پرس اسمیت — `3×12/10/8` — `90s`
2. نشر جانب — `3×12/10/10` — `60s`
3. فلای معکوس — `3×12/10/10` — `60s`
4. شراگ — `3×12/10/10` — `60s`
5. ساق — `3×12/10/10` — `60s`

### Day 5
1. جلو بازو هالتر — `3×12/10/8` — `60s`
2. پشت بازو طناب — `3×12/10/8` — `60s`
3. جلو بازو سیمکش — `3×12/10/10` — `60s`
4. پشت بازو بالای سر — `3×12/10/10` — `60s`
5. چکشی — `3×12/10/10` — `60s`

---

## Program 10 — FST-7 / Arms Priority — Advanced

### Day 1
1. پرس سینه — `4×12/10/8/6` — `150s`
2. بالا سینه هامر — `4×12/10/8/6` — `150s`
3. کراس‌اور — `7×12/10/10/10/8/8/8` — `45–60s` — `FST-7`
4. جلو بازو هالتر — `3×12/10/8` — `90s`

### Day 2
1. زیربغل هالتر — `4×12/10/8/6` — `150s`
2. لت — `4×12/10/8/6` — `150s`
3. پول‌داون دست صاف — `7×12/10/10/10/8/8/8` — `45–60s` — `FST-7`
4. پشت بازو طناب — `3×12/10/8` — `90s`

### Day 3
1. اسکوات جلو — `4×12/10/8/6` — `150s`
2. RDL — `4×12/10/8/6` — `150s`
3. پرس پا — `3×12/10/8` — `120s`
4. جلوپا — `7×12/10/10/10/8/8/8` — `45–60s` — `FST-7`
5. پشت پا خوابیده — `3×12/10/10` — `75s`

### Day 4
1. پرس اسمیت — `3×12/10/8` — `120s`
2. فلای معکوس — `3×12/10/10` — `75s`
3. نشر جانب دستگاه — `7×12/10/10/10/8/8/8` — `30–45s` — `FST-7`
4. ساق — `3×12/10/10` — `75s`

### Day 5
1. جلو بازو هالتر — `3×12/10/8` — `90s`
2. پشت بازو طناب — `3×12/10/8` — `90s`
3. جلو بازو لاری — `7×12/10/10/10/8/8/8` — `30–45s` — `FST-7`
4. پشت بازو بالای سر — `3×12/10/10` — `75s`

---

## Program 11 — Professional Split + Compound Day — Intermediate

Day order:

```text
Chest + Triceps
Legs + Core
Back + Biceps
Shoulders
Compound Day
```

### Day 1
1. پرس سینه — `4×12/10/8/6` — `120s`
2. بالا سینه دمبل — `4×12/10/8/6` — `120s`
3. کراس‌اور — `3×12/10/10` — `60s`
4. پشت بازو سیمکش — `3×12/10/8` — `60s`

### Day 2
1. اسکوات — `4×12/10/8/6` — `150s`
2. RDL — `4×12/10/8/6` — `150s`
3. لانج — `3×12/10/8 each leg` — `120s`
4. ساق — `3×12/10/10` — `60s`
5. پلانک — `3×45–60 sec` — `60s`

### Day 3
1. لت — `4×12/10/8/6` — `120s`
2. زیربغل هالتر — `4×12/10/8/6` — `120s`
3. High Row — `3×12/10/8` — `120s`
4. جلو بازو هالتر — `3×12/10/8` — `60s`
5. جلو بازو دمبل — `3×12/10/10` — `60s`

### Day 4
1. پرس نظامی — `3×12/10/8` — `90s`
2. نشر جانب دمبل — `3×12/10/10` — `60s`
3. فلای معکوس — `3×12/10/10` — `60s`
4. شراگ — `3×12/10/10` — `60s`

### Day 5
1. RDL — `4×12/10/8/6` — `150s`
2. پرس سینه دمبل — `4×12/10/8/6` — `120s`
3. قایقی — `4×12/10/8/6` — `120s`
4. اسکوات جلو — `4×12/10/8/6` — `150s`
5. پرس اسمیت — `3×12/10/8` — `90s`

---

## Program 12 — Professional Split + Compound Day — Advanced

### Day 1
1. پرس سینه — `4×12/10/8/6` — `150s`
2. بالا سینه هامر — `4×12/10/8/6` — `150s`
3. کراس‌اور — `3×12/10/10` — `75s`
4. پشت بازو طناب — `3×12/10/8` — `90s`

### Day 2
1. اسکوات جلو — `4×12/10/8/6` — `150s`
2. پرس پا — `4×12/10/8/6` — `150s`
3. RDL — `3×12/10/8` — `120s`
4. پشت پا خوابیده — `3×12/10/10` — `75s`
5. ساق — `3×12/10/10` — `75s`

### Day 3
1. زیربغل هالتر — `4×12/10/8/6` — `150s`
2. لت — `4×12/10/8/6` — `150s`
3. قایقی — `3×12/10/8` — `120s`
4. جلو بازو هالتر — `3×12/10/8` — `90s`
5. چکشی — `3×12/10/10` — `75s`

### Day 4
1. پرس اسمیت — `3×12/10/8` — `120s`
2. نشر جانب سیمکش — `3×12/10/10` — `75s`
3. فلای معکوس — `3×12/10/10` — `75s`
4. شراگ — `3×12/10/10` — `75s`

### Day 5
1. پرس سینه دمبل — `4×12/10/8/6` — `150s`
2. High Row — `4×12/10/8/6` — `150s`
3. پل باسن — `4×12/10/8/6` — `150s`
4. لانج — `4×12/10/8/6 each leg` — `150s`
5. نشر جانب دستگاه — `3×12/10/10` — `75s`

---

# 9. Approved 6-Day Programs

## Program 13 — PPL A/B — Intermediate

Day order:

```text
Push A / Pull A / Legs A / Push B / Pull B / Legs B
```

### Push A
1. پرس سینه — `4×12/10/8/6` — `120s`
2. بالا سینه دمبل — `4×12/10/8/6` — `120s`
3. پرس نظامی — `3×12/10/8` — `90s`
4. نشر جانب — `3×12/10/10` — `60s`
5. پشت بازو سیمکش — `3×12/10/8` — `60s`

### Pull A
1. لت — `4×12/10/8/6` — `120s`
2. High Row — `4×12/10/8/6` — `120s`
3. فلای معکوس — `3×12/10/10` — `60s`
4. جلو بازو دمبل — `3×12/10/8` — `60s`
5. شراگ — `3×12/10/10` — `60s`

### Legs A
1. اسکوات پشت — `4×12/10/8/6` — `150s`
2. پرس پا — `4×12/10/8/6` — `120s`
3. جلوپا — `3×12/10/10` — `60s`
4. پشت پا نشسته — `3×12/10/10` — `60s`
5. ساق — `3×12/10/10` — `60s`

### Push B
1. پرس اسمیت — `3×12/10/8` — `90s`
2. پرس سینه دمبل — `4×12/10/8/6` — `120s`
3. بالا سینه هامر — `4×12/10/8/6` — `120s`
4. نشر جانب دمبل — `3×12/10/10` — `60s`
5. پشت بازو بالای سر — `3×12/10/8` — `60s`

### Pull B
1. قایقی — `4×12/10/8/6` — `120s`
2. زیربغل هالتر — `4×12/10/8/6` — `120s`
3. پول‌داون دست صاف — `3×12/10/10` — `60s`
4. چکشی — `3×12/10/8` — `60s`
5. فلای معکوس — `3×12/10/10` — `60s`

### Legs B
1. RDL — `4×12/10/8/6` — `150s`
2. پشت پا خوابیده — `3×12/10/10` — `60s`
3. پل باسن — `4×12/10/8/6` — `120s`
4. اسکوات جلو — `3×12/10/8` — `120s`
5. لانج — `3×12/10/8 each leg` — `120s`
6. ساق — `3×12/10/10` — `60s`

---

## Program 14 — PPL A/B — Advanced

### Push A
1. پرس سینه — `4×12/10/8/6` — `150s`
2. بالا سینه هامر — `4×12/10/8/6` — `150s`
3. کراس‌اور — `3×12/10/10` — `75s`
4. نشر جانب — `3×12/10/10` — `75s`
5. پشت بازو طناب — `3×12/10/8` — `90s`

### Pull A
1. لت — `4×12/10/8/6` — `150s`
2. High Row — `4×12/10/8/6` — `150s`
3. فلای معکوس — `3×12/10/10` — `75s`
4. جلو بازو هالتر — `3×12/10/8` — `90s`
5. شراگ — `3×12/10/10` — `75s`

### Legs A
1. اسکوات پشت — `4×12/10/8/6` — `150s`
2. پرس پا — `4×12/10/8/6` — `150s`
3. جلوپا — `3×12/10/10` — `75s` — final set `DS`
4. پشت پا نشسته — `3×12/10/10` — `75s`
5. ساق — `3×12/10/10` — `75s`

### Push B
1. پرس اسمیت — `3×12/10/8` — `120s`
2. پرس سینه دمبل — `4×12/10/8/6` — `150s`
3. کراس‌اور — `3×12/10/10` — `75s`
4. نشر جانب دمبل — `3×12/10/10` — `75s`
5. پشت بازو بالای سر — `3×12/10/8` — `90s`

### Pull B
1. زیربغل هالتر — `4×12/10/8/6` — `150s`
2. قایقی — `4×12/10/8/6` — `150s`
3. پول‌داون دست صاف — `3×12/10/10` — `75s`
4. چکشی — `3×12/10/8` — `90s`
5. فلای معکوس — `3×12/10/10` — `75s`

### Legs B
1. RDL — `4×12/10/8/6` — `150s`
2. پشت پا خوابیده — `3×12/10/10` — `75s`
3. اسکوات جلو — `4×12/10/8/6` — `150s`
4. پل باسن — `3×12/10/8` — `120s`
5. لانج — `3×12/10/8 each leg` — `120s`
6. ساق — `3×12/10/10` — `75s`

---

## Program 15 — Upper / Lower ×3 — Intermediate

Day order:

```text
Upper A / Lower A / Upper B / Lower B / Upper C / Lower C
```

### Upper A
1. پرس سینه — `4×12/10/8/6` — `120s`
2. زیربغل هالتر — `4×12/10/8/6` — `120s`
3. پرس نظامی — `3×12/10/8` — `90s`
4. لت — `4×12/10/8/6` — `120s`
5. جلو بازو — `3×12/10/8` — `60s`
6. پشت بازو — `3×12/10/8` — `60s`

### Lower A
1. اسکوات پشت — `4×12/10/8/6` — `150s`
2. پرس پا — `4×12/10/8/6` — `120s`
3. جلوپا — `3×12/10/10` — `60s`
4. پشت پا نشسته — `3×12/10/10` — `60s`
5. ساق — `3×12/10/10` — `60s`

### Upper B
1. بالا سینه دمبل — `4×12/10/8/6` — `120s`
2. قایقی — `4×12/10/8/6` — `120s`
3. High Row — `4×12/10/8/6` — `120s`
4. نشر جانب — `3×12/10/10` — `60s`
5. لاری — `3×12/10/8` — `60s`
6. پشت بازو بالای سر — `3×12/10/8` — `60s`

### Lower B
1. RDL — `4×12/10/8/6` — `150s`
2. پشت پا خوابیده — `3×12/10/10` — `60s`
3. پل باسن — `4×12/10/8/6` — `120s`
4. لانج — `3×12/10/8 each leg` — `120s`
5. ساق — `3×12/10/10` — `60s`

### Upper C
1. پرس سینه دمبل — `4×12/10/8/6` — `120s`
2. لت — `4×12/10/8/6` — `120s`
3. پرس اسمیت — `3×12/10/8` — `90s`
4. پول‌داون دست صاف — `3×12/10/10` — `60s`
5. چکشی — `3×12/10/8` — `60s`
6. پشت بازو طناب — `3×12/10/8` — `60s`

### Lower C
1. اسکوات جلو — `4×12/10/8/6` — `150s`
2. پرس پا — `4×12/10/8/6` — `120s`
3. پشت پا نشسته — `3×12/10/10` — `60s`
4. لانج — `3×12/10/8 each leg` — `120s`
5. ساق — `3×12/10/10` — `60s`
6. پلانک بغل — `3×30–45 sec` — `60s`

---

## Program 16 — Upper / Lower ×3 — Advanced

### Upper A
1. پرس سینه — `4×12/10/8/6` — `150s`
2. زیربغل هالتر — `4×12/10/8/6` — `150s`
3. پرس نظامی — `3×12/10/8` — `120s`
4. لت — `4×12/10/8/6` — `150s`

### Lower A
1. اسکوات پشت — `4×12/10/8/6` — `150s`
2. پرس پا — `4×12/10/8/6` — `150s`
3. جلوپا — `3×12/10/10` — `75s`
4. پشت پا نشسته — `3×12/10/10` — `75s`
5. ساق — `3×12/10/10` — `75s`

### Upper B
1. بالا سینه هامر — `4×12/10/8/6` — `150s`
2. قایقی — `4×12/10/8/6` — `150s`
3. High Row — `4×12/10/8/6` — `150s`
4. نشر جانب — `3×12/10/10` — `75s` — final set `DS`
5. لاری — `3×12/10/8` — `90s`
6. پشت بازو بالای سر — `3×12/10/8` — `90s`

### Lower B
1. RDL — `4×12/10/8/6` — `150s`
2. پشت پا خوابیده — `3×12/10/10` — `75s`
3. پل باسن — `4×12/10/8/6` — `150s`
4. لانج — `3×12/10/8 each leg` — `120s`
5. ساق — `3×12/10/10` — `75s`

### Upper C
1. پرس سینه دمبل — `4×12/10/8/6` — `150s`
2. لت — `4×12/10/8/6` — `150s`
3. پرس اسمیت — `3×12/10/8` — `120s`
4. پول‌داون دست صاف — `3×12/10/10` — `75s`
5. جلو بازو سیمکش — `3×12/10/8` — `SS-A`
6. پشت بازو طناب — `3×12/10/8` — `SS-A`

SS-A recovery after pair: `90s`.

### Lower C
1. اسکوات جلو — `4×12/10/8/6` — `150s`
2. پرس پا — `4×12/10/8/6` — `150s`
3. پشت پا نشسته — `3×12/10/10` — `75s`
4. لانج — `3×12/10/8 each leg` — `120s`
5. ساق — `3×12/10/10` — `75s`
6. پلانک بغل — `3×30–45 sec` — `60s`

---

## Program 17 — FitClub Hybrid — Intermediate

Day order:

```text
Chest + Triceps
Back + Biceps
Legs
Shoulders + Core
Chest + Back
Posterior + Core
```

### Day 1
1. پرس سینه — `4×12/10/8/6` — `120s`
2. بالا سینه دمبل — `4×12/10/8/6` — `120s`
3. کراس‌اور — `3×12/10/10` — `60s`
4. پشت بازو سیمکش — `3×12/10/8` — `60s`
5. پشت بازو بالای سر — `3×12/10/10` — `60s`

### Day 2
1. زیربغل هالتر — `4×12/10/8/6` — `120s`
2. لت — `4×12/10/8/6` — `120s`
3. High Row — `3×12/10/8` — `120s`
4. جلو بازو سیمکش — `3×12/10/8` — `60s`
5. چکشی — `3×12/10/10` — `60s`

### Day 3
1. اسکوات — `4×12/10/8/6` — `150s`
2. پرس پا — `4×12/10/8/6` — `120s`
3. جلوپا — `3×12/10/10` — `60s`
4. پشت پا نشسته — `3×12/10/10` — `60s`
5. ساق — `3×12/10/10` — `60s`

### Day 4
1. پرس نظامی — `3×12/10/8` — `90s`
2. نشر جانب — `3×12/10/10` — `60s`
3. فلای معکوس — `3×12/10/10` — `60s`
4. شراگ — `3×12/10/10` — `60s`
5. پلانک — `3×45–60 sec` — `60s`

### Day 5
1. پرس سینه دستگاه — `4×12/10/8/6` — `120s`
2. قایقی — `4×12/10/8/6` — `120s`
3. بالا سینه هامر — `4×12/10/8/6` — `120s`
4. لت — `4×12/10/8/6` — `120s`
5. کراس‌اور — `3×12/10/10` — `60s`
6. پول‌داون دست صاف — `3×12/10/10` — `60s`

### Day 6
1. RDL — `4×12/10/8/6` — `150s`
2. پشت پا خوابیده — `3×12/10/10` — `60s`
3. پل باسن — `4×12/10/8/6` — `120s`
4. لانج — `3×12/10/8 each leg` — `120s`
5. ساق — `3×12/10/10` — `60s`
6. پلانک بغل — `3×30–45 sec` — `60s`

---

## Program 18 — FitClub Hybrid — Advanced

### Day 1 — Chest + Triceps
1. پرس سینه — `4×12/10/8/6` — `150s`
2. بالا سینه دمبل — `4×12/10/8/6` — `150s`
3. کراس‌اور — `3×12/10/10` — `75s`
4. پشت بازو سیمکش — `3×12/10/8` — `90s`
5. پشت بازو بالای سر — `3×12/10/10` — `75s`

### Day 2 — Back + Biceps
1. زیربغل هالتر — `4×12/10/8/6` — `150s`
2. لت — `4×12/10/8/6` — `150s`
3. High Row — `3×12/10/8` — `120s`
4. جلو بازو سیمکش — `3×12/10/8` — `90s`
5. چکشی — `3×12/10/10` — `75s`

### Day 3 — Legs
1. اسکوات — `4×12/10/8/6` — `150s`
2. پرس پا — `4×12/10/8/6` — `150s`
3. جلوپا — `3×12/10/10` — `75s`
4. پشت پا نشسته — `3×12/10/10` — `75s`
5. ساق — `3×12/10/10` — `75s`

### Day 4 — Shoulders + Core
1. پرس نظامی — `3×12/10/8` — `120s`
2. نشر جانب — `3×12/10/10` — `75s`
3. فلای معکوس — `3×12/10/10` — `75s`
4. شراگ — `3×12/10/10` — `75s`
5. پلانک — `3×45–60 sec` — `60s`

### Day 5
1. پرس سینه دستگاه — `4×12/10/8/6` — `150s`
2. قایقی — `4×12/10/8/6` — `150s`
3. کراس‌اور — `3×12/10/8` — `SS-A`
4. پول‌داون دست صاف — `3×12/10/8` — `SS-A`
5. بالا سینه هامر — `4×12/10/8/6` — `150s`
6. لت — `4×12/10/8/6` — `150s`

SS-A recovery after pair: `90s`.

### Day 6
1. RDL — `4×12/10/8/6` — `150s`
2. پشت پا خوابیده — `3×12/10/10` — `75s`
3. پل باسن — `4×12/10/8/6` — `150s`
4. لانج — `3×12/10/8 each leg` — `120s`
5. ساق — `3×12/10/10` — `75s`
6. Core — same approved plank/side-plank pattern

---

## Program 19 — Arnold Split — Intermediate

Day order:

```text
Chest + Back A
Shoulders + Arms A
Legs A
Chest + Back B
Shoulders + Arms B
Legs B
```

### Day 1
1. پرس سینه — `4×12/10/8/6` — `120s`
2. زیربغل هالتر — `4×12/10/8/6` — `120s`
3. بالا سینه دمبل — `4×12/10/8/6` — `120s`
4. لت — `4×12/10/8/6` — `120s`
5. کراس‌اور — `3×12/10/10` — `60s`
6. پول‌داون دست صاف — `3×12/10/10` — `60s`

### Day 2
1. پرس نظامی — `3×12/10/8` — `90s`
2. نشر جانب — `3×12/10/10` — `60s`
3. فلای معکوس — `3×12/10/10` — `60s`
4. جلو بازو هالتر — `3×12/10/8` — `60s`
5. پشت بازو سیمکش — `3×12/10/8` — `60s`
6. چکشی — `3×12/10/10` — `60s`

### Day 3
1. اسکوات — `4×12/10/8/6` — `150s`
2. پرس پا — `4×12/10/8/6` — `120s`
3. پشت پا نشسته — `3×12/10/10` — `60s`
4. ساق — `3×12/10/10` — `60s`

### Day 4
1. پرس سینه دمبل — `4×12/10/8/6` — `120s`
2. قایقی — `4×12/10/8/6` — `120s`
3. بالا سینه هامر — `4×12/10/8/6` — `120s`
4. High Row — `4×12/10/8/6` — `120s`
5. کراس‌اور — `3×12/10/10` — `60s`
6. لت — `3×12/10/8` — `120s`

### Day 5
1. پرس اسمیت — `3×12/10/8` — `90s`
2. نشر جانب دمبل — `3×12/10/10` — `60s`
3. فلای معکوس — `3×12/10/10` — `60s`
4. لاری — `3×12/10/8` — `60s`
5. پشت بازو بالای سر — `3×12/10/8` — `60s`
6. جلو بازو سیمکش — `3×12/10/10` — `60s`

### Day 6
1. RDL — `4×12/10/8/6` — `150s`
2. اسکوات جلو — `4×12/10/8/6` — `150s`
3. پشت پا خوابیده — `3×12/10/10` — `60s`
4. پل باسن — `3×12/10/8` — `120s`
5. لانج — `3×12/10/8 each leg` — `120s`
6. ساق — `3×12/10/10` — `60s`

---

## Program 20 — Arnold Split — Advanced

### Day 1
1. پرس سینه — `4×12/10/8/6` — `150s`
2. زیربغل هالتر — `4×12/10/8/6` — `150s`
3. بالا سینه دمبل — `3×12/10/8` — `SS-A`
4. لت — `3×12/10/8` — `SS-A`
5. کراس‌اور — `3×12/10/8` — `SS-B`
6. پول‌داون دست صاف — `3×12/10/8` — `SS-B`

SS-A recovery: `120s after pair`
SS-B recovery: `90s after pair`

### Day 2
1. پرس نظامی — `3×12/10/8` — `120s`
2. نشر جانب — `3×12/10/10` — `75s`
3. فلای معکوس — `3×12/10/10` — `75s`
4. جلو بازو هالتر — `3×12/10/8` — `SS-A`
5. پشت بازو طناب — `3×12/10/8` — `SS-A`

Recovery: `90s after pair`.

### Day 3
1. اسکوات — `4×12/10/8/6` — `150s`
2. پرس پا — `4×12/10/8/6` — `150s`
3. پشت پا نشسته — `3×12/10/10` — `75s`
4. ساق — `3×12/10/10` — `75s`

### Day 4
1. پرس سینه دمبل — `4×12/10/8/6` — `150s`
2. قایقی — `4×12/10/8/6` — `150s`
3. بالا سینه هامر — `3×12/10/8` — `SS-A`
4. High Row — `3×12/10/8` — `SS-A`
5. کراس‌اور — `3×12/10/10` — `75s`
6. لت — `3×12/10/8` — `120s`

### Day 5
1. پرس اسمیت — `3×12/10/8` — `120s`
2. نشر جانب دستگاه — `3×12/10/10` — `75s`
3. لاری — `3×12/10/8` — `SS-A`
4. پشت بازو بالای سر — `3×12/10/8` — `SS-A`
5. چکشی — `3×12/10/8` — `90s`

### Day 6
1. RDL — `4×12/10/8/6` — `150s`
2. اسکوات جلو — `4×12/10/8/6` — `150s`
3. پشت پا خوابیده — `3×12/10/10` — `75s`
4. پل باسن — `3×12/10/8` — `120s`
5. لانج — `3×12/10/8 each leg` — `120s`
6. ساق — `3×12/10/10` — `75s`

---

## Program 21 — Classic Six Body-Part — Intermediate

Day order:

```text
Chest / Biceps / Legs / Triceps / Back / Shoulders
```

### Chest
1. پرس سینه — `4×12/10/8/6` — `120s`
2. بالا سینه دمبل — `4×12/10/8/6` — `120s`
3. پرس دستگاه — `3×12/10/8` — `120s`
4. کراس‌اور — `3×12/10/10` — `60s`

### Biceps
1. جلو بازو هالتر — `3×12/10/8` — `60s`
2. لاری — `3×12/10/10` — `60s`
3. چکشی — `3×12/10/10` — `60s`
4. سیمکش — `3×12/10/10` — `60s`

### Legs
1. اسکوات — `4×12/10/8/6` — `150s`
2. پرس پا — `4×12/10/8/6` — `120s`
3. RDL — `3×12/10/8` — `120s`
4. پشت پا نشسته — `3×12/10/10` — `60s`
5. ساق — `3×12/10/10` — `60s`

### Triceps
1. پشت بازو سیمکش — `3×12/10/8` — `60s`
2. پشت بازو طناب — `3×12/10/10` — `60s`
3. پشت بازو بالای سر — `3×12/10/10` — `60s`

### Back
1. زیربغل هالتر — `4×12/10/8/6` — `120s`
2. لت — `4×12/10/8/6` — `120s`
3. قایقی — `3×12/10/8` — `120s`
4. High Row — `3×12/10/8` — `120s`
5. پول‌داون دست صاف — `3×12/10/10` — `60s`

### Shoulders
1. پرس نظامی — `3×12/10/8` — `90s`
2. نشر جانب — `3×12/10/10` — `60s`
3. فلای معکوس — `3×12/10/10` — `60s`
4. شراگ — `3×12/10/10` — `60s`

---

## Program 22 — Classic Six Body-Part — Advanced

### Chest
1. پرس سینه — `4×12/10/8/6` — `150s`
2. بالا سینه هامر — `4×12/10/8/6` — `150s`
3. پرس دمبل — `3×12/10/8` — `120s`
4. کراس‌اور — `3×12/10/10` — `75s` — final set `DS`

### Biceps
1. جلو بازو هالتر — `3×12/10/8` — `90s`
2. لاری — `3×12/10/10` — `75s`
3. سیمکش — `3×12/10/10` — `75s`
4. چکشی — `3×12/10/10` — `75s`

### Legs
1. اسکوات جلو — `4×12/10/8/6` — `150s`
2. پرس پا — `4×12/10/8/6` — `150s`
3. RDL — `3×12/10/8` — `120s`
4. پشت پا خوابیده — `3×12/10/10` — `75s`
5. ساق — `3×12/10/10` — `75s`

### Triceps
1. پشت بازو سیمکش — `3×12/10/8` — `90s`
2. پشت بازو طناب — `3×12/10/10` — `75s`
3. پشت بازو بالای سر — `3×12/10/10` — `75s`

### Back
1. زیربغل هالتر — `4×12/10/8/6` — `150s`
2. لت — `4×12/10/8/6` — `150s`
3. قایقی — `3×12/10/8` — `120s`
4. پول‌داون دست صاف — `3×12/10/10` — `75s`

### Shoulders
1. پرس اسمیت — `3×12/10/8` — `120s`
2. نشر جانب سیمکش — `3×12/10/10` — `75s`
3. فلای معکوس — `3×12/10/10` — `75s`
4. شراگ — `3×12/10/10` — `75s`

---

## Program 23 — Ronnie Double Exposure — Intermediate

Day order:

```text
Back + Biceps + Shoulders A
Legs A
Chest + Triceps A
Back + Biceps + Shoulders B
Legs B
Chest + Triceps B
```

### Day 1
1. لت — `4×12/10/8/6` — `120s`
2. زیربغل هالتر — `4×12/10/8/6` — `120s`
3. فلای معکوس — `3×12/10/10` — `60s`
4. جلو بازو دمبل — `3×12/10/8` — `60s`
5. نشر جانب سیمکش — `3×12/10/10` — `60s`

### Day 2
1. اسکوات — `4×12/10/8/6` — `150s`
2. پرس پا — `4×12/10/8/6` — `120s`
3. جلوپا — `3×12/10/10` — `60s`
4. پشت پا نشسته — `3×12/10/10` — `60s`
5. ساق — `3×12/10/10` — `60s`

### Day 3
1. پرس سینه — `4×12/10/8/6` — `120s`
2. بالا سینه دمبل — `4×12/10/8/6` — `120s`
3. کراس‌اور — `3×12/10/10` — `60s`
4. پشت بازو سیمکش — `3×12/10/8` — `60s`
5. پشت بازو بالای سر — `3×12/10/10` — `60s`

### Day 4
1. قایقی — `4×12/10/8/6` — `120s`
2. High Row — `4×12/10/8/6` — `120s`
3. پول‌داون دست صاف — `3×12/10/10` — `60s`
4. چکشی — `3×12/10/8` — `60s`
5. پرس اسمیت — `3×12/10/8` — `90s`

### Day 5
1. RDL — `4×12/10/8/6` — `150s`
2. پشت پا خوابیده — `3×12/10/10` — `60s`
3. پل باسن — `4×12/10/8/6` — `120s`
4. اسکوات جلو — `3×12/10/8` — `120s`
5. لانج — `3×12/10/8 each leg` — `120s`
6. ساق — `3×12/10/10` — `60s`

### Day 6
1. پرس سینه دمبل — `4×12/10/8/6` — `120s`
2. بالا سینه هامر — `4×12/10/8/6` — `120s`
3. کراس‌اور — `3×12/10/10` — `60s`
4. پشت بازو طناب — `3×12/10/8` — `60s`
5. پشت بازو بالای سر — `3×12/10/10` — `60s`

---

## Program 24 — Ronnie Double Exposure — Advanced

### Day 1
1. لت — `4×12/10/8/6` — `150s`
2. زیربغل هالتر — `4×12/10/8/6` — `150s`
3. فلای معکوس — `3×12/10/10` — `75s`
4. جلو بازو هالتر — `3×12/10/8` — `90s`
5. نشر جانب سیمکش — `3×12/10/10` — `75s`

### Day 2
1. اسکوات — `4×12/10/8/6` — `150s`
2. پرس پا — `4×12/10/8/6` — `150s`
3. جلوپا — `3×12/10/10` — `75s`
4. پشت پا نشسته — `3×12/10/10` — `75s`
5. ساق — `3×12/10/10` — `75s`

### Day 3
1. پرس سینه — `4×12/10/8/6` — `150s`
2. بالا سینه هامر — `4×12/10/8/6` — `150s`
3. کراس‌اور — `3×12/10/10` — `75s`
4. پشت بازو سیمکش — `3×12/10/8` — `90s`
5. پشت بازو بالای سر — `3×12/10/10` — `75s`

### Day 4
1. قایقی — `4×12/10/8/6` — `150s`
2. High Row — `4×12/10/8/6` — `150s`
3. پول‌داون دست صاف — `3×12/10/10` — `75s`
4. چکشی — `3×12/10/8` — `90s`
5. پرس اسمیت — `3×12/10/8` — `120s`
6. نشر جانب سیمکش — `3×12/10/10` — `75s` — final set `DS`

### Day 5
1. RDL — `4×12/10/8/6` — `150s`
2. اسکوات جلو — `4×12/10/8/6` — `150s`
3. پشت پا خوابیده — `3×12/10/10` — `75s`
4. پل باسن — `3×12/10/8` — `120s`
5. لانج — `3×12/10/8 each leg` — `120s`
6. ساق — `3×12/10/10` — `75s`

### Day 6
1. پرس سینه دمبل — `4×12/10/8/6` — `150s`
2. بالا سینه دمبل — `4×12/10/8/6` — `150s`
3. کراس‌اور — `3×12/10/10` — `75s`
4. پشت بازو طناب — `3×12/10/8` — `90s`
5. پشت بازو بالای سر — `3×12/10/10` — `75s`

---

# 10. Implementation Phases

## Phase A — Discovery

1. Read current seed/template architecture.
2. Enumerate current structures.
3. Enumerate current level-specific default programs.
4. Determine which approved structures already exist.
5. Determine which must be added.
6. Validate all Exercise Library identities.
7. Capture frozen 2/3/4-day signatures.

Do not edit before completing this phase.

## Phase B — Structure Layer

For every approved base structure:
- reuse an existing semantically identical structure when possible,
- otherwise add a new canonical structure using existing dataclasses/models,
- define correct day count, order, names, focus tags, and supported levels.

The approved variants for every structure in this task are:

```text
Intermediate
Advanced
```

Do not alter 2/3/4-day supported levels.

## Phase C — Level-Specific Program Rows

Create one deterministic program row per:

```text
approved structure × approved level
```

Exactly 24 approved program rows must result.

Seed reruns must not duplicate them.

## Phase D — Exercise Linking

For every ProgramExercise:
1. resolve real Exercise Library record,
2. populate current FK/reference,
3. preserve stable identity,
4. do not create duplicate Exercise rows.

## Phase E — Prescription

Persist the approved:
- sets
- rep_min
- rep_max
- duration mode for timed core exercises
- target RIR
- rest
- intensity method
- superset group

If the current schema supports duration separately, use duration mode correctly for plank work.

---

# 11. RIR Assignment

If a line does not explicitly repeat RIR:

## Intermediate

```text
major compound: RIR 2
secondary compound: RIR 2
isolation: RIR 2
duration/core: use existing duration semantics
```

## Advanced

```text
heavy primary compound: RIR 1
secondary compound: RIR 2
isolation: RIR 2
```

For final drop-set extension, the extension may approach technical failure / ~0–1 RIR.

If only one `target_rir` field exists, store the normal-set target and represent the final-set exception with the intensity method.

---

# 12. Required Tests

Add/extend tests for all of the following.

## Frozen 2/3/4-Day Catalog

Assert:

```text
before_signature == after_signature
```

No 2/3/4-day content changes.

## Approved Addition Count

Exactly:

```text
12 approved 5-day
12 approved 6-day
24 approved additions
```

## Level Coverage

Every approved structure has:

```text
Intermediate
Advanced
```

## Program Uniqueness

No duplicate stable program identity.

No duplicate `(structure, level)` pair for this approved catalog.

Seed is idempotent.

## Day Count

Every approved 5-day program has exactly 5 days.

Every approved 6-day program has exactly 6 days.

## Day Order

Verify exact day order for all 12 structures.

## Exercise Resolution

Every ProgramExercise must satisfy:

```text
exercise exists
exercise is active when modeled
exercise is programmable
exercise FK/reference is non-null
```

No unresolved exercise identity.

## Prescription

Verify:
- sets
- reps
- duration
- rest
- RIR
- intensity method
- superset grouping
- drop-set assignment
against this specification.

## Pyramid Prescription Validation

Add explicit assertions that:

```text
no normal rep target is below 6
```

For each large-muscle day/block:

```text
first eligible compound = 4×12/10/8/6
second eligible compound = 4×12/10/8/6
```

unless that exercise is explicitly part of a superset.

For later large-muscle compounds:

```text
3×12/10/8
```

For large-muscle isolation/accessory work:

```text
3×12/10/10
```

For shoulders, biceps, triceps, and calves:

```text
mostly 3 working sets
main movement: 3×12/10/8
secondary/isolation: 3×12/10/10
```

For every superset:

```text
exactly 3 rounds
each paired exercise uses 12/10/8
```

For Program 10 FST-7 movements:

```text
7×12/10/10/10/8/8/8
```

## Technique Safety

Assert:
- no heavy barbell primary movement gets a drop set,
- drop sets occur only where explicitly marked,
- superset groups contain the intended pairs,
- Intermediate programs do not receive Advanced-only techniques,
- FST-7 seven-set prescriptions appear only in Program 10.

## Scope

Verify:
- Program Engine behavior unchanged unless explicitly required,
- 2/3/4-day catalog unchanged,
- no Exercise Library duplicate created,
- no unrelated default program deleted.

---

# 13. Admin / API Verification

After seed, verify the relevant API/service exposes the additions.

Expected grouping:

```text
5 days
  -> structure
      -> Intermediate
      -> Advanced

6 days
  -> structure
      -> Intermediate
      -> Advanced
```

Do not redesign UI unless a minimal compatibility fix is required to display a newly introduced structure name.

---

# 14. Database / Seed Verification

Run the actual seed path against an appropriate test/dev database.

Verify:

```text
seed once  -> expected additions
seed twice -> same result, no duplicates
```

Check all Exercise FK references.

---

# 15. Scope Review

Before finishing:

```bash
git status
git diff
```

Explicitly verify:

1. No existing 2-day program changed.
2. No existing 3-day program changed.
3. No existing 4-day program changed.
4. No unrelated Exercise Library record changed.
5. No unrelated Program Engine file changed.
6. No broad formatting occurred.
7. No unnecessary migration.
8. No unrelated dependency change.
9. Only required 5/6-day catalog functionality changed.

Do not revert unrelated pre-existing user changes.

Distinguish pre-existing working-tree changes from changes made by this task.

---

# 16. Testing

Run at minimum:

- training template tests
- default program library tests
- exercise-linking tests
- seed/idempotency tests
- supported-level tests
- API/service program-library tests
- frozen 2/3/4-day snapshot tests
- intensity method / superset / drop-set tests
- relevant backend tests

Run the broader backend suite if reasonably possible.

If a test fails:
1. find the real cause,
2. fix implementation,
3. do not weaken tests merely to get green output.

---

# 17. Final Report

The final report must include:

## Files Changed
Exact file list.

## Structures
List structures reused and structures newly added, with canonical slugs.

## Program Count

```text
new approved 5-day programs = 12
new approved 6-day programs = 12
new approved total = 24
```

Also report total Default Program Library count after implementation.

## 2/3/4-Day Preservation

Explicitly report whether:

```text
before_signature == after_signature
```

and confirm no 2/3/4-day program changed.

## Exercise Resolution

Report whether all requested exercise references resolved.

If any requested identity changed:

| Requested Exercise | Requested Identity | Actual Fitsho Identity | Reason |
|---|---|---|---|

## Techniques

Report implementation of:
- Supersets
- Drop Sets
- FST-7 representation

## Database / Migration

State whether schema/migration changed and why.

## Program Engine

State:

```text
Program Engine changed: yes/no
```

If yes, exact reason and files.

## Tests

List test commands/groups and results.

## Final 24-Row Summary

Provide exactly 24 rows:

| # | Days | Structure | Level | Created/Updated | Validation |
|---:|---:|---|---|---|---|

Rows must correspond to Programs 01–24 in this document.

## Git Scope Summary

Summarize final diff and confirm unrelated pre-existing changes remained untouched.

---

# Completion Gate

Do not declare completion until all applicable items are true:

```text
[ ] 24 approved programs exist
[ ] 12 are 5-day
[ ] 12 are 6-day
[ ] all 12 base structures have Intermediate + Advanced variants
[ ] all approved programs have exact day order
[ ] every exercise resolves to a real Fitsho Exercise Library record
[ ] prescriptions match this specification
[ ] no normal working-set target is below 6 reps
[ ] first two eligible large-muscle compounds use 4×12/10/8/6 unless supersetted
[ ] smaller-muscle exercises are mostly 3-set prescriptions
[ ] every superset uses exactly 3 rounds
[ ] supersets/drop sets/FST-7 are represented correctly
[ ] seed is idempotent
[ ] no duplicate default programs
[ ] all existing 2/3/4-day signatures are unchanged
[ ] Program Engine behavior was not unintentionally modified
[ ] relevant tests pass
[ ] git diff is within scope
```

Do not stop before the completion gate is satisfied.