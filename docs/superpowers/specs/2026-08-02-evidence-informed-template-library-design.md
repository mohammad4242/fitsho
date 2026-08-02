# Evidence-Informed Template Library Design

## Scope

Rewrite the persisted Fitsho training-template library using public, general
hypertrophy-programming principles inspired by Stronger By Science, Jeff
Nippard, and RP Strength. This is a Fitsho synthesis, not a copy of any paid
program or an endorsement by those publishers.

## Decisions

- Persist five bilingual rationale entries with every template in JSON.
- Reorder every template session deterministically: priority target and main
  multi-joint work first, complementary work next, isolation work after that,
  and supersets/drop sets last.
- Keep current 5–9 exercise and specialised-movement floors intact.
- Display the rationale only in the admin template library, below each program.

## Rationale entries

Every template contains exactly five bilingual entries:

1. Exercise order.
2. Main movements.
3. Working-set and repetition ranges.
4. Program focus and weekly distribution.
5. Fatigue management and progression.

## Data flow

Seed definitions produce the ordered slots and structured rationale. The seed
service persists both. The admin API returns them and the React admin card
renders the selected language with a prominent divider.

## Safety and validation

The existing deterministic exercise eligibility, 5–9 exercise range,
specialised-movement floors, and catalog placeholders are unchanged. Tests
cover persistence, ordering, API output, and admin rendering.
