@echo off
cd /d "%~dp0"

REM Clear any stale .pyc bytecode so edits to site_app.py / generators/ always
REM take effect on next launch. Python normally invalidates pyc by mtime, but
REM on the Google Drive folder mtime can lag, leaving a stale cached module.
for /d /r %%i in (__pycache__) do @if exist "%%i" rd /s /q "%%i"

echo.
echo  Longboard Technology — local dev server
echo  Open http://localhost:5000 in your browser
echo  (tip: Ctrl-F5 to hard-refresh if you don't see your latest changes)
echo  Press Ctrl-C in this window to stop.
echo.

REM -B prevents Python from writing new .pyc files this session — keeps the
REM source-of-truth in the .py files and avoids the cache problem above.
python -B site_app.py

echo.
echo  Server stopped.
pause
