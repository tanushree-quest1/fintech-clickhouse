@echo off
echo ========================================================
echo   Starting Banking Control Tower Dashboard Services
echo ========================================================
echo.

echo Starting FastAPI Real-Time Backend on port 8000...
start "Banking Control Tower Backend" cmd /k "python -m backend.main"

echo Waiting 3 seconds for backend to initialize...
timeout /t 3 /nobreak >nul

echo Starting Vite React Frontend on port 5173...
cd frontend
start "Banking Control Tower Frontend" cmd /k "npm run dev"

echo.
echo ========================================================
echo   Services Launched!
echo   Dashboard UI: http://localhost:5173
echo   API & WS:     http://localhost:8000
echo ========================================================
