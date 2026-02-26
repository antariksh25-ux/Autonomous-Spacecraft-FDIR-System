@echo off
echo ========================================
echo Starting FDIR Frontend Dashboard
echo ========================================
echo.
echo Frontend will run on: http://localhost:3000
echo.

cd /d "%~dp0\frontend"

REM Check if node_modules exists
if not exist "node_modules" (
    echo Installing dependencies...
    call npm install
)

echo.
echo Starting Next.js development server...
call npm run dev

pause
