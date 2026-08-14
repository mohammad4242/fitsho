#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
hostdev_lan_ips="${FITSHO_HOSTDEV_LAN_IPS:-${FITSHO_HOSTDEV_LAN_IP:-}}"

if [[ -z "$hostdev_lan_ips" ]]; then
  hostdev_lan_ips="$(hostname -I)"
fi
if [[ -z "$hostdev_lan_ips" ]]; then
  echo "Set FITSHO_HOSTDEV_LAN_IPS to the phone-accessible host addresses." >&2
  exit 1
fi

frontend_origins="http://localhost:5174,http://127.0.0.1:5174"
for hostdev_lan_ip in $hostdev_lan_ips; do
  if [[ "$hostdev_lan_ip" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    frontend_origins+=",http://${hostdev_lan_ip}:5174"
  fi
done

export DATABASE_URL="postgresql+psycopg://fitsho:fitsho@127.0.0.1:5433/fitsho"
export FRONTEND_ORIGIN="http://localhost:5174"
export FRONTEND_ORIGINS="$frontend_origins"
export COOKIE_SECURE="false"
export SESSION_COOKIE_NAME="fitsho_session"

cd "$project_root/backend"
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8002
