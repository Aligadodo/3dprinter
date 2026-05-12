#!/usr/bin/env bash
# start-server.sh - Launch the 3D Print Pipeline web management platform
# Usage: ./start-server.sh [--lan] [--port 8080]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "================================================"
echo "   3D Print Pipeline - Web Management Platform"
echo "================================================"
echo

exec python "$SCRIPT_DIR/start-server.py" "$@"
