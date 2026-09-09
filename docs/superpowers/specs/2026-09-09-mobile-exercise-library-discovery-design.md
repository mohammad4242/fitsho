# Mobile Exercise Library Discovery Design

## Goal

Align Fitician mobile Exercise Library discovery with the web catalog by making
body region, target muscle, and muscle focus a visible guided sequence below
search, while keeping equipment, difficulty, and other secondary filters in a
sheet.

## Scope

- Modify the mobile catalog screen and its focused native/presentation tests.
- Add only reusable copy needed by the discovery prompt, stage descriptions,
  focus-all label, and advanced-filter action.
- Continue using `CatalogSelection`, the existing category schema, the existing
  `ExerciseFilters` fields, `createExerciseApi()`, and existing cards/details.
- Do not change backend code, API serialization, web catalog code, routing, or
  exercise media/card/detail behavior.

## Interaction model

The screen keeps one selection object and adds an explicit `showAll` mode.
Initial state is guided discovery: no catalogue query is enabled, no result
count/cards are rendered, and the user sees a prompt to choose a region.

The query becomes enabled only when `showAll`, trimmed search, a special
shortcut, or both body region and primary muscle are present. Choosing a body
region clears muscle/focus, special shortcuts, and `showAll`; choosing a muscle
clears focus. Special shortcuts clear guided selections and `showAll`. “همه
حرکات” resets filters and explicitly enables the full catalogue. “پاک کردن
فیلترها” returns to the initial guided state.

## Layout

```text
ScreenHeader
Search
Discovery panel
  quick shortcuts
  01 body region
  02 target muscle (after region)
  03 muscle focus + content type (after muscle)
  more filters
Active filters
Results or guided prompt
Advanced filter Sheet
```

The discovery panel is one raised surface using existing Fitician tokens. Quick
shortcuts use a dedicated compact chip with a 36px visual height and hit slop.
Region options are three responsive cards. Muscles and focuses use wrapped,
RTL-aware option layouts so a 360–400dp phone does not depend on a horizontal
carousel. The content switcher remains a compact two-option segmented control
inside stage 03.

## Secondary filters and active state

The Sheet contains equipment, difficulty, exercise type, clear, and apply
actions. Primary region/muscle/focus controls are not repeated there. The
“فیلترهای بیشتر” trigger shows `advancedFilterCount`, counting only equipment,
difficulty, and non-mobility exercise type. Search and guided/special mode are
not advanced filters. Existing removable active-filter chips remain below the
panel and preserve their removal behavior.

## Loading and states

Categories continue loading independently and are displayed in the discovery
panel. Exercise query options include `enabled: canLoadExercises`. Before that
condition is true, the result heading/count and cards are absent; the prompt
changes from region guidance to muscle guidance after a region is selected.
Search can enable results without any guided selection.

## Verification

Native tests cover visible regions, staged muscle/focus reveal, state clearing,
special shortcut filter payloads, explicit all-mode loading, direct search,
advanced sheet behavior, absence of the header filter action, and no primary
filter duplication in the sheet. Presentation contract tests assert the query
gate and stage placement. The mobile typecheck, native suite, Vitest suite, and
focused catalog tests are run before completion.
