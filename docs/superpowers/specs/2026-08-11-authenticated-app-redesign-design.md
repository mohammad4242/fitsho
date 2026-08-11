# Authenticated App Redesign Design

## Scope

Redesign the authenticated Fitsho frontend on the existing `nutrition` branch. Preserve all
routes, API contracts, authentication, product modes, role checks, data semantics, and existing
flows. No backend, database, or product-logic changes are included.

## Architecture

`AppShell` remains the shared wrapper for completed-profile member routes and becomes the single
owner of authenticated navigation. Existing pages continue to own their data loading and actions.
Shared visual behavior is implemented through the existing token and primitive stylesheets, while
page-specific styles remain beside each feature.

The shell exposes capability-aware destinations for training, nutrition, progress, and account
areas. A dedicated `/more` route provides profile, secondary product tools, role-specific
workspaces, language selection, and logout without removing any existing destination.

## Visual System

- Canvas: `#020b0c`; deep petrol surfaces: `#071716` and `#0b201f`.
- Raised surfaces: `#102b28`; primary accent: `#50dfce`; warm status accent: `#f2b85b`.
- Persian interface typography uses Vazirmatn. English and numeric metrics use Sora.
- Page titles remain product-sized. Lalezar stays limited to existing brand/marketing usage.
- Cards use consistent 16–24 px internal spacing, 18–24 px radii, quiet borders, and limited glow.
- The signature element is an aqua signal line used on primary actions, active navigation, and
  progress surfaces. It communicates status rather than acting as decoration.

## Navigation and Shell

Mobile navigation uses Home, Workout, Nutrition, Progress, and More. Unsupported capabilities are
omitted without substituting fake destinations. More remains available for every product mode.
Desktop uses a compact persistent rail with the same information architecture and a constrained
content canvas. The current authenticated header becomes a concise utility header for brand,
language, account access, and role-aware links.

The bottom navigation respects safe areas, keeps touch targets at least 44 px, and never overlays
interactive page content. Menus close after navigation, on Escape, and when the route changes.

## Pages

### Home

Keep current workout-plan and weekly-nutrition requests. Present one capability-aware primary focus,
then nutrition and progress summaries, followed by secondary actions. Do not calculate unprovided
calorie, macro, or recovery values.

### Workout

Keep generation method, plan versions, coach review, body-analysis provenance, generation controls,
and exercise media. Tighten the weekly summary, highlight the first actionable day, and render other
days with lower emphasis. Do not introduce workout tracking.

### Nutrition

Keep estimates, targets, scientific notes, weekly plans, tracking, labs, supplements, and physician
review states. Make calories and macros dominant when returned by the API. Keep all uncertainty and
medical-review language visible.

### Food Catalogue

Keep member/admin serialization boundaries, search, category filters, pagination, portions,
nutrients, sources, and admin price controls. Increase scan speed through compact rows/cards and a
stable search/filter toolbar. Member views never expose price.

### Body Analysis and Progress

Keep session upload, validation, provider state, confidence, findings, specialist reviews,
comparisons, and disclaimers. Use the body map as the distinctive visual focus. Do not infer health,
recovery, or diagnostic claims. Progress shows only stored sessions and supported comparisons.

### More and Profile

More groups account, product tools, professional/admin workspaces, language, and logout. Profile
keeps the existing editable fields and save behavior, with clearer personal/training/nutrition
grouping. Existing role visibility remains unchanged.

## Localization and Accessibility

Every new label has Persian and English translations. Direction continues to come from the global
i18n document settings. Logical CSS properties are used for directional layout. Focus indicators,
semantic headings, labels, status regions, reduced motion, keyboard navigation, and color contrast
remain first-class requirements.

## Responsive Behavior

- 360, 390, and 430 px: single-column composition, full-width actionable cards, fixed bottom nav,
  no horizontal scrolling, and contained charts/body callouts.
- Tablet: selective two-column sections where card content remains readable.
- Desktop: persistent navigation rail, constrained page widths, and two-column summaries where they
  improve scanning. The interface must not resemble a scaled phone canvas.

## Verification

Run focused component tests during each behavior change. Before completion, run the full frontend
test suite, lint, and production build. Inspect authenticated routes in Persian and English at 360,
390, 430, tablet, and desktop widths. Verify navigation visibility for training, nutrition, both,
admin, coach, and physician contexts, and confirm no horizontal overflow.
