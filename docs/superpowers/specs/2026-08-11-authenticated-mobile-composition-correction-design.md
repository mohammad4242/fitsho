# Authenticated Mobile Composition Correction

## Scope

Recompose the existing authenticated frontend into a compact mobile product while preserving routes, API contracts, permissions, product modes, deterministic engines, and truthful data states.

## Visual system

- Near-black canvas; petrol is limited to surfaces and aqua to active/primary information.
- Four distinct content patterns: one hero action, connected metric panels, compact rows, and low-priority status/details surfaces.
- Mobile type and spacing are compact; desktop uses controlled widths and selective split layouts.
- Shared line SVG icons replace CSS shapes and text-character icons.

## Shell

- Mobile uses a contextual top bar and bottom navigation as the primary navigation.
- Desktop keeps a product header and side navigation.
- Product-mode filtering and role-specific links remain unchanged.
- Secondary training and nutrition routes activate their related primary destination.

## Page composition

- Dashboard: greeting, real next workout, real nutrition target/tracking summary, real progress state, concise actions.
- Workout: weekly summary and schedule first; next session expanded, other days compact; technical metadata moves to lower details.
- Nutrition: calorie target/status and one macro strip first; tracking and photo estimation are prominent; scientific details remain secondary.
- Catalogue: search/filter first, dense food rows with complete expandable details and unchanged price visibility.
- Body analysis/progress: supported visual/result data first; history and details secondary; no invented chart or metric.
- More/profile: compact grouped rows and connected data summaries; role links and edit flows remain available.

## Responsive and accessibility

- Validate 360, 390, 430, 768, and desktop widths with no horizontal overflow.
- Use logical properties and document direction for native RTL/LTR behavior.
- Maintain visible focus, semantic headings, touch targets, reduced motion, and honest loading/empty/error states.

## Verification

Run focused tests after each step, then full frontend lint, test, and build. Inspect every requested route in a real browser at the required widths in Persian and English.
