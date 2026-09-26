# SPIDY - Autonomous Software Engineering Launcher
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  SPIDY - Autonomous Software Engineering" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

if (Test-Path ".venv\Scripts\python.exe") {
    & ".venv\Scripts\python.exe" server.py
} else {
    python server.py
}
