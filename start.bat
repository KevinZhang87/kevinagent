@echo off
chcp 65001 >nul 2>&1
echo ============================================
echo   KevinAgent
echo ============================================
echo.

cd /d "%~dp0"

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    pause
    exit /b 1
)

REM Check Node
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js is not installed or not in PATH.
    pause
    exit /b 1
)

REM Install backend dependencies only if needed
if not exist "backend\.deps_installed" (
    echo [1/3] Installing Python dependencies...
    cd backend
    pip install -r requirements.txt -q
    if errorlevel 1 (
        echo [ERROR] Failed to install Python dependencies.
        pause
        exit /b 1
    )
    echo done > .deps_installed
    cd ..
) else (
    echo [1/3] Python dependencies already installed. Skipping.
)

REM Install frontend dependencies only if needed
if not exist "frontend\node_modules" (
    echo [2/3] Installing Node.js dependencies...
    cd frontend
    call npm install
    if errorlevel 1 (
        echo [ERROR] Failed to install Node.js dependencies.
        pause
        exit /b 1
    )
    cd ..
) else (
    echo [2/3] Node.js dependencies already installed. Skipping.
)

REM Copy .env if not exists
if not exist backend\.env (
    copy backend\.env.example backend\.env >nul
    echo [3/3] Created backend\.env - please edit with your API keys.
) else (
    echo [3/3] .env already exists.
)

echo.
echo Starting services...
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:3000
echo.

REM Start backend (suppress reload noise, only show warnings+)
start "KevinAgent Backend" cmd /k "cd /d "%~dp0backend" && python -X utf8 run.py"

REM Wait a moment for backend to start
timeout /t 2 /nobreak >nul

REM Start frontend
start "KevinAgent Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo Both services started in separate windows.
echo Close those windows or press Ctrl+C in them to stop.
echo.
pause
