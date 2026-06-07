@echo off
cd /d "%~dp0"

REM Clear any stale .pyc bytecode so edits to site_app.py / generators/ always
REM take effect on next launch. Python normally invalidates pyc by mtime, but
REM on the Google Drive folder mtime can lag, leaving a stale cached module.
for /d /r %%i in (__pycache__) do @if exist "%%i" rd /s /q "%%i"

echo.
echo  Longboard Technology — local dev server
echo  Flask:  http://localhost:5000
echo  tunnel: check the cloudflared window for your public URL
echo  (tip: Ctrl-F5 to hard-refresh if you don't see your latest changes)
echo.

REM Start Flask in its own window
start "Flask" cmd /k "python -B site_app.py"

REM Give Flask a moment to bind before opening the tunnel
timeout /t 2 /nobreak >nul

REM Start cloudflared tunnel in its own window
start "cloudflared" cmd /k "cloudflared tunnel --url localhost:5000"
