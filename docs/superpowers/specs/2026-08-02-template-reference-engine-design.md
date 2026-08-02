# Template Reference Engine Design

## Goal

Make the curated Fitsho training-template library the deterministic starting
point for hypertrophy programs. The engine selects one compatible reference
template, applies the existing safety filter, and adapts only low-priority
slots when the user's available time, equipment, or limitations require it.

## Scope

- Grow the four-day and five-day library buckets from five to ten original
  Fitsho templates each.
- Cover beginner, intermediate, and advanced templates, with classic,
  chest, back, shoulder, quad, hamstring/glute, and arm-priority variants.
- Encode a template slot's adaptation priority and optional superset pairing.
- Route deterministic Fitsho-coach generation through the selected template.
- Preserve the current free-form deterministic planner as a safe fallback
  when no template can satisfy the profile or the eligible catalog.

## Reference policy

Templates are original Fitsho structures informed by published volume and
frequency evidence. They are not copied from a named coach or commercial
program. `source_name` remains Fitsho attribution and links to the evidence
summary used for the library.

Per-session slot bands apply to direct target work before time adaptation:

| Level | Large-muscle direct slots | Small-muscle direct slots | Working sets per slot |
| --- | --- | --- | --- |
| Beginner | 3-5 | 2-3 | 3 |
| Intermediate | 4-6 | 2-3 | 3-4 |
| Advanced specialization | 5-7 | 3-4 | 3-4 |

Advanced specialization templates require a sufficiently long session and
retain all core slots. Drop sets and supersets are restricted to eligible
low-risk accessory slots and never override safety filtering.

## Data model

`training_program_template_slots` gains:

- `adaptation_priority`: `core`, `accessory`, or `optional`; adaptation only
  removes optional then accessory slots.
- `superset_group`: nullable short identifier shared by exactly two compatible
  accessory slots on the same day.

The existing exercise reference, movement pattern, prescription, and
intensity-method fields remain the source of truth. The migration uses safe
defaults (`core`, null) for previously seeded rows.

## Deterministic data flow

1. The workout service loads active templates with their days and slots.
2. The program engine normalizes the user and applies safety/eligibility to
   the exercise catalog first.
3. The template selector scores candidates by days, level, goal, priority
   tags, duration fit, and whether every core slot has an eligible exercise or
   a safe movement-compatible replacement.
4. The template session builder resolves each slot to the referenced eligible
   exercise where possible, otherwise ranks an eligible replacement with the
   same movement and target muscle.
5. The adapter removes optional then accessory slots when its time estimate
   exceeds the user budget. Core work and priority-muscle work are retained;
   if they cannot fit, the template is rejected and the existing planner is
   used.
6. The existing prescription, cardio, volume repair, and full validator run
   on the resulting program. The decision trace records the selected template,
   substitutions, and removed slots.

## Guardrails

- Template choice never bypasses equipment, limitation, pain, caution, or
  catalog-review constraints.
- The template-specific volume band supplies validation ranges, while the
  normal planner's ranges remain unchanged for fallback generation.
- A beginner never receives an advanced template, drop set, or superset.
- Identical exercise IDs are not duplicated unless the existing progression
  rule allows it.

## Tests

- Ten templates exist for both four and five training days, across all three
  experience levels and requested focus tags.
- A compatible intermediate four-day request selects a template rather than
  the fallback planner.
- A hard-filtered reference exercise is replaced only by an eligible matching
  candidate; it cannot reach the final program.
- Short-session adaptation removes optional/accessory work first.
- Advanced templates preserve their configured direct-slot bands when the
  session budget permits and contain only valid paired supersets/drop sets.
- Existing deterministic planner tests remain green when no reference template
  is supplied.

## Out of scope

- Browser editing of templates.
- Copying named coaches' copyrighted programs.
- Changing public user-profile fields.
- Replacing the AI-generation path; it retains its current separate contract.
