# Body Photo Upload Origin and Gray Design

## Goal

Fix phone uploads rejected as untrusted requests and change the standardized background from the
near-white gray to the approved soft neutral gray `#A0A3A1`.

## Design

- Keep trusted-origin enforcement enabled. Add the active LAN origin to local runtime
  configuration instead of weakening origin validation.
- Preserve structured backend photo-validation codes. When an API error is a trusted-origin
  rejection, show an actionable connection message instead of the generic upload failure.
- Use RGB `[160, 163, 161]` for background compositing. Segmentation, pixels belonging to the
  body, canvas dimensions, and geometry remain unchanged.

## Verification

- A frontend test must fail if the compositor receives a different neutral-gray RGB value.
- A wizard test must fail if an untrusted-origin response becomes a generic upload error.
- Verify an authenticated create/upload request from the active LAN origin.
- Run focused frontend tests, build, lint, backend tests, and runtime proxy checks.
