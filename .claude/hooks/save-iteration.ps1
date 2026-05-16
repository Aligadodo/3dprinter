# Iteration History — Hook Script
# Copies plan file to docs/iterations/ when it changes, for progress tracking.
# Triggered by Claude Code Stop hook (project-level).

param(
    [string]$PlanFile = "",
    [string]$IterDir = "D:\projects\3dprint\docs\iterations"
)

$ErrorActionPreference = "SilentlyContinue"

# Auto-detect most recent plan if not specified
if (-not $PlanFile -or -not (Test-Path $PlanFile)) {
    $plansDir = "$env:USERPROFILE\.claude\plans"
    if (Test-Path $plansDir) {
        $PlanFile = Get-ChildItem $plansDir -Filter "*.md" | Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName
    }
}

if (-not $PlanFile -or -not (Test-Path $PlanFile)) { exit 0 }

$planHash = (Get-FileHash $PlanFile -Algorithm MD5).Hash
$stateFile = Join-Path $IterDir ".last-save-hash"

# Check if plan changed since last save
$lastHash = $null
if (Test-Path $stateFile) { $lastHash = Get-Content $stateFile -Raw }
if ($planHash -eq $lastHash) { exit 0 }

# Read plan title from first H1 line
$planContent = Get-Content $PlanFile -Raw -Encoding UTF8
$titleLine = ($planContent -split "`n" | Select-String "^# " | Select-Object -First 1).ToString().TrimStart("# ")

# Generate filename
$timestamp = Get-Date -Format "yyyy-MM-dd-HHmmss"
$safeTitle = ($titleLine -replace '[^\w一-鿿-]', '-') -replace '-+', '-' -replace '^-|-$', ''
if (-not $safeTitle) { $safeTitle = "iteration" }
$filename = "$timestamp-$safeTitle.md"
$destPath = Join-Path $IterDir $filename

# Copy plan
Copy-Item $PlanFile $destPath -Force

# Update state
$planHash | Out-File $stateFile -NoNewline -Encoding utf8

# Update INDEX.md
$indexFile = Join-Path $IterDir "INDEX.md"
$entry = "- [$timestamp] [$titleLine]($filename)"
$existingEntries = @()
if (Test-Path $indexFile) {
    $existingEntries = Get-Content $indexFile -Encoding UTF8 |
        Where-Object { $_ -match '^- \[' } |
        Where-Object { $_ -ne "" }
}
$newContent = @("# Iteration History", "", "Sorted by time (newest first).", "") + @($entry) + $existingEntries
$newContent -join "`n" | Out-File $indexFile -Encoding utf8

Write-Output "[iter-hook] Saved: $filename"
