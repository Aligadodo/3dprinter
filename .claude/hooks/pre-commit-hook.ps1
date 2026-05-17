# pre-commit-hook.ps1 — Fast smoke tests for 3D Print Pipeline
# Install: copy to .git/hooks/pre-commit (without .ps1 extension) or configure via git config
# Runs: schema + engine + script error contracts + frontend vitest (~10-30s total)

$ErrorActionPreference = "SilentlyContinue"
$ROOT = "D:\projects\3dprint"
$FAIL = 0

function Run-Test {
    param($name, $cmd)
    $desc = "[pre-commit] $name"
    Write-Host -NoNewline "$desc ... "
    $out = Invoke-Expression $cmd 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host -ForegroundColor Green "PASS"
    } else {
        Write-Host -ForegroundColor Red "FAIL ($LASTEXITCODE)"
        $FAIL++
    }
}

Write-Host -ForegroundColor Cyan "[pre-commit] Running smoke tests..."
Write-Host ""

Run-Test "Schema Consistency" "python $ROOT\tests\test_schema_consistency.py"
Run-Test "Workflow Engine" "python $ROOT\tests\test_workflow_engine.py"
Run-Test "Script Error Contracts" "python -m pytest $ROOT\tests\test_scripts.py -k `"file_not_found or nonexistent or error_json`" -v --tb=line"
Run-Test "Frontend Unit Tests" "npx vitest run tests/frontend/ --reporter=default"

Write-Host ""
if ($FAIL -eq 0) {
    Write-Host -ForegroundColor Green "[pre-commit] All smoke tests passed."
    exit 0
} else {
    Write-Host -ForegroundColor Red "[pre-commit] $FAIL smoke test(s) FAILED."
    Write-Host -ForegroundColor Yellow "To skip pre-commit tests: git commit --no-verify"
    exit 1
}