#!/usr/bin/env bash
# Iteration report hook for 3dprint project
set -euo pipefail
export PYTHONIOENCODING=utf-8
export PYTHONUTF8=1

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="D:/projects/3dprint"

python -X utf8 "$SCRIPT_DIR/iteration_report.py" "$PROJECT_DIR"

REPORT_DIR="$PROJECT_DIR/docs/iterations"
REPORT_FILE=$(ls -t "${REPORT_DIR}/"*-report.md 2>/dev/null | head -1)
REPORT_NAME=$(basename "$REPORT_FILE" 2>/dev/null || echo "unknown")

echo "{\"decision\":\"continue\",\"systemMessage\":\"📊 迭代报告已保存: docs/iterations/${REPORT_NAME}\"}"
