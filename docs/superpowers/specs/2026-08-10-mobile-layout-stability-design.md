# Mobile Layout Stability Design

## Goal

Fix the structural mobile layout failures shown on authenticated Fitsho pages without redesigning the visual system or changing backend/API behavior.

## Scope

- Prevent horizontal document overflow across authenticated member pages.
- Keep fixed full-page media inside the mobile visual viewport.
- Collapse the authenticated header to the brand and account-menu button on small screens.
- Keep the bottom navigation to one row with four primary destinations plus a More control.
- Keep cards, headings, controls, and media within the available mobile width.
- Preserve desktop layout and existing route/capability rules.

## Navigation

For members with training and nutrition enabled, the mobile navigation shows:

1. Today
2. Workout plan
3. Exercises
4. Nutrition
5. More

More exposes Food catalogue and Profile. Capability filtering remains authoritative: unavailable product areas are not shown. Members with fewer available destinations may receive direct links without an unnecessary More control.

The desktop authenticated navigation remains unchanged. At the mobile breakpoint, the desktop pill navigation is hidden globally and the account menu remains available.

## Layout Rules

- Global shells and their direct content use `min-width: 0` and stay within `100%`.
- The document does not scroll horizontally.
- Fixed background media covers the visual viewport using dynamic viewport units with a safe fallback.
- Mobile cards use fluid widths and mobile-safe padding; no card may impose a minimum width wider than the viewport.
- Main content reserves enough bottom space for one navigation row plus the device safe area.
- The fixed navigation remains above content but does not obscure the final interactive controls.

## Components

- `AppShell` owns primary-versus-overflow navigation grouping and the More interaction.
- Shared CSS owns the mobile header, bottom navigation, safe-area spacing, and overflow guard.
- Page CSS only receives targeted width fixes where an existing component creates overflow.
- `MemberHeaderMedia` keeps its current playback and fallback behavior; only its layout boundary changes.

## Interaction

The More control is a button, exposes its expanded state to assistive technology, and opens a compact list of overflow destinations above the bottom navigation. Route selection and outside navigation close the list. Existing links and route guards remain unchanged.

## Verification

- Add focused component tests for capability-aware primary navigation and More links.
- Keep existing navigation and media tests passing.
- Run frontend lint, focused tests, the full frontend test suite, and production build.
- Verify authenticated Today and Workout Plan pages at representative mobile widths, including 360 px and 412 px, with no horizontal overflow and no two-row bottom navigation.

## Out of Scope

- Visual redesign, new colors, typography changes, or animation changes.
- Backend, API, authentication, workout generation, or nutrition behavior changes.
- Native mobile application work.
