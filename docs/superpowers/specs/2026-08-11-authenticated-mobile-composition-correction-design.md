# Panel-Driven Authenticated Mobile Composition

## Source of truth

`Panel.png` is the primary visual reference for density, proportions, hierarchy, and navigation. It is never rendered or bundled by the application. Existing Fitsho routes, APIs, product modes, permissions, deterministic engines, privacy controls, and localized data remain the behavioral source of truth.

## Visual foundation

- Canvas: near-black `#020607`; surfaces progress through subtle petrol-black layers rather than green page fills.
- Accent: Aqua marks primary actions, selected navigation, real progress, and the most important metric. Green, amber, and coral retain semantic meanings only.
- Typography: Vazirmatn carries Persian product copy; Sora is restricted to Latin/data metrics; headings stay at app scale.
- Density: 12 px mobile page gutters, 8-14 px internal spacing, compact rows, thin borders, and one dominant card per viewport.
- Signature: a real-data “instrument panel” combines one dominant metric or action with connected supporting values. It is specific to fitness use and replaces repeated generic cards.

## Shared composition

- Mobile uses a 56-60 px contextual top bar and a safe-area-aware five-destination bottom bar.
- Product-mode filtering controls whether Workout and Nutrition appear. Exercises map to Workout; catalogue and tracking map to Nutrition; profile maps to More.
- Desktop keeps the same hierarchy in bounded columns and a side navigation without stretching phone cards across the viewport.
- Shared primitives cover progress rings, connected metric strips, status badges, compact rows, and media-led hero cards.

## Screen mapping

### Dashboard

Use a compact greeting, then one real workout hero containing the next day, its first available exercise image, duration, and CTA. Follow with a connected nutrition instrument using actual intake, plan or estimate target, a circular ring when a valid denominator exists, and one macro strip. Finish with a compact real weight/body-analysis summary. Missing data produces a concise CTA or state, never a fabricated metric.

### Nutrition and meal photo

Load the current estimate, latest weekly plan, and current daily tracking together. The first panel combines calories, target context, ring, macros, physician status, and the first real meal rows. Detailed safety, fibre, sodium, sugar, fat, micronutrients, and provenance remain in an expandable scientific section.

Food-photo tracking presents a focused media stage. The browser previews only the user-selected local file, shows an explicit analysis state, then renders the API's detected items and confidence with correction/removal controls. Consent, third-party disclosure, estimate wording, and confirmation-before-logging remain unchanged.

### Workout

Show cycle metrics first, then the next workout as the only media hero and all days as compact schedule rows. The focused day expands on demand into dense exercise rows; it is not expanded by default. Exercise media, sets, repetitions, rest, RIR, notes, and alternatives remain real. Coach review, stale state, generation source, history, body provenance, and guidance move below the schedule in compact banners/details.

### Catalogue, body analysis, and progress

Catalogue keeps search and category controls above dense rows with bilingual names and five real macro values. Detail disclosure retains portions, micronutrients, and provenance. Member price data remains structurally absent.

Body analysis leads with the real body-region map, semantic markers, confidence, and a compact finding list. Full finding explanations and specialist review appear below. Progress uses one weight line chart only when two or more real points exist; otherwise it leads with real body-photo session history and an honest action.

### More and profile

More uses one compact account row, grouped route rows, authorization-aware role entries, language, and a separated logout row. Profile opens as a compact read view of real name, email, height, weight, age, activity, and goal, with editing kept behind an explicit action; the existing multi-step editor and onboarding semantics remain intact.

## Accessibility and responsive behavior

- Use semantic links, buttons, details, lists, labels, and progress text.
- Progress rings expose current/max values and never rely on color alone.
- Logical properties handle RTL/LTR arrows, metric order, spacing, and alignment.
- Focus-visible contrast and reduced-motion behavior are mandatory.
- Verify 360, 390, 430, 768, and desktop widths with no horizontal overflow or bottom-bar occlusion.

## Verification

Each page change starts with a failing behavior/structure test, then focused tests and visual comparison against its mapped Panel screen. Completion requires the full frontend lint, test, production build, Persian and English browser QA, and direct inspection of every authenticated route.
