# Canonical Template Tagging System

Date: 2026-08-22
Scope: Phase 5 only
Status: Approved approach

## Goal

Replace unrestricted workout-template `focus_tags` conventions with one typed,
documented, validated vocabulary. Keep JSON/string persistence and existing score
magnitudes. Do not implement Phase 6 scoring.

## Audit baseline

The pre-Phase-5 seed library contained these tag values:

`arms_priority`, `back_priority`, `balanced`, `body_part_rotation`,
`chest_priority`, `classic`, `compound_first`, `compound_focus`,
`direct_targets`, `drop_set`, `fat_loss`, `foundation`, `frequency_two`,
`full_body`, `general_fitness`, `hamstrings_glutes`, `high_frequency`,
`hypertrophy`, `legs_priority`, `long_session`, `push_pull_legs`,
`quad_priority`, `shoulders_priority`, `specialization`, `strength`,
`strength_hypertrophy`, `superset`, `three_day`, `time_efficient`,
`upper_lower`, `volume`, and `weak_point`.

Tag producers and persistence boundaries:

- `training_templates/seed_data.py`: Fitsho-managed template metadata.
- `admin/schemas.py` and `training_templates/admin_service.py`: admin writes.
- `training_templates/models.py`: JSON string persistence.
- `training_templates/service.py`: managed reseeding.
- `training_templates/engine_reference.py`: persisted model to engine reference.
- `workouts/program_engine/schemas.py`: immutable engine reference shape.
- `frontend/src/features/admin/AdminTrainingTemplateEditorPage.tsx`: admin form input.

Runtime consumers:

- `workouts/program_engine/template_selector.py`: priority, Body Analysis, and
  balanced-template score inputs.
- `workouts/program_engine/body_analysis.py`: muscle-to-template-tag matching.
- `workouts/ai_coach.py`: deterministic candidate priority score.
- `training_templates/seed_data.py`: rationale text and structural seed helpers.
- `frontend/src/features/admin/AdminTrainingTemplatesPage.tsx`: display labels.

`priority_allocation.py` does not consume template tags. It consumes normalized
priority muscles and Body Analysis muscles, so Phase 5 must not change its policy.

Legacy runtime dependencies found:

- `classic` granted the selector's existing balanced-template bonus.
- `long_session` applied a short-session penalty.
- Program Engine priority matching generated `<muscle>_priority` dynamically.
- Body Analysis kept a separate alias-aware mapping including `legs_priority`,
  `posterior_chain_priority`, `calf_priority`, and `core_priority`.
- AI Coach compared muscle values directly with focus tags.

The partial implementation already present at the audit baseline introduced
`training_templates/tags.py`, but still retained seed-only legacy aliases and
slug-specific normalization, lacked category-level validation, left raw tag
strings in producers/tests, and left a non-canonical frontend default.

## Architecture

Keep the source of truth at `app/training_templates/tags.py`.

It owns:

- `TemplateFocusTag`, a `StrEnum` used by Python producers and consumers.
- `TemplateTagCategory`, an explicit semantic category enum.
- immutable metadata containing each tag's category and contract.
- category membership sets derived from that metadata.
- one explicit `MuscleGroup -> TemplateFocusTag` priority mapping.
- tag membership and priority lookup helpers.
- deterministic tag-set validation.

The database continues storing JSON string values. Boundary code converts
validated enum values to strings for persistence and converts persisted strings
back to validated canonical values for engine use. No migration is required.

Seed data declares canonical enum values directly. There is no runtime alias
normalizer, dynamic tag construction, or per-template tag rewrite table.

## Canonical vocabulary

### Primary structure

- `full_body`: every session trains major upper and lower movement regions.
- `upper_lower`: the week contains explicit upper- and lower-body session blocks.
- `push_pull_legs`: the week contains explicit push, pull, and leg session blocks.
- `body_part_rotation`: the week rotates dedicated muscle or body-region sessions.

A template must have at least one primary structure tag. The audited PPL plus
upper/lower hybrids may have two; unrelated structural combinations are invalid.

### Regional balance and emphasis

- `balanced`: no region or muscle receives deliberate extra structural exposure.
- `upper_priority`: the weekly layout deliberately adds upper-body exposure.
- `lower_priority`: the weekly layout deliberately adds lower-body exposure.

`balanced` conflicts with all regional and muscle priority tags.
`upper_priority` and `lower_priority` conflict with each other.

### Muscle specialization and priority

- `chest_priority`: deliberate additional direct chest exposure.
- `back_priority`: deliberate additional direct back exposure.
- `shoulders_priority`: deliberate additional direct shoulder exposure.
- `arms_priority`: deliberate additional direct biceps/triceps exposure.
- `glute_priority`: deliberate additional direct glute exposure.
- `quad_priority`: deliberate additional direct quadriceps exposure.
- `hamstrings_priority`: deliberate additional direct hamstring exposure.

Each claim requires at least one dedicated direct-target day or repeated direct
weekly exposure supported by multiple direct slots. The exact evidence threshold
is deterministic and tested against every active Fitsho-managed template.

The explicit priority mapping is:

- chest -> `chest_priority`
- back -> `back_priority`
- shoulders -> `shoulders_priority`
- biceps, triceps, and forearms -> `arms_priority`
- glutes -> `glute_priority`
- quadriceps -> `quad_priority`
- hamstrings -> `hamstrings_priority`
- other muscle groups -> no template priority tag

### Structural character

- `compound_focus`: compound roles consistently lead meaningful session structure.
- `strength_bias`: primary compound exposure, ordering, frequency, and recovery
  make the weekly layout strength-friendly independent of user Goal.
- `specialization`: the week deliberately adds dedicated or repeated structural
  exposure and therefore requires a regional or muscle priority tag.

`time_efficient` is removed from stored focus tags. Compactness is derivable from
session slots, sets, rest, and duration policy, and no active template requires
this tag for ranking. Intensity methods remain separate.

## Legacy migration

Renamed or consolidated:

- `classic` -> `balanced` only where the weekly structure is actually balanced.
- `compound_first` -> `compound_focus` where compound ordering is structural.
- `strength_hypertrophy` -> `compound_focus` where justified.
- `legs_priority` -> `lower_priority` plus exact canonical muscle priorities
  supported by the template.
- `hamstrings_glutes` -> `hamstrings_priority` and/or `glute_priority` where
  direct structure supports each claim.
- `strength` -> `strength_bias` only for structurally strength-friendly templates.

Moved to `intensity_methods` only:

- `superset`
- `drop_set`

Removed without replacement:

- `foundation`
- `direct_targets`
- `frequency_two`
- `high_frequency`
- `long_session`
- `three_day`
- `volume`
- `weak_point`
- `hypertrophy`
- Goal tags `fat_loss`, `general_fitness`, and `build_muscle`
- sex tags `female`, `male`, `women_program`, and `men_program`
- stored `time_efficient`

Managed reseeding overwrites legacy persisted tags with each seed's canonical
declaration. It does not accept or normalize aliases as valid application input.
Custom/admin templates must already pass canonical validation.

## Runtime behavior preservation

Days and experience level remain hard Program Engine template filters. Goal
remains outside Program Engine hard eligibility.

Score constants and ordering remain unchanged:

- Program Engine base score: 100.
- Priority match increment: 35.
- Body Analysis boosts: unchanged ruleset values.
- Balanced no-priority bonus: 10, replacing the legacy `classic` dependency.
- AI Coach priority increment: 10.

The `long_session` penalty is removed because duration suitability is handled by
the existing duration policy and because the tag was redundant. Selection
characterization tests must show that this removal does not alter active-library
deterministic outcomes for covered baseline profiles.

Explicit priority mapping necessarily replaces broken dynamic/alias matching.
No score magnitude changes. Tests characterize canonical chest, back, shoulders,
arms, glute, quad, and hamstring matches plus unsupported muscles.

Body Analysis uses the same priority mapping. Alias-only matches disappear;
canonical matches retain the same boost values and confidence gates.

Template tags are immutable metadata. No user request path mutates them.

## Validation

Central validation rejects:

- unknown values and aliases;
- duplicate tags;
- missing primary structure;
- unsupported primary-structure combinations;
- `balanced` with any regional or muscle priority;
- simultaneous `upper_priority` and `lower_priority`;
- `specialization` without a regional or muscle priority;
- muscle-priority claims without structural evidence;
- `specialization` without structural evidence;
- Goal or sex identities;
- `superset`, `drop_set`, or any other intensity method in focus tags.

Admin writes and engine-reference conversion call the same validator. Managed
seed validation runs during seed construction and in the template test suite.
Duplicate normalization is not allowed at write/read boundaries; duplicates fail.

## Test strategy

TDD sequence:

1. Add failing vocabulary, category, mapping, combination, and structural-evidence
   tests.
2. Add failing active-library and admin-boundary tests.
3. Add failing selector, Body Analysis, and AI Coach characterization tests.
4. Implement the minimal central registry and consumer migration.
5. Replace seed raw strings and remove alias normalization.
6. Update frontend canonical types/defaults/labels and tests.
7. Run focused tag/template/selector tests, all Program Engine tests, broader
   workout tests, Ruff, mypy, frontend tests, lint, and build.

Regression coverage retains Days x Experience hard eligibility, Goal exclusion
from Program Engine hard eligibility, deterministic tie-breaking, priority and
Body Analysis score magnitudes, volume planning, prescription, duration repair,
safety, equipment, substitution, validation, and dynamic fallback.

## Out of scope

No Phase 6 score redesign, Goal/Sex weights, priority/body-analysis weight changes,
template redesign, template-family expansion, schema migration, safety change,
fallback removal, or volume/prescription rewrite.

## Product-owner ambiguities

None block Phase 5. The active library supports the canonical structural set.
Calves, core, traps, forearms-only, and other unlisted muscle specializations have
no dedicated canonical template tag; adding any is a future product decision.
