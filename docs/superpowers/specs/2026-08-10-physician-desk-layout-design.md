# Physician Desk Layout Design

## Goal

Make the physician nutrition workspace as clear and polished as the coach workspace while
preserving its physician-only clinical tools: laboratory documents, lab requests, supplement
orders, and private clinical notes.

## Layout

The page uses the same desktop workspace pattern as the coach review page.

- A compact hero identifies the page as the physician desk, presents the three review queue
  counts, and retains the back action.
- In Persian, the review list is the right-hand sidebar; in English it follows normal LTR order.
- The sidebar contains the pending, claimed, and approved queue filters plus compact case cards.
  A selected case is visually distinct and shows member name, status, priority, and overdue state.
- The primary pane presents the selected nutrition-plan revision. When no case is selected, it
  gives a direct empty-state instruction.

## Clinical Workspace

The selected case pane is divided into explicit tabs:

1. Plan review: nutrition validation, foods, quantity/replacement controls, and plan decision.
2. Laboratory review: submitted lab files, clinical review state, and lab-request controls.
3. Supplements: current orders plus prescribe/edit/transition controls.
4. Notes: member-visible note and private physician note.

The approved queue opens the same revision in read-only mode. No food, lab, supplement, note, or
plan-decision mutation is available there.

## Data and Access

This is a frontend-only composition change. It continues using the existing physician review API
and role guard. No clinical data is added to queue responses beyond the safe member display name;
private notes remain available only from the selected physician case and never reach member views.

## Responsive and Accessibility Behaviour

On narrower screens, the queue sidebar moves above the case pane. Queue filters remain keyboard
operable tabs, selection uses buttons with clear state, and read-only controls are not actionable.
The existing bilingual labels remain aligned with the active language direction.

## Validation

Tests will cover queue/sidebar selection, rendering the four physician workspace tabs, correct
read-only behaviour for approved cases, and retention of plan/lab/supplement actions for active
reviews. Frontend lint, build, focused tests, and the full frontend suite will run before delivery.
