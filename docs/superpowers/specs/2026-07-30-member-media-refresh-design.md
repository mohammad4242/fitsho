# Member Media Refresh Design

## Goal

Replace the low-quality authenticated-page backgrounds with the supplied media while keeping exercise content, forms, and program data readable and unchanged.

## Scope

- Today: replace the existing hero and story image set with the supplied stills.
- Workout plan: add one muted, visibility-controlled header video with a supplied still fallback.
- Exercise catalog and exercise detail: add still-image header treatments only; exercise media remains separate.
- Profile, onboarding, and admin: add distinct low-contrast header images.
- Preserve routes, API contracts, database behavior, form behavior, and exercise media.

## Media Assignment

| Surface | Media | Behavior |
| --- | --- | --- |
| Today hero and story | `hero-strength-fallback.jpg`, `plan-focus-fallback.jpg`, `progress-drive-fallback.jpg` | Static images with an accessible dark overlay. |
| Workout-plan header | `plan-focus.mp4` | Muted; plays only while visible; uses `plan-focus-fallback.jpg` for reduced motion or playback failure. |
| Exercise catalog and detail headers | `hero-strength-fallback.jpg` | Static treatment only; never replaces per-exercise video/image. |
| Profile and onboarding | `auth-training-accent.jpg` | Static header treatment. |
| Admin | `app-training-accent.jpg` | Static header treatment. |

## Design Rules

- Each page owns a single media treatment; no repeated full-screen video.
- Text and controls sit above an opaque/gradient overlay with sufficient contrast.
- Media is decorative except the workout-plan video, which has an empty alt equivalent and a still fallback.
- Mobile uses the same assignment with tighter image crops; reduced-motion always uses still images.

## Testing

- Add focused tests for video fallback/visibility behavior and header-media rendering.
- Run the complete frontend test suite, lint, and production build.
