@echo off
chcp 65001 >nul 2>&1
echo Fixing Next.js SWC dependencies...
cd /d "%~dp0\frontend"
rmdir /s /q node_modules 2>nul
del package-lock.json 2>nul
call npm install
echo.
echo Done! Now run start.bat to launch the app.
pause
