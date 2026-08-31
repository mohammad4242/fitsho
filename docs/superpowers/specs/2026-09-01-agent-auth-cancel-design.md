# Admin Agent Authentication Cancellation Design

**Date:** 2026-09-01  
**Status:** Approved for implementation

## Goal

When an administrator starts authentication for an Agent that already has an
active authentication process, the admin dialog must offer a clear
«لغو احراز هویت قبلی» action. The action cancels the existing session, sends
`Esc` to a PTY-backed CLI such as Antigravity, reaps the process, and closes
the dialog. It must not start a replacement session automatically.

## Scope

This change covers the existing Admin → AI Settings authentication flow for
Antigravity, Codex, and Claude. It adds recovery for the existing
`auth_in_progress` response and keeps the current per-session cancel action.
It does not change provider credentials, model routing, authentication TTL, or
the browser OAuth URL contract.

## Architecture and data flow

```text
Admin dialog
    │ POST /api/v1/admin/ai/agent-service/auth/start
    │ ◄── 409 auth_in_progress
    │
    │ POST /api/v1/admin/ai/agent-service/auth/cancel-active
    │     { agent }
    ▼
Fitsho backend (admin + trusted-origin protected)
    │ internal bearer-authenticated proxy
    ▼
Agent Service
    │ AuthManager.cancel_active(agent), under its lifecycle lock
    │ mark canceled → release active slot → send Esc when PTY → terminate/reap
    └──► { agent, canceled }
```

The new endpoint is static and is declared before the existing UUID session
routes. The request reuses the existing agent-only auth request shape. The
response contains no session identifier, URL, code, terminal output, or
credential; `canceled` is false when another request already cleared the
active session, making the operation idempotent for the UI.

`AuthManager.cancel_active` identifies the active session while holding the
manager lock, transitions it to `canceled`, and releases the per-agent active
slot before doing process I/O. Process cleanup sends one fixed `Esc` byte for
PTY processes, ignores an already-closed PTY, then uses the existing
SIGTERM/SIGKILL and wait path. Non-PTY agents skip `Esc` and still terminate
through the same cleanup path.

## User experience

`AgentAuthDialog` preserves the stable `ApiError.code` from the start request.
Only when that code is `auth_in_progress` does it render the new translated
button beside the safe error. Clicking it disables the action, calls the
cancel-active endpoint for the selected Agent, and closes the dialog on any
successful response. The existing close/cancel button continues to cancel a
session that belongs to the current dialog. No raw downstream error text is
shown.

Translations are added for Persian and English, including the action label and
its in-progress state. Existing polling, URL allowlists, StrictMode cleanup,
and terminal-state behavior remain unchanged.

## Security and concurrency

- Both new routes require an authenticated admin and the existing trusted
  browser origin; the Agent Service route requires its internal bearer token.
- The endpoint accepts only a known `AgentName`; it never accepts a command,
  process identifier, or arbitrary terminal input.
- The manager lock prevents a race between starting an auth process and
  canceling the active process. A second cancellation is harmless.
- `Esc` is a fixed control byte, never user-provided content. All cleanup still
  reaps the process group and closes file descriptors.
- No auth URL, authorization code, token, or raw PTY output is added to API
  responses or telemetry.

## Verification

Tests will cover:

- PTY `Esc` delivery and existing termination behavior.
- Manager active-session cancellation, idempotency, slot release, and process
  reaping for PTY and pipe-backed processes.
- Agent Service and backend route contracts, auth/origin protection, and safe
  response fields.
- Frontend rendering of the button only for `auth_in_progress`, API call,
  disabled state, close-on-success behavior, and translated copy.

Runtime smoke verification will start a real pinned Agent Service auth process,
exercise cancellation, verify no `agy` process remains, and report only safe
status metadata.
