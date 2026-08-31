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
