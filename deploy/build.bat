@echo off
setlocal

set REGISTRY=%REGISTRY%
set TAG=%TAG:latest%
set PUSH=%PUSH:false%

echo ============================================
echo   KevinAgent - Docker Build
echo ============================================
echo.

echo [1/2] Building backend image...
docker build -t %REGISTRY%kevin-agent/backend:%TAG% -f backend/Dockerfile backend/
if errorlevel 1 exit /b 1

echo [2/2] Building frontend image...
docker build --build-arg NEXT_PUBLIC_API_URL=http://localhost:8000 --build-arg NEXT_PUBLIC_WS_URL=ws://localhost:8000 -t %REGISTRY%kevin-agent/frontend:%TAG% -f frontend/Dockerfile frontend/
if errorlevel 1 exit /b 1

echo.
echo Build complete!
echo   - %REGISTRY%kevin-agent/backend:%TAG%
echo   - %REGISTRY%kevin-agent/frontend:%TAG%

endlocal
pause
