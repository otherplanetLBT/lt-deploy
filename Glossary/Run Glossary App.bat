@echo off
cd /d "%~dp0"
echo Starting Glossary Reader App...
echo Open http://localhost:5001 in your browser.
echo Press Ctrl+C to stop.
echo.
python -B glossary_app.py
pause
