@echo off
REM run-tests.bat — CI test runner for 3D Print Pipeline (Windows)
REM Runs: Python schema tests → vitest frontend → Playwright E2E

setlocal enabledelayedexpansion
set "ROOT=%~dp0"
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
echo [1/3] !STAGE!
python "%ROOT%tests\test_schema_consistency.py"
if %ERRORLEVEL% neq 0 (
    set /a FAIL+=1
    echo [FAIL] !STAGE!
) else (
    set /a PASS+=1
    echo [PASS] !STAGE!
)
echo.

REM ── Stage 2: Python Backend Unit Tests ────────────────────────
set "STAGE=Python Backend Unit Tests"
echo [2/5] !STAGE!
python "%ROOT%tests\test_workflow_engine.py"
if %ERRORLEVEL% neq 0 (
    set /a FAIL+=1
    echo [FAIL] !STAGE!
) else (
    set /a PASS+=1
    echo [PASS] !STAGE!
)
echo.

REM ── Stage 3: Frontend Unit Tests (vitest) ─────────────────────
set "STAGE=Frontend Unit Tests (vitest)"
echo [3/5] !STAGE!
call npx vitest run tests/frontend/
if %ERRORLEVEL% neq 0 (
    set /a FAIL+=1
    echo [FAIL] !STAGE!
) else (
    set /a PASS+=1
    echo [PASS] !STAGE!
)
echo.

REM ── Stage 4: E2E Tests (Playwright) ───────────────────────────
set "STAGE=E2E Tests (Playwright)"
echo [4/5] !STAGE!
call npx playwright test --config=e2e/playwright.config.js
if %ERRORLEVEL% neq 0 (
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
