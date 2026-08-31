# CLI Authentication Flow Probe

Probe date: 2026-08-31

The probe used the image built from the current `agent-service/Dockerfile`. Login
commands were run in disposable containers with a ten-second timeout. Output was
classified in memory; no login URL, query string, code, prompt, account identity,
token, or raw stdout/stderr was recorded.

## Antigravity

- Version: `1.1.22`
- Help: `agy --help` exposes no `auth` or `login` subcommand. `agy auth --help`
  and `agy login --help` both returned the root help output.
- Exact automated auth command: none observed.
- Interactive behavior: `agy` opened an interactive terminal session and did not
  expose a parseable HTTPS URL or user/device code during the probe. `agy
  --prompt-interactive` is not usable without the required interactive context;
  `agy --print probe` exited with an authentication-related failure and no URL.
- PTY: required for the interactive CLI session, but no safe auth handoff was
  exposed by the tested binary.
- Allowed verification hosts: none. No hostname was allowlisted because no
  verification URL was emitted by a supported auth command.
- User input: no safe browser/device input contract was observed.
- Status command: none found in help.
- Completion/failure: unauthenticated print mode exited non-zero; the interactive
  session remained active until the probe harness stopped it. Natural successful
  auth and natural cancel were not attempted.
- Capability decision: `manual_auth_only`; no automated URL parser or guessed
  command is permitted.

## Codex

- Version: `codex-cli 0.151.0`
- Browser auth command: `codex login`.
- Device auth command: `codex login --device-auth`; this exact option is exposed
  by `codex login --help`.
- PTY: not required for the initial handoff. Both commands produced their handoff
  while stdin/stdout/stderr were pipes and emitted no ANSI sequences.
- Browser flow: `codex login` emitted an HTTPS handoff on stderr. The observed
  hostname was `auth.openai.com`; no user/device code was observed in this mode.
- Device flow: `codex login --device-auth` emitted an HTTPS handoff on stdout.
  The observed hostname was `auth.openai.com` and a device-code prompt was
  observed. The code itself was not retained.
- Status command: `codex login status` exited non-zero with a not-logged-in state
  and did not make a model request.
- Completion/failure: both login modes remained pending for browser completion in
  the probe. The harness stopped the process group after the timeout; natural
  success and cancel were not claimed.
- Supported automated flow: browser/device handoff only. The help also exposes
  API-key and access-token stdin modes; those credential-input modes are excluded
  from the admin auth adapter.

## Claude

- Version: `2.1.220 (Claude Code)`
- Exact subscription auth command: `claude auth login`. Help identifies the
  default as Claude subscription login and also exposes the explicit `--claudeai`
  option.
- PTY: not required for the initial handoff. The command emitted its handoff with
  pipes and no ANSI sequences.
- Browser flow: `claude auth login` emitted an HTTPS handoff on stdout. The
  observed hostname was `claude.com`; no user/device code was observed.
- Status commands: `claude auth status --json` and `claude auth status --text`
  exited non-zero with a not-logged-in state and did not make a model request.
- Completion/failure: the login command remained pending for browser completion
  in the probe and was stopped by the timeout harness. Natural success and cancel
  were not claimed.
- Scope: console/API-key login is not used by the subscription Agent Service
  adapter; no API key or access-token input is accepted.

## Probe gate

Only the evidence above may drive the adapters. Auth URL validation is restricted
to `auth.openai.com` for Codex and `claude.com` for Claude. Antigravity remains
manual-only until a future pinned binary exposes a documented, machine-readable,
safe auth handoff. Image capability remains disabled; no image smoke test was
performed.
