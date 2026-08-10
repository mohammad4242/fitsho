# Fitsho Product Identity Redesign

## Scope

Redesign the public landing experience and harmonize the member-facing application around one dark, restrained Fitsho identity. Preserve all routes, API contracts, permissions, validation, onboarding drafts, workout generation, nutrition science, body-analysis safety language, and existing product behavior.

Backend behavior and database schemas are out of scope. Admin and specialist workspaces keep their current task-focused layouts, while inheriting shared tokens where safe.

## Approved direction

The landing hierarchy is deliberately weighted rather than mixing three ideas equally:

1. The real input-to-plan product story is the landing backbone.
2. A premium 3D human body is the recognizable Fitsho identity.
3. The body becomes an interface only in one or two signature moments.

The signature asset is a Fitsho-exclusive stylized-realism 3D athletic body render, not stock photography and not a medical scanner. It uses realistic proportions, controlled Aqua rim light, neutral dark training clothing, and no visible face emphasis. The composition leaves usable negative space for Persian RTL and English LTR layouts.

The body visualizes how Fitsho understands the user; it is not itself the product. The decision engine remains the product story. At most three restrained callouts appear near the body, while a separate plan-building panel makes the transformation into training and nutrition explicit. Landing examples are clearly separate from authenticated user results.

### Design signature

The memorable interaction is a localized Aqua body-area highlight connected to a real Fitsho priority and a visible plan adjustment. It appears in the hero and Body Intelligence section only. It must never imply medical diagnosis, future-physique prediction, or continuous body scanning.

### Layout thesis

Desktop hero uses three coordinated zones: product message, central 3D body, and plan-building state. Persian mirrors the reading order without changing the underlying meaning. Mobile stacks message, body, then plan state, keeping the CTA in the first viewport.

The visual sequence is:

`User context -> Understand -> Plan -> Train -> Adapt`

The interface transformation below the hero uses only real Fitsho concepts: goal, experience, available days, session duration, considerations, training structure, exercise selection, nutrition targets, and revision.

## Shared visual system

Evolve the existing tokens instead of creating a parallel system.

- Canvas: `#020B0C`
- Deep Petrol: `#0A211F`
- Surface: `#0B201F`
- Raised surface: `#163431`
- Primary text: `#E8F4F1`
- Muted text: `#8CA39E`
- Aqua accent: `#50DFCE`
- Coral priority/error: `#F67859`
- Amber warning: `#F2B85B`
- Green success: `#66C89F`

Retain Lalezar for restrained Persian display use, Vazirmatn for Persian UI and body text, and Sora for English UI and numeric data. Define shared spacing, radius, shadow, border, focus, duration, and easing tokens. Shared button, input, badge, card, section-heading, status, page-container, and navigation styles become the base for feature styles.

Use large negative space, opaque or lightly translucent surfaces, low-contrast borders, and Aqua only for primary actions, selected states, and important progress. Avoid ambient neon, stacked gradients, decorative charts, and repeated oversized cards.

## Landing information architecture

1. Header with Fitsho mark, language control, sign-in, and a compact mobile menu.
2. Full-height three-zone hero with the approved bilingual headline, concise product explanation, CTA to `/get-started`, central 3D body, two or three restrained callouts, and a plan-building panel.
3. Ordered product progression: Understand, Plan, Train, Adapt.
4. A visible transformation from real Fitsho inputs into training structure, exercise selection, nutrition targets, and revision without claiming live AI work.
5. Body-intelligence section using the same 3D identity with one localized body-area highlight and honest priority, uncertainty, and confidence language.
6. Responsive real-product previews based on Dashboard, Workout Plan, Nutrition, Body Analysis/Progress, and Food Catalogue.
7. Final adaptive-plan statement and repeated CTA.

The current fixed background film, app-store placeholders, social card, and cinematic scrolling panels are removed because they do not explain the real product.

## Public onboarding and authentication

Keep the existing mode selection, guided questions, validation, session draft, account hydration, login, and registration behavior. Re-skin them with the shared dark system so the landing-to-onboarding transition is continuous. Keep one question per screen where already implemented and preserve native form semantics and focus-on-error behavior.

## Member shell and navigation

Keep the existing route and capability model. Desktop navigation becomes compact and stable, with one active-state treatment. Mobile keeps four primary destinations plus More when required. The More menu becomes a compact anchored sheet with correct safe-area handling, focus behavior, and RTL/LTR alignment.

Remove full-page cinematic background videos from Dashboard and Workout. Member pages use the shared dark canvas and structured content surfaces. Existing media stays in exercise content and other places where it communicates real information.

## Dashboard

Replace the cinematic story with a command-center hierarchy:

1. greeting and current context;
2. today's workout or generation action;
3. primary nutrition status when enabled;
4. progress/body-analysis entry;
5. compact secondary shortcuts.

Only supported data is shown. Missing information uses clear empty states and existing actions.

## Workout Plan

Preserve generation method, cooldown, active and historical versions, coach review, provisional analysis warnings, stale status, AI explanations, exercise media, sets, reps, rest, RIR, notes, alternatives, and future tools.

Lead with current-plan context and a compact week/session summary. Training days use dense expandable sections rather than oversized cards. Today's session is visually first when determinable; otherwise the first scheduled day is emphasized without inventing calendar state.

## Nutrition and Food Catalogue

Nutrition leads with calories, protein, carbohydrate, and fat. Fibre, sugar, saturated fat, trans fat, sodium, micronutrients, confidence, provenance, policy, formula, and revision remain available in secondary sections and native disclosure controls.

Weekly planning, tracking, labs, supplements, safety outcomes, physician approval, price-coverage warnings, and scientific disclaimers remain unchanged.

Food Catalogue stays dense and reference-oriented. Search and category controls remain sticky where practical. Cards prioritize bilingual food identity, serving basis, and primary macros. Micronutrients and source details remain in the dialog. Admin-only price and creation controls remain permission-gated.

## Body Analysis and Progress

This area uses the body-as-interface concept most strongly. Display real session photos and real returned findings only. A responsive abstract body map links visible areas to strengths, mild lag, clear priority, uncertainty, and confidence. It does not generate findings or medical claims.

The map is an alternate index into the existing findings; the full accessible text groups remain the source of truth. Progress uses the same area vocabulary and status colors, preserving insufficient-data and uncertainty states.

## Internationalization and accessibility

New interface copy is added to both `fa.ts` and `en.ts`. Layout uses logical CSS properties and document direction from the existing i18n setup. Directional icons flip through CSS or language-aware markup. Bilingual catalogue names retain explicit direction where needed.

Maintain semantic landmarks, headings, labels, focus-visible states, keyboard navigation, status announcements, adequate contrast, and readable mobile type. Decorative imagery is hidden from assistive technology; informative imagery receives localized alternatives.

All animation is optional. Reduced-motion mode removes parallax, reveal movement, and animated plan-building transitions while leaving content visible and ordered.

## Performance

Add no runtime 3D or animation dependency. The body is a pre-rendered high-quality 3D asset; CSS supplies only restrained depth and localized highlight motion. Use CSS transitions and small React state only. Export responsive WebP sizes with a JPEG fallback and explicit dimensions. Route-level lazy loading is allowed if it does not alter routing behavior and is verified separately.

## Testing

Update behavior-focused tests only where intended copy or structure changes. Add coverage for:

- Persian RTL and English LTR landing content;
- CTA routing into public onboarding;
- reduced-motion content visibility;
- public onboarding and auth continuity;
- capability-aware desktop and mobile navigation;
- Dashboard workout, nutrition, and progress hierarchy;
- Workout status, history, generation, and exercise details;
- Nutrition primary versus secondary information;
- Food Catalogue search, filters, permissions, and dialog details;
- Body Analysis real findings, confidence, uncertainty, and progress;
- key mobile containment rules.

Run the full frontend Vitest suite, Oxlint, TypeScript/Vite production build, `git diff --check`, and targeted browser checks at mobile and desktop widths in both languages.

## Delivery boundaries

Do not modify backend behavior, database schema, or APIs. Do not fabricate analysis, recovery, nutrition, plan, or progress data. Do not expose admin-only price data. Do not commit local environment files, generated brainstorm artifacts, user screenshots, videos, media storage, or unrelated working-tree changes.
