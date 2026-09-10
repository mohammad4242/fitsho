# Native Landing Scroll Motion Design

## Goal

Make the Fitician Android public landing page scroll smoothly and reveal its
cinematic content in a deliberate sequence. Match the Web story structure while
moving all continuous scroll animation work off the React render path.

## Scope

- Change only the native public landing motion implementation and focused tests.
- Restore the unrelated public-question height behavior changed by commit
  `14b8a2a4`.
- Preserve landing copy, media, navigation, accessibility, RTL, reduced-motion,
  API, authentication, and onboarding-draft behavior.
- Preserve unrelated worktree changes.

## Current problem

`PublicLandingScreen` stores every native scroll event in React state. At a
16 ms throttle this rerenders the full video, SVG, image, and story tree during
the gesture. The Web implementation coalesces scroll work with
`requestAnimationFrame` and updates element-local CSS variables instead of
rerendering the page.

## Motion architecture

Use one Reanimated shared scroll value and a UI-thread scroll handler. Each
chapter derives its own styles with clamped interpolation:

1. Hero exits before the training supervision card enters.
2. Training exits before nutrition enters.
3. Nutrition exits before meal analysis enters.
4. Process steps reveal in strict order: ring, copy, connector, next step.
5. Body scan exits before the body result enters.

The scroll remains continuous and controlled by the user. There is no forced
page snapping. Short easing windows and small translation distances create the
rhythm; opacity never relies on React state.

Android overscroll is disabled only on this landing ScrollView. Reduced-motion
renders final readable states without continuous animation.

## Visual direction

The existing Fitician palette, Persian typography, video, and dark clinical
cinema remain unchanged. The signature is a calm supervised reveal: exactly one
primary scene has visual emphasis at a time, followed by a short handoff to the
next scene.

## Testing

- A pure motion model test covers clamping and chapter ordering.
- A source contract rejects React scroll state and requires a Reanimated shared
  value, UI-thread handler, and Android overscroll protection.
- Existing native landing interaction tests remain green.
- Mobile TypeScript validation must pass.

## Acceptance criteria

1. Scrolling does not call a React state setter for each scroll frame.
2. Continuous transforms, opacity, SVG progress, and scan motion run from a
   Reanimated shared value.
3. Process and cinematic items reveal in deterministic order with no abrupt
   overlap.
4. Android edge overscroll cannot stretch the landing story.
5. Reduced-motion, navigation, media fallback, RTL, and accessibility remain
   intact.
6. The previous public-question height change is restored and its tests pass.

