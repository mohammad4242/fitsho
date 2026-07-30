# Full-page Member Backgrounds Design

## Goal

Show the supplied Fitsho media as the full viewport background on every post-registration route. Do not confine the media to a hero card.

## Scope

- Today: `hero-strength.mp4` with `hero-strength-fallback.jpg`
- Workout plan: `plan-focus.mp4` with `plan-focus-fallback.jpg`
- Exercise catalog and detail: `hero-strength-fallback.jpg`
- Profile and onboarding: `auth-training-accent.jpg`
- Admin list, new exercise, and edit exercise: `app-training-accent.jpg`

Login, registration, backend, API, data, and exercise media are out of scope.

## Layout

Each routed page shell renders one `MemberHeaderMedia` layer as a fixed `cover` background behind the whole viewport. The existing header, content, forms, and controls receive a higher stacking layer. A dark, static veil is part of the background layer so text remains readable.

The current image-filled header cards are removed. Their content remains in place as transparent or lightly translucent content surfaces; cards and form fields keep their current opaque treatment where it is needed for legibility and input contrast.

Today and workout plan use their distinct supplied videos as muted, visibility-controlled full-page backgrounds. Their supplied still images remain the reduced-motion and playback-error fallback. Profile, onboarding, catalog, exercise detail, and admin use only the assigned static images. Exercise demonstration media remains unchanged.

## Accessibility and resilience

- Decorative page backgrounds remain hidden from assistive technology.
- The background image uses `object-fit: cover` and stays fixed while content scrolls.
- Existing keyboard navigation, labels, focus states, and API behavior do not change.
- The image element is the fallback for the two background videos.

## Verification

- Update page tests to assert the full-page background layer and its assigned image or video.
- Test video visibility and still-image fallback on Today and workout plan.
- Run frontend lint, all tests, production build, and a local browser check on representative desktop and mobile widths.
