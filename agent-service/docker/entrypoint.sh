#!/bin/sh
set -eu

# Antigravity uses the user's session keyring. Keep the bus and keyring inside
# this container without starting a desktop environment.
runtime_dir="${XDG_RUNTIME_DIR:-/tmp/agent-runtime}"
mkdir -p "$runtime_dir"
chmod 700 "$runtime_dir"
export XDG_RUNTIME_DIR="$runtime_dir"

exec dbus-run-session -- sh -c '
  if command -v gnome-keyring-daemon >/dev/null 2>&1; then
    keyring_env="$(gnome-keyring-daemon --start --components=secrets 2>/dev/null || true)"
    while IFS= read -r keyring_line; do
      case "$keyring_line" in
        GNOME_KEYRING_CONTROL=*|SSH_AUTH_SOCK=*) export "$keyring_line" ;;
      esac
    done <<EOF
$keyring_env
EOF
  fi
  exec "$@"
' fitsho-agent-session "$@"
