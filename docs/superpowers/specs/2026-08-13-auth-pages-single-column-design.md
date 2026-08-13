# Single-Column Account Pages Design

## Goal

Remove the decorative promotional panel from every public account page so desktop and mobile users see only the account form, brand link, and language switcher.

## Scope

- Apply the single-column shell to login, registration, password recovery, password reset, and onboarding pages that use `AuthShell`.
- Keep the Fitsho brand link and language switcher visible at every viewport width.
- Keep each form centered with its existing bounded width.
- Preserve routes, authentication behavior, validation, translations, and API calls.
- Remove the unused promotional image import and markup from `AuthShell`.

## Layout

`AuthShell` remains the shared layout boundary. It renders one full-width form panel with a compact top navigation and centered content. The form panel owns the full viewport height on desktop and mobile. Responsive rules only adjust padding and vertical spacing; they do not change page structure.

## Verification

- A shared-shell test proves that promotional media and copy are absent while navigation and content remain present.
- Existing login, registration, and password-recovery tests continue to pass.
- Frontend lint and production build pass.
