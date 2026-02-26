@echo off
echo ========================================
echo Starting FDIR Full Stack
echo ========================================
echo.
echo Backend: http://localhost:8001
echo Frontend: http://localhost:3000
echo.

cd /d "%~dp0"

REM Start backend in new window
start "FDIR Backend" cmd /k "call start-backend.bat"

REM Wait 3 seconds for backend to start
timeout /t 3 /nobreak >nul

REM Start frontend in new window  
start "FDIR Frontend" cmd /k "call start-frontend.bat"

echo.
echo Both services started in separate windows
echo Close this window or press any key to continue...
pause >nul
