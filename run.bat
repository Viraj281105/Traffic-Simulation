@echo off
title Traffic Simulation Runner
echo ========================================================
echo   Traffic Simulation Runner
echo ========================================================
echo.
echo How would you like to run the application?
echo [1] Run Natively (Local Python Virtualenv + npm dev server)
echo [2] Run via Docker (Docker Compose for backend, npm local dev for frontend)
echo.
set /p choice="Enter option (1 or 2): "

if "%choice%"=="2" (
    echo.
    echo Starting Backend via Docker Compose...
    start "Traffic Backend (Docker)" cmd /c "docker compose up --build"
) else (
    echo.
    echo Starting Backend Natively...
    start "Traffic Backend (Native)" cmd /c "cd backend && .venv\Scripts\uvicorn src.main:app --host 127.0.0.1 --port 8000"
)

echo.
echo Starting Frontend Dashboard...
start "Traffic Frontend" cmd /c "cd frontend && npm run dev"

echo.
echo Waiting for servers to initialize...
timeout /t 5 /nobreak >nul

echo.
echo Opening visualization in browser...
start http://localhost:5173/

echo.
echo.
echo Done! Keep the spawned command prompt windows open.
echo to shut down, close the spawned command windows.
echo.
pause
