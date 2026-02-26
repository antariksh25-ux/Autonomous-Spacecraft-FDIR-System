# FDIR Frontend Dashboard Startup Script
# Starts the Next.js development server on port 3000

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Starting FDIR Frontend Dashboard" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Frontend will run on: http://localhost:3000" -ForegroundColor Green
Write-Host ""

# Change to frontend directory
Set-Location "$PSScriptRoot\frontend"

# Check if node_modules exists
if (-not (Test-Path "node_modules")) {
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    npm install
}

Write-Host ""
Write-Host "Starting Next.js development server..." -ForegroundColor Green
Write-Host "Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

npm run dev
