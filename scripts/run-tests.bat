@echo off
REM run-tests.bat — CI test runner for 3D Print Pipeline (Windows)
REM Runs: Python schema → Python engine → Python scripts → pytest API → vitest → Playwright

setlocal enabledelayedexpansion
set "ROOT=%~dp0..\"
pushd "%ROOT%"
set "PASS=0"
set "FAIL=0"
set "STAGE="

echo.
echo ============================================================
echo   3D Print Pipeline — Test Suite Runner
echo ============================================================
echo.

REM ── Stage 1: Python Schema Consistency Tests ──────────────────
set "STAGE=Python Schema Consistency"
echo [1/6] !STAGE!
python "%ROOT%tests\test_schema_consistency.py"
if !ERRORLEVEL! neq 0 (
    set /a FAIL+=1
    echo [FAIL] !STAGE!
) else (
    set /a PASS+=1
    echo [PASS] !STAGE!
)
echo.

REM ── Stage 2: Python Backend Unit Tests ────────────────────────
set "STAGE=Python Backend Unit Tests"
echo [2/6] !STAGE!
python "%ROOT%tests\test_workflow_engine.py"
if !ERRORLEVEL! neq 0 (
    set /a FAIL+=1
    echo [FAIL] !STAGE!
) else (
    set /a PASS+=1
    echo [PASS] !STAGE!
)
echo.

REM ── Stage 3: Python Script Tests ────────────────────────────────
set "STAGE=Python Script Tests"
echo [3/6] !STAGE!
python -m pytest "%ROOT%tests\test_scripts.py" -v
if !ERRORLEVEL! neq 0 (
    set /a FAIL+=1
    echo [FAIL] !STAGE!
) else (
    set /a PASS+=1
    echo [PASS] !STAGE!
)
echo.

REM ── Stage 4: Python API Tests ──────────────────────────────────
set "STAGE=Python API Tests"
echo [4/6] !STAGE!
python -m pytest "%ROOT%tests\test_api.py" -v --start-server
if !ERRORLEVEL! neq 0 (
    set /a FAIL+=1
    echo [FAIL] !STAGE!
) else (
    set /a PASS+=1
    echo [PASS] !STAGE!
)
echo.

REM ── Stage 5: Frontend Unit Tests (vitest) ─────────────────────
set "STAGE=Frontend Unit Tests (vitest)"
echo [5/6] !STAGE!
call npx vitest run tests/frontend/
if !ERRORLEVEL! neq 0 (
    set /a FAIL+=1
    echo [FAIL] !STAGE!
) else (
    set /a PASS+=1
    echo [PASS] !STAGE!
)
echo.

REM ── Stage 6: E2E Tests (Playwright) ───────────────────────────
set "STAGE=E2E Tests (Playwright)"
echo [6/6] !STAGE!
call npx playwright test --config=e2e/playwright.config.js
if !ERRORLEVEL! neq 0 (
    set /a FAIL+=1
    echo [FAIL] !STAGE!
) else (
    set /a PASS+=1
    echo [PASS] !STAGE!
)
echo.

REM ── Summary ───────────────────────────────────────────────────
echo ============================================================
echo   Test Results: !PASS! passed, !FAIL! failed
echo ============================================================

endlocal
