@echo off
cd /d "%~dp0"

REM Conversation-driven push. Update the commit message each run to match what
REM this session is shipping; the comment below records the intended changeset.
REM (For ad-hoc solo pushes outside a conversation, use Manual push.bat.)
REM
REM Shipping this run (glossary deploy):
REM   - Render/glossary_app.py          new — glossary Flask app (WSGI-ready copy)
REM   - Render/glossary.db              new — SQLite DB (read-only in production)
REM   - Render/site_app.py              mount glossary at /glossary via DispatcherMiddleware
REM   - render.yaml                     gunicorn target: site_app:application
REM   - Tools/_redirects                add /glossary* proxy rule

REM Copy the latest glossary.db before every push so the deployed DB stays current.
REM Source: The Ultimate Longboard Wiki Project (canonical DB owner for now).
REM Path from deploy\: ..\..\  = Projects\  (deploy is inside Website Generators\)
copy /Y "..\..\The Ultimate Longboard Wiki Project\Wiki\Glossary\glossary.db" "Render\glossary.db"
if errorlevel 1 (
    echo ERROR: Could not copy glossary.db -- check that the Wiki project folder is present.
    pause
    exit /b 1
)
echo glossary.db copied.

git add -A
git status
git commit -m "Deploy glossary to tools.../glossary via DispatcherMiddleware"
git push origin main

pause
