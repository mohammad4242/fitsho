# Program Engine V1 Examples and Comparisons

## Example normalized input

```json
{
  "user_id": "00000000-0000-0000-0000-000000000001",
  "age": 30,
  "height_cm": 175,
  "weight_kg": 75,
  "primary_goal": "fat_loss",
  "training_experience": "beginner",
  "training_age_months": 3,
  "available_training_days": 3,
  "session_duration_minutes": 45,
  "available_equipment": ["bodyweight", "dumbbell"],
  "training_location": "home",
  "impact_limit": "low",
  "sleep_quality": "average",
  "stress_level": "average",
  "program_duration_weeks": 4,
  "seed_optional": 1234
}
```

## Example generated output excerpt

```json
{
  "engine_version": "program_engine_v1",
  "ruleset_version": "resistance_training_v1",
  "seed": 1234,
  "primary_goal": "fat_loss",
  "training_status": "novice",
  "safety_status": "clear",
  "split": "full_body_abc",
  "weekly_schedule": [
    {
      "day_index": 1,
      "weekday": 0,
      "focus": "full_body_a",
      "estimated_duration_minutes": 45,
      "exercises": [
        {
          "exercise_name": "Push Up",
          "sets": 3,
          "rep_min": 8,
          "rep_max": 15,
          "target_rir": 3,
          "rest_seconds": 90,
          "warmup_sets": 2,
          "reason_codes": ["GOAL_SPECIFIC", "EQUIPMENT_MATCH", "TIME_EFFICIENT"]
        }
      ],
      "cardio": {
        "modality_name": "March",
        "duration_minutes": 10,
        "intensity": "moderate",
        "reason_codes": ["LOW_IMPACT_CARDIO_SELECTED"]
      }
    }
  ],
  "validation_report": {"errors": [], "warnings": []}
}
```

IDs and complete schedules are intentionally omitted from the documentation excerpt; executable
fixtures are the source of truth.

## Old versus new comparisons

### Novice, six available days, poor recovery

- Before: the day count could pass straight through and the validator accepted six demanding days.
- Root cause: no recovery-aware split stage.
- V1: full-body A/B/C, maximum three resistance days, spaced 0/2/4.
- Correcting rule: `SPLIT_REDUCED_FOR_RECOVERY` and volume reductions for each recovery signal.
- Validation: no errors; day count 3; recovery days 4; volume bounded at the novice floor.
- Limitation: readiness is self-reported; V1 does not infer clinical recovery status.

### Novice, three days

- Before: AI could choose P/P/L, leaving most muscles at one exposure, or fallback days could repeat.
- Root cause: number of days acted as the split rule; no scored candidates or frequency invariant.
- V1: full-body A/B/C with push, pull, knee-dominant, hinge, and trunk coverage distributed across
  the week; short sessions rotate priorities instead of repeating the same three slots.
- Correcting rule: `SPLIT_SIMPLIFIED_FOR_NOVICE` and hard weekly movement coverage.
- Validation: no errors; three requested days; deterministic repeated core movements carry an explicit
  progression reason.
- Limitation: V1's slot taxonomy is general-fitness focused, not sport-specific periodization.

### Fat loss, 45 minutes, low impact

- Before: a reproduced output had 28 resistance slots, one generic prescription, and no cardio.
- Root cause: exercises were selected before weekly volume; cardio had no independent model.
- V1: quality resistance work remains primary, low-impact moderate cardio is a separate 10-minute
  prescription, and total duration fits the session tolerance.
- Correcting rule: weekly volume before selection, `LOW_IMPACT_CARDIO_SELECTED`, and duration fitting.
- Validation: no errors; resistance exercises present; high-impact cardio rejected; cardio minutes
  reported separately.
- Limitation: long-term WHO targets require progressive updates from logged adherence, not an automatic
  week-one jump.

### One day, 45 minutes, bodyweight

- Before: a plan missing pulling and trunk work passed validation.
- Root cause: validator counted valid IDs but not weekly movement coverage.
- V1: full body with push, pull, knee-dominant, hinge, and trunk work. If that coverage cannot fit
  safely, generation returns a structured failure instead of dropping an essential pattern.
- Correcting rule: required safe patterns and time-prioritized session assembly.
- Validation: no errors; equipment subset holds; duration is within tolerance.
- Limitation: a usable bodyweight pull exercise must exist with reviewed metadata; otherwise generation
  returns `NO_SAFE_EXERCISE_FOR_PATTERN` instead of inventing one.

### Shoulder limitation with no overhead movement

- Before: shoulder caution could create repeated incoherent days or fail only after construction.
- Root cause: partial caution mapping without an explicit movement constraint stage.
- V1: vertical pressing and overhead-tagged candidates are removed before scoring; horizontal safe work
  remains eligible.
- Correcting rule: blocked pattern/tag hard filters and independent substitution eligibility.
- Validation: no errors; no vertical press; no blocked caution tag.
- Limitation: ambiguous free text still requires professional review; the engine does not guess ROM.
