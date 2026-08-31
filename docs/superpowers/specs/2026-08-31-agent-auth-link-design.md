# Agent Authentication Link Design

**Date:** 2026-08-31
**Status:** Approved for implementation

## Goal

Let an administrator authenticate the Antigravity (`agy`) runner from Admin →
AI Settings without seeing a terminal. The admin receives the one-time browser
authorization link produced by the real CLI, completes Google sign-in, and
returns any authorization code through the existing dialog.

## Evidence and scope

The pinned image contains `agy` 1.1.22. Its official remote/SSH flow runs the
interactive CLI, prints a unique authorization URL, then asks for the code shown
by the browser. There is no separate `agy login` subcommand or machine API in the
pinned binary. Therefore the service must keep the real CLI process alive in a
PTY; a static URL or browser-only backend request would not represent the CLI's
PKCE session.

This change is limited to Antigravity authentication. Codex and Claude browser
flows retain their current pipe-based adapters. Model generation, provider
routing, credentials in PostgreSQL, and public service exposure are unchanged.

## Architecture and data flow

```text
Admin browser
    │ POST /api/v1/admin/ai/agent-service/auth/start
    ▼
Fitsho Backend
    │ internal bearer-authenticated request
    ▼
Agent Service
    │ hidden PTY, safe environment, persisted HOME
    ▼
agy 1.1.22
    │ emits URL + waits for browser code
    └──► validated URL/status only ──► Backend ──► Admin dialog
```

`AuthManager` remains the lifecycle owner. The Antigravity adapter starts
`agy` with no user-controlled arguments, enables the PTY process implementation,
and supplies the provider's SSH marker so the CLI selects its documented remote
URL flow. It presses one fixed Enter action after detecting the default Google
OAuth menu. The PTY output is bounded, ANSI-normalized, and parsed in memory.

## Security contract

- Only a fixed `agy` executable and fixed arguments may be started.
- The child receives the existing safe login environment plus fixed remote-flow
  markers; backend secrets and API credentials are excluded.
- The generated URL must be HTTPS, contain no URL credentials, and match the
  exact Antigravity Google OAuth hostname observed from the pinned CLI.
- URL/code/raw terminal output is never logged. The API returns only the
  existing safe session fields (`verification_url`, optional `user_code`, fixed
  `input_label`, status, expiry, safe error).
- The PTY process is terminated and reaped on success, failure, cancellation,
  expiry, shutdown, or disconnect cleanup. Completed CLI credentials remain
  only in the existing `/home/agent` persistent volume.
- A second active Antigravity auth session is rejected with the existing
  `auth_in_progress` contract.

## User experience

The existing `AgentAuthDialog` remains terminal-free. While the process emits a
handoff it displays the URL and an “open authentication page” action. After the
browser completes, any fixed authorization-code prompt is shown as the existing
single input field. Antigravity is no longer rejected as `manual_auth_only`; the
capability response identifies it as browser-link authentication so the panel
does not offer an unusable manual-only state.

## Failure behavior

Malformed, non-HTTPS, unapproved-host, truncated, or ambiguous output fails the
session with a safe generic auth error and kills the process. PTY EOF with a
non-zero exit is failed; a zero exit after the browser code is authenticated.
Expiry and cancellation never expose a partial handoff after the terminal state.

## Verification

Unit tests will cover PTY start/read/write/terminate behavior, ANSI and URL
parsing, remote markers, bounded output, auth state transitions, and safe API
responses. Integration tests will exercise `POST /v1/auth/start` for a fake
Antigravity process, verify the browser link reaches the backend/UI contract,
and ensure no raw output or credentials appear in telemetry. A disposable
container smoke test will run the pinned CLI with the remote markers and record
only the URL hostname and state, never the actual URL or code.
