#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"
REQUESTED_BACKEND_PORT_START="${BACKEND_PORT_START:-}"
REQUESTED_FRONTEND_PORT_START="${FRONTEND_PORT_START:-}"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

if [[ -n "$REQUESTED_BACKEND_PORT_START" ]]; then
  BACKEND_PORT_START="$REQUESTED_BACKEND_PORT_START"
fi

if [[ -n "$REQUESTED_FRONTEND_PORT_START" ]]; then
  FRONTEND_PORT_START="$REQUESTED_FRONTEND_PORT_START"
fi

BACKEND_PORT_START="${BACKEND_PORT_START:-8000}"
FRONTEND_PORT_START="${FRONTEND_PORT_START:-3000}"

validate_port() {
  local name="$1"
  local value="$2"

  if ! [[ "$value" =~ ^[0-9]+$ ]] || ((value < 1 || value > 65535)); then
    echo "$name must be a port number between 1 and 65535." >&2
    exit 1
  fi
}

python_cmd=""
if command -v python3 >/dev/null 2>&1; then
  python_cmd="python3"
elif command -v python >/dev/null 2>&1; then
  python_cmd="python"
else
  echo "python or python3 is required to detect available ports." >&2
  exit 1
fi

validate_port "BACKEND_PORT_START" "$BACKEND_PORT_START"
validate_port "FRONTEND_PORT_START" "$FRONTEND_PORT_START"

port_available() {
  "$python_cmd" - "$1" <<'PY'
import errno
import socket
import sys

port = int(sys.argv[1])

try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
except OSError as exc:
    print(f"Unable to probe port {port}: {exc}", file=sys.stderr)
    sys.exit(2)

with sock:
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("", port))
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            sys.exit(1)
        print(f"Unable to probe port {port}: {exc}", file=sys.stderr)
        sys.exit(2)
    else:
        sys.exit(0)
PY
}

find_free_port() {
  local port="$1"
  local reserved="${2:-}"
  local status

  while ((port <= 65535)); do
    if [[ "$port" == "$reserved" ]]; then
      port=$((port + 1))
      continue
    fi

    if port_available "$port"; then
      echo "$port"
      return 0
    else
      status=$?
    fi

    if [[ "$status" -ne 1 ]]; then
      exit "$status"
    fi

    port=$((port + 1))
  done

  echo "No available port found at or above $1." >&2
  exit 1
}

BACKEND_PORT="$(find_free_port "$BACKEND_PORT_START")"
FRONTEND_PORT="$(find_free_port "$FRONTEND_PORT_START" "$BACKEND_PORT")"
NEXT_PUBLIC_API_BASE_URL="http://localhost:$BACKEND_PORT"

cat >"$ENV_FILE" <<EOF
BACKEND_PORT_START=$BACKEND_PORT_START
FRONTEND_PORT_START=$FRONTEND_PORT_START
BACKEND_PORT=$BACKEND_PORT
FRONTEND_PORT=$FRONTEND_PORT
NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
EOF

echo "Using backend:  http://localhost:$BACKEND_PORT"
echo "Using frontend: http://localhost:$FRONTEND_PORT"

if [[ "${1:-}" == "--write-env-only" ]]; then
  exit 0
fi

exec docker compose --env-file "$ENV_FILE" up --build "$@"
