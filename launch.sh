#!/bin/bash
set -e

# 3D Print Pipeline - Web Server Launcher (Linux/macOS)
# Usage: ./launch.sh
#        ./launch.sh --port 9090
#        ./launch.sh --host 0.0.0.0 --port 8080
#        ./launch.sh --no-browser

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOST="127.0.0.1"
PORT="8080"
NO_BROWSER=""

# Find Python
PYTHON_CMD=""

# Priority: project venv > system python
for venv_bin in "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/venv/bin/python"; do
    if [ -f "$venv_bin" ]; then
        PYTHON_CMD="$venv_bin"
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    for name in python3 python; do
        if command -v "$name" >/dev/null 2>&1; then
            PYTHON_CMD="$name"
            break
        fi
    done
fi

if [ -z "$PYTHON_CMD" ]; then
    echo "Error: Python not found. Please install Python 3.10+ or activate a virtual environment." >&2
    exit 1
fi

echo "Python: $PYTHON_CMD"

# Parse arguments
while [ $# -gt 0 ]; do
    case "$1" in
        --host)
            HOST="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --no-browser)
            NO_BROWSER="--no-browser"
            shift
            ;;
        -h|--help)
            echo "Usage: ./launch.sh [--host HOST] [--port PORT] [--no-browser]"
            echo ""
            echo "Options:"
            echo "  --host HOST     Bind address (default: 127.0.0.1, use 0.0.0.0 for LAN)"
            echo "  --port PORT     Port number (default: 8080)"
            echo "  --no-browser    Don't open browser on start"
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            echo "Use --help for usage information" >&2
            exit 1
            ;;
    esac
done

echo "Starting 3D Print Pipeline Server..."
echo "  Host: $HOST"
echo "  Port: $PORT"
echo ""

cd "$SCRIPT_DIR"
exec "$PYTHON_CMD" -m web.server --host "$HOST" --port "$PORT" $NO_BROWSER
