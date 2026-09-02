# Agent Service proxy control design

## Goal

Allow an administrator to control the network route used by the shared Agent
Service without coupling the application to V2Ray. Local development will use
the deployment's current proxy by default. A server with supported direct Google
egress can leave the proxy disabled or use the deployment default with empty
proxy variables.

## Decisions

- Proxy configuration is global to the Agent Service, not task-scoped or
  profile-scoped. The CLI transport is shared by generation, task smoke tests,
  capabilities, and authentication.
- The Agent Service remains on the internal Docker network. The local V2Ray
  listener is made reachable from Docker by deployment configuration; the
  Agent Service does not use host networking.
- The deployment default is the `HTTP_PROXY`/`HTTPS_PROXY` environment captured
  when the Agent Service starts. A custom admin value is one validated proxy URL
  applied to both variables.
- Disabling proxy removes proxy variables from new provider subprocesses while
  preserving `NO_PROXY` and the saved custom value.
- Custom proxy URLs are encrypted with the existing AI credential cipher. API
  responses, audit events, telemetry, and UI state expose only a safe mask.

## Runtime architecture

The Agent Service will own a small in-memory runtime proxy state initialized
from its process environment. Every new runner and authentication subprocess
gets a snapshot of this state, so a setting change applies without rebuilding
or restarting the container. An already running subprocess keeps the snapshot
it started with.

The Backend remains the only public admin boundary:

1. `GET /api/v1/admin/ai/agent-service/proxy` returns the desired state,
   deployment-default availability, safe masked status, and apply status.
2. `PUT /api/v1/admin/ai/agent-service/proxy` validates and persists the
   desired state, records an audit event, and applies it through an internal
   token-protected Agent Service runtime endpoint.
3. The Backend synchronizes the persisted state when it starts and reports a
   pending apply state if the Agent Service is temporarily unreachable.
4. The frontend never sends proxy configuration directly to the Agent Service.

The persisted singleton contains `enabled`, source (`deployment_default` or
`custom`), encrypted custom URL, safe masked URL, actor, and timestamps. A
missing row behaves as enabled deployment-default mode, preserving the current
local proxy behavior.

## Admin UI

The existing AI settings page will receive a dedicated Agent Service network
panel above task routing. It will contain:

- an accessible on/off checkbox labelled as using a proxy;
- deployment-default and custom-proxy choices;
- a custom proxy URL field shown only for custom mode;
- a masked current value and a clear replacement hint, without returning the
  stored secret to the browser;
- an apply/save action and a visible applied/pending/error status.

The panel will reuse the existing AI settings visual language, remain usable in
RTL Persian and English, preserve keyboard focus, and collapse to one column on
mobile. Saving task-specific AI settings will not change the global proxy.

## Error and reproducibility fixes included

- Classify the provider message `User location is not supported for the API use`
  as a stable `location_unsupported` error and map it to a safe admin/user
  message instead of `provider_unavailable`.
- Keep raw provider stderr out of API responses and telemetry.
- Install pinned CLI binaries outside the persistent `/home/agent` state volume;
  keep that volume for authentication and cache state only. The image-owned
  binary path must take precedence so a rebuild cannot be shadowed by a stale
  volume binary.

## Verification

- Agent Service unit and API tests cover deployment-default, custom, disabled,
  redaction, internal authorization, dynamic runner/auth snapshots, and
  location-error classification.
- Backend tests cover admin authorization and trusted-origin protection,
  encrypted persistence, safe masking, audit fields, Agent Service apply/sync,
  and error-code mapping.
- Frontend tests cover initial default display, custom entry, disabling,
  save/error feedback, responsive containment, and absence of proxy secrets in
  rendered output.
- Docker verification checks the resolved CLI version/path after rebuild.
- A live local smoke test will run with the host-reachable V2Ray proxy. Direct
  egress will be tested only when the deployment provides it; production proxy
  variables remain optional and are not hardcoded in the repository.

## Out of scope

- Editing or migrating the user's V2Ray/Xray profile automatically.
- Exposing Agent Service or proxy controls to non-admin users.
- Silent fallback from Agent Service to a different AI provider.
