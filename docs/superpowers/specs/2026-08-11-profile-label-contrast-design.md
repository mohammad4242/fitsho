# Profile Label Contrast Design

## Scope

Improve text contrast inside the existing Profile form without changing layout, spacing, typography, form behavior, or the dark Fitsho theme.

## Visual hierarchy

- Question and field labels use `--fitsho-ink` (`#e8f4f1`).
- Helper text uses `--fitsho-muted` (`#8ca39e`).
- Fieldset legends and section highlights remain `--fitsho-aqua` (`#50dfce`).
- The selectors stay scoped to `.profile-form` so other screens and shared navigation are unchanged.

## Verification

Add a stylesheet regression test for the three semantic color roles, then run frontend tests, lint, and the production build.
