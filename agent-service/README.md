# Fitsho Agent Service

The Agent Service is a private, internal-only HTTP service on port `9001`.
It contains the pinned Antigravity, Codex, and Claude CLIs in one image. The
service never receives backend secrets, PostgreSQL credentials, Docker access,
or the user's media archive. Request files are copied into short-lived
workspaces by the application.

## Build and run

From the repository root:

```bash
export AGENT_SERVICE_TOKEN="$(openssl rand -hex 32)"
docker compose build agent-service
docker compose up -d db agent-service backend
```

`agent-service` has no host port mapping. The backend reaches it at
`http://agent-service:9001`. If its token is absent, the Agent Service exits;
the backend remains able to start and use API-mode providers.

The Agent Service container is non-root, read-only apart from its persistent
`/home/agent` volume and request-scoped `/tmp`. It has no Docker socket,
database, backend source, or Fitsho private-media mount. The backend keeps
body photos, food photos, and nutrition-lab uploads in separate persistent
bind mounts under `backend/var/private/`.

## One-time CLI login

Authentication is performed manually inside the running container. Credentials
are stored in the named `fitsho_agent_home` volume and are not part of the
image:

```bash
docker compose exec agent-service agy
docker compose exec agent-service codex login
docker compose exec agent-service claude
```

Complete each provider's browser or device flow, then exit the interactive
session. Do not put subscription credentials or API keys in `compose.yaml`,
the image, or PostgreSQL. Removing `fitsho_agent_home` intentionally removes
these saved sessions.

## Contract smoke check

```bash
docker compose exec agent-service curl -fsS \
  -H "Authorization: Bearer ${AGENT_SERVICE_TOKEN}" \
  http://127.0.0.1:9001/v1/capabilities
```

The response is authoritative: a provider is exposed only after its binary,
configuration, authentication, and tested capabilities are available. Image
input remains disabled until a real container smoke test proves it for that
CLI.

## Operations runbook

### Verify capabilities and run the admin test

The capabilities response is the source of truth for installed providers,
authentication state, model allowlists, and text/image support. Use the admin
dashboard's **AI Task Settings → Agent Service → Test** action with the exact
agent and model shown by that response. This exercises the same authenticated
route used by the backend without exposing provider credentials.

Do not enable a model allowlist or image capability based on configuration
alone. Keep both disabled until a real container smoke test succeeds for the
specific CLI and model.

### Restart and persistence check

Restart the service, then repeat the capabilities request and the admin Test:

```bash
docker compose restart agent-service
docker compose exec agent-service curl -fsS \
  -H "Authorization: Bearer ${AGENT_SERVICE_TOKEN}" \
  http://127.0.0.1:9001/v1/capabilities
```

The provider login state must remain available because it is stored in the
named `fitsho_agent_home` volume. If authentication disappears, stop and
investigate the volume mount; do not log in with credentials embedded in
compose files or shell history.

### Local proxy use

When provider login requires a local HTTP(S) proxy, inject proxy variables at
runtime and keep Docker-internal hosts in `NO_PROXY`:

```bash
docker compose exec \
  -e HTTP_PROXY="${HTTP_PROXY}" \
  -e HTTPS_PROXY="${HTTPS_PROXY}" \
  -e NO_PROXY="agent-service,db,localhost,127.0.0.1" \
  agent-service agy
```

Use the same runtime environment for the corresponding `codex login` or
`claude` command. Never place proxy credentials, provider tokens, or API keys
in this README or in `compose.yaml`.

### Back up the authentication volume

Back up `fitsho_agent_home` before changing images, hosts, or volume mounts.
The archive contains sensitive provider sessions; protect it like a secret and
never commit it:

```bash
mkdir -p backups
docker run --rm \
  -v fitsho_agent_home:/source:ro \
  -v "$PWD/backups:/backup" \
  alpine tar czf /backup/fitsho_agent_home.tgz -C /source .
```

### Disable or revert safely

For an emergency disable, open the admin dashboard's **AI Task Settings**,
turn off **Agent Service**, and save. The backend then falls back to its API
provider path. To revert only one task, edit that task's provider in the same
screen to **API**, save, and run the task's Test action before re-enabling any
Agent Service task. This does not delete the authentication volume.
