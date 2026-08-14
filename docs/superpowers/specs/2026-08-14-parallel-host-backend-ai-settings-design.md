# Parallel Host Backend and AI Settings Design

## Goal

Keep the current Fitsho stack running unchanged while adding a parallel local testing stack
that lets the backend use the host Xray proxy for OpenRouter.

## Runtime layout

- Existing stack remains on frontend `5173`, backend `8001`, and PostgreSQL `5432`.
- A separate Compose project runs a Vite frontend on `5174` and PostgreSQL on `5433`.
- A host-native FastAPI process runs on `8002`.
- The parallel frontend proxies `/api` and `/media` to `host.docker.internal:8002`.
- The host backend connects to PostgreSQL at `localhost:5433` and Xray at
  `socks5://127.0.0.1:10808`.
- The phone opens the host LAN address on port `5174`; state-changing requests accept that
  origin.

## Database clone

The PostgreSQL instance on `5433` uses its own named volume. It is initialized by a one-time,
read-only dump of the current database on `5432`, preserving users, administrator access, AI
settings, and application records. Later changes in either database do not affect the other.

Private media is not stored inside PostgreSQL. New body photos uploaded through the parallel
stack use the host backend's existing private media directory. Existing database records whose
private files are unavailable are not treated as proof that the clone failed.

## AI settings UI

- A stored API credential is represented inside the credential field with an ASCII mask such as
  `********1f4e`; plaintext is never returned by the backend.
- Entering a replacement key clears the display-only mask and uses a password input.
- Save, connection-test, and catalog-refresh feedback appears next to the relevant controls.
- AI settings cards, model selectors, status rows, and actions shrink to the mobile viewport and
  switch to a single-column layout where needed.

## OpenRouter behavior

The proxy address remains environment configuration and is never committed with credentials.
The host backend uses the stored encrypted OpenRouter key. Connection testing and model refresh
must be verified against the real provider from the host runtime before handoff.

Future foreign-server deployment may omit `OPENROUTER_PROXY_URL` when direct OpenRouter access is
available. This local layout does not change the production networking contract.

## Files and isolation

- Add a dedicated parallel Compose file; do not edit or stop the current Compose project.
- Make the Vite proxy target configurable while preserving the current `8001` default.
- Add a small host-backend launcher/configuration path without committing `.env` or secrets.
- Preserve all unrelated working-tree files and the existing modified `compose.yaml`.

## Verification

- Frontend tests cover masked credential display, operation-local feedback, and responsive
  containment hooks.
- Backend AI configuration tests continue to verify encrypted persistence and masked responses.
- Run focused tests first, followed by frontend lint, tests, build, and relevant backend tests.
- Verify both stacks remain reachable, the cloned admin can sign in, the host backend reaches the
  cloned database, OpenRouter connection succeeds, and the catalog refresh stores models.
- Verify the parallel app is reachable from the phone-facing LAN URL on port `5174`.
