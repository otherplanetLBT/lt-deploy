@echo off
cd /d "%~dp0"
echo.
echo  ── Longboard Technology — Manual Push ──────────────────────────────────────
echo.

git status
echo.

set /p MSG=Commit message:
if "%MSG%"=="" (
    echo No message entered. Aborting.
    pause
    exit /b 1
)

git add .
git commit -m "%MSG%"
git push origin main

echo.
echo  Done.
pause
