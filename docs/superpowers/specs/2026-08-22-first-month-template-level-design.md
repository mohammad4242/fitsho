# First-Month Template Experience Level

## Scope

Preserve the profile's four-level `ExperienceLevel` value through deterministic
workout generation so template selection can distinguish `FIRST_MONTH` from
`BEGINNER`, without changing the derived programming `TrainingStatus` model.

This phase does not change Goal filtering, template scoring, sex behavior,
priority scoring, safety/equipment constraints, template families, or dynamic
fallback.

## Data flow

The existing `ProgramGenerationRequest.training_experience` field remains the
single request-level experience input. Its engine enum gains the missing
`FIRST_MONTH` value, allowing the service to pass the profile value unchanged.
The normalized request keeps that original value in `source.training_experience`.

Normalization continues to derive `TrainingStatus` independently:

- `FIRST_MONTH` and `BEGINNER` map to `NOVICE` programming status;
- training age and recent consistency may reduce status conservatively; and
- the preserved template experience level is never rewritten by those status
  reductions.

Template selection reads the preserved experience value from the normalized
request source and compares its string value to the existing template reference
level. Training status remains the input for difficulty, volume, recovery,
prescription, safety, and other programming rules.

## Compatibility

Existing callers that provide `BEGINNER`, `INTERMEDIATE`, or `ADVANCED` retain
their current behavior. Existing database templates and the engine reference
loader require no schema or seed changes. Since no FIRST_MONTH templates are
currently seeded, selector tests use an in-memory `TemplateReference` fixture
to prove the path without creating a template family.

## Tests

Regression coverage will verify:

- service-to-request preservation for `FIRST_MONTH`;
- distinct FIRST_MONTH and BEGINNER template selection;
- shared NOVICE status for conservative first-month/beginner inputs;
- independent template level when training age reduces status;
- unchanged intermediate and advanced level/status behavior; and
- deterministic normalization and selection for repeated identical inputs.
