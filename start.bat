@echo off
title AgenticRAG Launcher
cd /d "%~dp0"

set PYTHON=%~dp0.venv\Scripts\python.exe
set PROJECT=%~dp0

echo ============================================
echo   AgenticRAG - One-Click Start
echo ============================================
echo.

echo [0/3] Clearing local ports 8080 and 5173...
%PYTHON% -c "import subprocess; r=subprocess.run(['netstat','-ano'],capture_output=True,text=True); [subprocess.run(['taskkill','/PID',l.split()[-1],'/F'],capture_output=True) for l in r.stdout.splitlines() if (':8080 ' in l or ':5173 ' in l) and 'LISTENING' in l]"

echo [1/3] Verifying npm is on PATH...
for /f "tokens=*" %%i in ('where npm 2^>nul') do set NPM=%%i
if not defined NPM (
    echo [ERROR] npm not found in PATH. Install Node.js, then re-run start.bat.
    pause
    exit /b 1
)
echo   npm: %NPM%

echo [2/3] Starting backend (SSH tunnel + remote services + FastAPI on :8080)...
start "AgenticRAG Backend" cmd /k "cd /d %PROJECT% && %PYTHON% run.py & echo. & echo [Backend exited] & pause"

echo [3/3] Starting frontend (Vite on :5173)...
start "AgenticRAG Frontend" cmd /k "cd /d %PROJECT%frontend && %NPM% run dev & echo. & echo [Frontend exited] & pause"

echo.
echo Open http://localhost:5173 when Backend window shows "Uvicorn running on port 8080".
echo Worker model loading takes ~2 minutes on first start.
echo If a window flashes and closes — check the title for details, or scroll up before pressing any key.
echo.
pause
