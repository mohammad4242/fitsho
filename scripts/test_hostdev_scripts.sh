#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
launcher="$project_root/scripts/run-host-backend.sh"
clone_script="$project_root/scripts/clone-hostdev-database.sh"

test -x "$launcher"
test -x "$clone_script"

grep -Fq '127.0.0.1:5433/fitsho' "$launcher"
grep -Fq -- '--port 8002' "$launcher"
grep -Fq 'COOKIE_SECURE="false"' "$launcher"
grep -Fq 'SESSION_COOKIE_NAME="fitsho_session"' "$launcher"
grep -Fq ':5174' "$launcher"

grep -Fq 'destination_project="fitsho-hostdev"' "$clone_script"
grep -Fq 'destination_service="hostdev-db"' "$clone_script"
grep -Fq 'pg_dump' "$clone_script"
grep -Fq 'psql' "$clone_script"

if grep -Eq '/tmp|mktemp|[.]dump|[.]sql' "$clone_script"; then
  echo "clone script must stream the database without a dump file" >&2
  exit 1
fi

echo "hostdev script contracts: ok"
