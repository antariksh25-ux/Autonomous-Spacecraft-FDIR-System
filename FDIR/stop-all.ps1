# FDIR System Stop Script
# Stops all running FDIR processes

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Stopping FDIR System" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Find and stop Python processes running api_server.py
Write-Host "Stopping backend processes..." -ForegroundColor Yellow
$backendProcesses = Get-Process python -ErrorAction SilentlyContinue | 
    Where-Object { $_.CommandLine -like "*api_server.py*" }

if ($backendProcesses) {
    $backendProcesses | Stop-Process -Force
    Write-Host "  Stopped $($backendProcesses.Count) backend process(es)" -ForegroundColor Green
} else {
    Write-Host "  No backend processes found" -ForegroundColor Gray
}

# Find and stop Node processes (Next.js)
Write-Host "Stopping frontend processes..." -ForegroundColor Yellow
$frontendProcesses = Get-Process node -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*next*dev*" }

if ($frontendProcesses) {
    $frontendProcesses | Stop-Process -Force
    Write-Host "  Stopped $($frontendProcesses.Count) frontend process(es)" -ForegroundColor Green
} else {
    Write-Host "  No frontend processes found" -ForegroundColor Gray
}

# Also stop uvicorn processes
Write-Host "Stopping uvicorn processes..." -ForegroundColor Yellow
$uvicornProcesses = Get-Process python -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*uvicorn*" }

if ($uvicornProcesses) {
    $uvicornProcesses | Stop-Process -Force
    Write-Host "  Stopped $($uvicornProcesses.Count) uvicorn process(es)" -ForegroundColor Green
} else {
    Write-Host "  No uvicorn processes found" -ForegroundColor Gray
}

Write-Host ""
Write-Host "All FDIR processes stopped" -ForegroundColor Green
Write-Host ""
Write-Host "Press any key to exit..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
