#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
hostdev_lan_ip="${FITSHO_HOSTDEV_LAN_IP:-}"

if [[ -z "$hostdev_lan_ip" ]]; then
  hostdev_lan_ip="$(hostname -I | awk '{print $1}')"
fi
if [[ -z "$hostdev_lan_ip" ]]; then
  echo "Set FITSHO_HOSTDEV_LAN_IP to the phone-accessible host address." >&2
  exit 1
fi

export DATABASE_URL="postgresql+psycopg://fitsho:fitsho@127.0.0.1:5433/fitsho"
export FRONTEND_ORIGIN="http://localhost:5174"
export FRONTEND_ORIGINS="http://localhost:5174,http://127.0.0.1:5174,http://${hostdev_lan_ip}:5174"
export COOKIE_SECURE="false"
export SESSION_COOKIE_NAME="fitsho_session"

cd "$project_root/backend"
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8002
