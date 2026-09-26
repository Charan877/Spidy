@echo off
title SPIDY // Autonomous Software Engineering
cd /d "%~dp0.."

echo ========================================================
echo   SPIDY - Autonomous Software Engineering
echo ========================================================
echo.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" server.py
) else (
    python server.py
)

pause
