#!/usr/bin/env bash
# stop-server.sh - Terminate the 3D Print Pipeline server
# Usage: ./stop-server.sh [--port 8080]
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python "$SCRIPT_DIR/stop-server.py" "$@"
