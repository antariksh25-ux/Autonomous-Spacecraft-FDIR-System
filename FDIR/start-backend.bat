@echo off
echo ========================================
echo Starting FDIR Backend API Server
echo ========================================
echo.
echo Backend will run on: http://localhost:8001
echo API Docs: http://localhost:8001/docs
echo.

cd /d "%~dp0"

REM Check if virtual environment exists
if exist ".venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
) else if exist "..\.venv\Scripts\activate.bat" (
    echo Activating parent virtual environment...
    call ..\.venv\Scripts\activate.bat
) else (
    echo No virtual environment found, using system Python
)

REM Check if dependencies are installed
python -c "import fastapi" 2>nul
if errorlevel 1 (
    echo.
    echo Installing dependencies...
    pip install -r requirements.txt
)

echo.
echo Starting FDIR API server...
python api_server.py

pause
