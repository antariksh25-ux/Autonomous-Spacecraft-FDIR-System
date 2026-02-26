# FDIR Backend API Server Startup Script
# Starts the FastAPI backend on port 8001

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Starting FDIR Backend API Server" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Backend will run on: http://localhost:8001" -ForegroundColor Green
Write-Host "API Docs: http://localhost:8001/docs" -ForegroundColor Green
Write-Host ""

# Change to script directory
Set-Location $PSScriptRoot

# Check if virtual environment exists
if (Test-Path ".venv\Scripts\Activate.ps1") {
    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    & .\.venv\Scripts\Activate.ps1
} elseif (Test-Path "..\.venv\Scripts\Activate.ps1") {
    Write-Host "Activating parent virtual environment..." -ForegroundColor Yellow
    & ..\.venv\Scripts\Activate.ps1
} else {
    Write-Host "No virtual environment found, using system Python" -ForegroundColor Yellow
}

# Check if dependencies are installed
try {
    python -c "import fastapi" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "FastAPI not installed"
    }
} catch {
    Write-Host ""
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    pip install -r requirements.txt
}

Write-Host ""
Write-Host "Starting FDIR API server..." -ForegroundColor Green
Write-Host "Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

python api_server.py
