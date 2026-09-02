FROM node:22.18.0-bookworm-slim AS node-runtime

FROM python:3.12-slim-bookworm

ARG AGY_VERSION=1.1.22
ARG AGY_SHA256_AMD64=1e1a219a86e75d7c6351f96d182ca2105302d5c34d8fa9c31265dc0adf24145f
ARG AGY_SHA256_ARM64=a68925bc7336eb0b90de1e1aefd44d535f5487b7cf606a76fdb982207aef9a2e
ARG CODEX_VERSION=0.151.0
ARG CLAUDE_VERSION=2.1.220
ARG TARGETARCH

ENV HOME=/home/agent \
    PATH=/opt/fitsho-agent/bin:/home/agent/.local/bin:/app/.venv/bin:/opt/venv/bin:$PATH \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    CLAUDE_CODE_DISABLE_AUTOUPDATE=1

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates curl dbus git gnome-keyring \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash agent

COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=node-runtime /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx
COPY --from=ghcr.io/astral-sh/uv:0.8.14 /uv /uvx /usr/local/bin/

RUN mkdir -p /opt/fitsho-agent/bin \
    && chown -R agent:agent /opt/fitsho-agent

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY app ./app

USER agent
RUN set -eux; \
    case "${TARGETARCH:-amd64}" in \
      amd64) agy_arch="x64"; agy_sha256="${AGY_SHA256_AMD64}" ;; \
      arm64) agy_arch="arm64"; agy_sha256="${AGY_SHA256_ARM64}" ;; \
      *) echo "Unsupported Antigravity architecture: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    agy_archive="/home/agent/agy.tar.gz"; \
    curl --fail --silent --show-error --location --retry 3 \
      "https://github.com/google-antigravity/antigravity-cli/releases/download/${AGY_VERSION}/agy_cli_linux_${agy_arch}.tar.gz" \
      --output "${agy_archive}"; \
    echo "${agy_sha256}  ${agy_archive}" | sha256sum --check --status; \
    mkdir -p /home/agent/agy-extract /home/agent/.local/bin; \
    tar --extract --gzip --file "${agy_archive}" --directory /home/agent/agy-extract; \
    agy_binary="$(find /home/agent/agy-extract -type f \( -name agy -o -name antigravity \) -print -quit)"; \
    test -n "${agy_binary}"; \
    install -m 0755 "${agy_binary}" /opt/fitsho-agent/bin/agy; \
    rm -rf /home/agent/agy-extract "${agy_archive}"; \
    test "$(agy --version | head -n 1)" = "${AGY_VERSION}" \
    && npm install --global --prefix /opt/fitsho-agent @openai/codex@${CODEX_VERSION} \
    && test "$(codex --version | head -n 1)" = "codex-cli ${CODEX_VERSION}" \
    && npm install --global --prefix /opt/fitsho-agent @anthropic-ai/claude-code@${CLAUDE_VERSION} \
    && test "$(claude --version | head -n 1)" = "${CLAUDE_VERSION} (Claude Code)"

COPY --chown=agent:agent docker/entrypoint.sh /usr/local/bin/fitsho-agent-entrypoint
RUN chmod 0755 /usr/local/bin/fitsho-agent-entrypoint

EXPOSE 9001
ENTRYPOINT ["/usr/local/bin/fitsho-agent-entrypoint"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9001"]
