# Fitician Mobile Visual Parity Design

## Goal

Bring the Expo/React Native application to clear brand and UX parity with the Fitician web
frontend while keeping native phone interaction, performance, offline behavior, API contracts,
authentication, product capabilities, and shared `@fitician/core` rules unchanged.

The result should feel cinematic and media-led without copying desktop composition or surrounding
every surface with neon effects.

## Audit Findings

- The current mobile palette, fonts, tab icons, real API data, and media URL handling match the web
  foundation.
- Home is vertically long. Its workout media is separated from the workout decision, and its calorie
  ring is a static border rather than a value-driven visualization.
- Workout exercise rows combine fixed-width media, content, and a full button in one row, causing
  crowding on narrow phones. Day expansion still uses text glyphs instead of the shared icon set.
- Public entry has no visual media, while the web landing experience is defined by cinematic fitness
  imagery.
- The exercise catalogue places several filter panels before results, so users scroll through form
  controls before seeing exercise media.
- Native onboarding preserves the correct controller and validation, but several stages still feel
  like grouped forms instead of a guided question flow.
- Nutrition and Body Analysis received summary surfaces, but their deeper member screens do not yet
  consistently use the same hierarchy and media treatment.
- Some newer Home styles duplicate literal colors and font names instead of using mobile tokens.
- Loading bars use arbitrary partial values and skeletons have no restrained loading treatment.
- Physical-device visual verification is still required before release acceptance.

## Visual Direction

The subject is a Persian-first personal fitness companion. The primary job of every member screen is
to make the next safe action obvious while showing real body, workout, and nutrition evidence.

- Canvas: `#020607`
- Deep petrol: `#091817`
- Raised surface: `#101e1c`
- Ink: `#e8f4f1`
- Muted: `#94aba5`
- Aqua signal: `#50dfce`
- Status colors remain the current amber, success, and coral values.
- Vazirmatn owns Persian interface copy, Lalezar owns short Persian display headings, and Sora owns
  the FITICIAN wordmark and numeric metrics.
- The signature element is the web dashboard's restrained aqua scan line. It appears only on media
  actions, progress, and the active destination.

## Shared Native Architecture

Existing screens continue to own queries, mutations, cache state, and navigation. Presentation is
extracted into focused reusable primitives:

- `CinematicSurface`: layered dark surface, quiet highlight, optional ambient aqua edge, and media
  scrim.
- `ScreenHeader`: consistent FITICIAN wordmark, Persian title, optional action, and compact metrics.
- `MetricRing`: accessible value-driven circular progress built with `react-native-svg`.
- `MediaHero`: image/video frame with loading state, poster/fallback, overlay copy, and one primary
  action.
- `MetricStrip`: responsive numeric facts with logical RTL dividers.
- `IconAction`: compact icon-led secondary action.
- `StateSkeleton`: shape-based loading placeholders without fake percentages.

`react-native-svg` is the only planned new direct UI dependency. It is installed through Expo's
version resolver. Gradient atmosphere uses layered native views, so no broad animation or blur stack
is introduced.

## Home

The welcome area stays compact: FITICIAN, profile access, greeting, and today's date occupy one
short header block.

The workout card becomes the main visual thesis. On normal phones it uses a two-zone composition:
the first exercise media and scrim occupy one side while title, day, duration, state, and start action
occupy the other. Very small phones fall back to a stacked layout. Missing media uses a purposeful
training illustration state instead of a blank block.

The nutrition card uses a real progress ring driven by consumed and target calories. Protein,
carbohydrate, and fat stay visible as a compact strip. Pending, empty, partial-error, and offline
states remain explicit.

Quick actions remain image-led. They gain the restrained scan line and corner markers found in the
web dashboard. Two cards share a row on standard phones and stack only when width is insufficient.

## Workout Plans

The top title and plan overview become one compact hero containing status, cycle duration, training
days, and average session duration. Warnings remain immediately visible but use a compact status
rail rather than repeated large rectangles.

The first actionable day is visually dominant and receives a useful media preview. Other collapsed
days remain compact. Expanded exercises become full-width pressable rows; the redundant separate
guide button is removed while the same detail route remains available from the whole row and media.
This leaves enough width for Persian names and prescriptions on 360 px phones.

All expand/collapse, play, history, PDF, and status controls use the shared icon system. Existing
generation, coach approval, cycle, stale/offline, history, replacement, and PDF behavior remains
unchanged.

## Exercise Catalogue and Detail

Catalogue results move closer to the top. Search and primary category chips stay inline; advanced
equipment, difficulty, type, and focus controls move into the existing native Sheet pattern. Active
filters remain visible and removable.

Exercise cards use a consistent media aspect ratio and reveal name, muscle/category, equipment, and
difficulty without turning each card into a form. Media remains lazy and only visible videos animate.

Detail keeps large top media, presentation selection, and optional offline video storage. Metadata,
instructions, cues, and safety are grouped into quiet sections below the media.

## Public Entry and Onboarding

Public entry uses one bundled, optimized landing poster derived from the existing web landing assets.
Text and CTAs overlay a dark scrim, giving new users the same first impression as the website without
bundling promotional video.

Onboarding keeps `onboardingController`, shared validation, secure draft storage, route guards, and
all current fields. UI-local question state presents one logical question or tightly related group at
a time. Progress represents real completed questions. Back navigation returns to the previous
question and drafts survive restart.

Product mode cards remain the opening decision. The combined mode receives the same subtle
recommended treatment as the web flow.

## Nutrition

The nutrition landing hierarchy becomes: calorie status, macro strip, today's actions, current plan,
then clinical and catalogue tools. Dense forms remain available inside their existing sections but
do not dominate the first viewport.

Meal cards use existing food imagery when returned by the API. Physician approval, scientific
details, confidence, safety, budget, tracking, history, and plan state remain visible and unchanged.

## Body Analysis

The entry screen makes the body visualization the dominant surface and places capture/history as
clear actions. Camera instructions use concise numbered steps and the existing Ghost as a pose and
privacy guide only.

Processing uses stage-specific skeleton/status surfaces. Results prioritize the body map, then body
composition, balance/symmetry, strengths, weaknesses, and history. Existing crop geometry, pose
validation, upload rules, thresholds, and analysis data remain unchanged.

## Auth and Profile

Auth receives the same cinematic background treatment as public entry while retaining current
email, phone, Google, password recovery, and error behavior. Profile keeps existing editable
sections but uses the shared header, summary metrics, and grouped card rhythm.

## Motion, RTL, and Accessibility

- Press feedback remains a short scale/opacity change.
- Progress updates animate only when reduced motion is not requested.
- No ambient looping animation is added outside actual exercise media.
- Persian copy uses RTL alignment and logical layout; FITICIAN and numeric-only Sora content remain
  LTR where needed.
- Touch targets remain at least 48 dp. Font scaling, accessible labels, progress values, and status
  announcements remain supported.
- Tab labels, cards, and forms must fit 360, 390, and 430 px widths without horizontal scrolling.

## Performance and Media

- Bundle only the optimized public landing poster and current small static assets.
- Exercise GIF/video remains remote through existing API base URL resolution.
- Only the Home lead exercise may autoplay; catalogue thumbnails do not autoplay videos.
- Loading, image errors, and missing media always produce stable-height fallbacks.
- No WebView, blur framework, large animation package, or promotional video bundle is introduced.

## Implementation Boundaries

- No backend, schema, API contract, persisted model, authentication security, workout engine,
  nutrition engine, Body Analysis algorithm, or specialist approval change.
- No mock data when API or cache data exists.
- No removal of offline cache, stale state, history, PDF, replacement, or capability-based routing.
- Existing unrelated worktree changes remain untouched.

## Verification

Each implementation phase adds focused presentation and behavior tests before production code. Run
the relevant focused tests, mobile typecheck, and source lint before each phase commit.

Final automated verification includes the complete mobile Vitest suite, native Jest suite,
typecheck, source lint, foundation validation, `git diff --check`, and dependency audit.

Runtime acceptance requires inspection on a modern Android phone and one smaller Android viewport:
public entry, sign-in, onboarding, Home for all three product modes, workout plan, exercise catalogue,
exercise detail, nutrition, Body Analysis, and profile. Release completion is not claimed without
that physical-device evidence.
