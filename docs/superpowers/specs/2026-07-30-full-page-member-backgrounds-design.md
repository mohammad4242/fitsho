# Full-page Member Backgrounds Design

## Goal

Show the supplied Fitsho still images as the full viewport background on every post-registration route. Do not confine the image to a hero card.

## Scope

- Today: `hero-strength-fallback.jpg`
- Workout plan: `plan-focus-fallback.jpg`
- Exercise catalog and detail: `hero-strength-fallback.jpg`
- Profile and onboarding: `auth-training-accent.jpg`
- Admin list, new exercise, and edit exercise: `app-training-accent.jpg`

Login, registration, backend, API, data, and exercise media are out of scope.

## Layout

Each routed page shell renders one `MemberHeaderMedia` layer as a fixed `cover` background behind the whole viewport. The existing header, content, forms, and controls receive a higher stacking layer. A dark, static veil is part of the background layer so text remains readable.

The current image-filled header cards are removed. Their content remains in place as transparent or lightly translucent content surfaces; cards and form fields keep their current opaque treatment where it is needed for legibility and input contrast.

Workout plan uses its supplied still image, not an autoplaying background video. Exercise demonstration media remains unchanged.

## Accessibility and resilience

- Decorative page backgrounds remain hidden from assistive technology.
- The background image uses `object-fit: cover` and stays fixed while content scrolls.
- Existing keyboard navigation, labels, focus states, and API behavior do not change.
- The image element remains the fallback if an optional background video is ever enabled later.

## Verification

- Update page tests to assert the full-page background layer and its assigned asset.
- Test that the workout page uses the assigned still instead of a background video.
- Run frontend lint, all tests, production build, and a local browser check on representative desktop and mobile widths.
