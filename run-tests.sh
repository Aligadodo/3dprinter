#!/bin/bash
# run-tests.sh — CI test runner for 3D Print Pipeline (Unix/macOS)
# Runs: Python schema → engine → scripts (pytest) → vitest → Playwright

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
PASS=0
FAIL=0
TOTAL=0

echo
echo "============================================================"
echo "  3D Print Pipeline — Test Suite Runner"
echo "============================================================"
echo

# Stage 1: Python Schema Consistency Tests
echo "[1/5] Python Schema Consistency"
if python "$ROOT/tests/test_schema_consistency.py"; then
    PASS=$((PASS+1)); echo "[PASS] Stage 1"
else
    FAIL=$((FAIL+1)); echo "[FAIL] Stage 1"
fi
echo

# Stage 2: Python Backend Unit Tests
echo "[2/5] Python Backend Unit Tests"
if python "$ROOT/tests/test_workflow_engine.py"; then
    PASS=$((PASS+1)); echo "[PASS] Stage 2"
else
    FAIL=$((FAIL+1)); echo "[FAIL] Stage 2"
fi
echo

# Stage 3: Python Script Tests (pytest)
echo "[3/5] Python Script Tests"
if python -m pytest "$ROOT/tests/test_scripts.py" -v; then
    PASS=$((PASS+1)); echo "[PASS] Stage 3"
else
    FAIL=$((FAIL+1)); echo "[FAIL] Stage 3"
fi
echo

# Stage 4: Frontend Unit Tests (vitest)
echo "[4/5] Frontend Unit Tests (vitest)"
if npx vitest run tests/frontend/; then
    PASS=$((PASS+1)); echo "[PASS] Stage 4"
else
    FAIL=$((FAIL+1)); echo "[FAIL] Stage 4"
fi
echo

# Stage 5: E2E Tests (Playwright)
echo "[5/5] E2E Tests (Playwright)"
if npx playwright test --config=e2e/playwright.config.js; then
    PASS=$((PASS+1)); echo "[PASS] Stage 5"
else
    FAIL=$((FAIL+1)); echo "[FAIL] Stage 5"
fi
echo

# Summary
TOTAL=$((PASS+FAIL))
echo "============================================================"
echo "  Test Results: $PASS passed, $FAIL failed ($TOTAL total)"
echo "============================================================"

exit $FAIL
