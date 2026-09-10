# Fitician Mobile Public Onboarding Web Parity

Date: 2026-09-10

## Goal

Bring the Fitician Android public entry and public onboarding experience into literal
parity with the current web experience. The web remains the presentation source of truth.
Native differences are limited to safe-area handling, touch interaction, Android Back,
keyboard behavior, accessibility, and media lifecycle constraints.

## Scope

- `/(public)` public entry / landing screen.
- `/public-onboarding` mode selection, guided questions, nutrition questions, and account handoff.
- Web presentation references:
  - `frontend/src/features/landing/PublicLandingPage.tsx`
  - `frontend/src/features/landing/CinematicStory.tsx`
  - `frontend/src/features/landing/ProcessStory.tsx`
  - `frontend/src/features/landing/BodyIntelligence.tsx`
  - `frontend/src/features/landing/publicLanding.css`
  - `frontend/src/features/landing/landingStory.css`
  - `frontend/src/features/publicOnboarding/PublicOnboardingPage.tsx`
  - `frontend/src/features/publicOnboarding/publicOnboarding.css`
- Existing authentication, draft persistence, onboarding state transitions, API contracts,
  and authenticated onboarding remain unchanged.

## Current Gaps

The web landing uses a sticky, scroll-driven cinematic story with the real `landfilm.mp4`,
animated plan documents and verification seals, meal-photo scanning and result reveal,
process-ring fill, and interactive body-analysis highlights. The current native entry is a
static scroll view with a poster image, compact cards, and static process/body states. Its
food and body media also differ from the web assets.

The native public onboarding already owns the required draft and state contracts, but its
presentation must be checked against the current web question order, full-screen question
hierarchy, progress treatment, responsive spacing, and account handoff surface.

## Architecture

Keep the Expo Router route wrappers and extract the public landing presentation into
focused native components:

- `PublicLandingScreen` owns the screen shell, header actions, scroll container, and route actions.
- `PublicCinematicStory` mirrors the web hero, supervision moments, meal analysis, and background film.
- `PublicProcessStory` mirrors the four ordered stages and scroll-filled rings/connectors.
- `PublicBodyIntelligence` mirrors the scan frame, body visual, hotspots, connectors, and live callout.
- `PublicLandingScrollProgress` converts native scroll position into normalized section progress values.

Use one native animated scroll source for all three story sections. Use `expo-video` for the
local background film with the web poster as fallback. Use the existing SVG, media, button,
RTL, typography, and token primitives; do not introduce a second global theme or alter
backend/domain behavior.

The public onboarding route keeps `PublicOnboardingScreen`, its controller/state machine,
SecureStore draft, native Back registration, and existing dedicated question components.
Only presentation gaps are corrected, with the web component and CSS as the comparison
reference.

## Visual and Interaction Contract

- Preserve web copy, section order, direction, hierarchy, spacing rhythm, dark palette,
  aqua accents, overlays, rounded document surfaces, scan lines, rings, and CTA destinations.
- Background video starts muted, loops, fills the cinematic stage, and falls back to its
  local poster on reduced motion or playback failure.
- Scroll progress drives hero exit, scene opacity/translation, seal/ring/check fill,
  meal scan/result reveal, process step fill, and body-analysis reveal.
- Body hotspots remain touchable and update the accessible live callout.
- Public onboarding retains question-by-question progression, dynamic training questions,
  validation, resume, auth handoff, Android Back, keyboard-safe inputs, and accessibility.
- Content remains available when reduced motion is enabled; animation is replaced with
  visible final/static states.

## Data Flow and Failure Handling

Landing data is local copy and local assets. The CTA routes to `/public-onboarding`; sign-in
routes to the existing auth path. No landing or onboarding API is added.

Video errors switch the film to its poster without blocking the page. Missing or invalid
draft data continues through the existing native reset/error path. Auth, validation, and
network errors continue through their existing user-facing notices and handlers.

## Verification

Implementation starts with failing native tests for scroll progress, film configuration,
section hierarchy, interactive hotspots, and public onboarding navigation/presentation.
Focused Jest/RNTL tests, mobile TypeScript, and `git diff --check` run after each logical
implementation step. An Android build/device comparison at 360, 390, and 430 dp is reported
separately from automated evidence; source and tests do not claim physical-device parity.
