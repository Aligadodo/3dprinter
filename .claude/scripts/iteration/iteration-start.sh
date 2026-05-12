#!/usr/bin/env bash
# Iteration start hook for 3dprint project
set -euo pipefail
export PYTHONIOENCODING=utf-8
export PYTHONUTF8=1

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="D:/projects/3dprint"

python -X utf8 "$SCRIPT_DIR/iteration_start.py" "$PROJECT_DIR"
echo '{"decision":"continue"}'
