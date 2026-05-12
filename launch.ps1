# 3D Print Pipeline - Web Server Launcher (Windows)
# Usage: .\launch.ps1
#        .\launch.ps1 -Port 9090
#        .\launch.ps1 -Host 0.0.0.0 -Port 8080
#        .\launch.ps1 -NoBrowser

param(
    [string]$HostAddr = "127.0.0.1",
    [int]$Port = 8080,
    [switch]$NoBrowser = $false
)

$ErrorActionPreference = "Stop"
$ScriptDir = $PSScriptRoot

# Find Python
$PythonCmd = $null
$pythonNames = @("python", "python3", "py")

# Priority: project venv > system python
$venvPaths = @(
    (Join-Path $ScriptDir ".venv\Scripts\python.exe"),
    (Join-Path $ScriptDir "venv\Scripts\python.exe")
)
foreach ($vp in $venvPaths) {
    if (Test-Path $vp) {
        $PythonCmd = $vp
        break
    }
}

if (-not $PythonCmd) {
    foreach ($name in $pythonNames) {
        if (Get-Command $name -ErrorAction SilentlyContinue) {
            $PythonCmd = $name
            break
        }
    }
}

if (-not $PythonCmd) {
    Write-Host "Error: Python not found. Please install Python 3.10+ or activate a virtual environment." -ForegroundColor Red
    exit 1
}

Write-Host "Python: $PythonCmd" -ForegroundColor Cyan

# Build arguments
$args = @("-m", "web.server", "--host", $HostAddr, "--port", $Port)
if ($NoBrowser) {
    $args += "--no-browser"
}

# Start server from project root
Write-Host "Starting 3D Print Pipeline Server..." -ForegroundColor Green
Write-Host "  Host: $HostAddr" -ForegroundColor Gray
Write-Host "  Port: $Port" -ForegroundColor Gray
Write-Host ""

Set-Location $ScriptDir
& $PythonCmd $args

if ($LASTEXITCODE -ne 0) {
    Write-Host "Server exited with code $LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}
