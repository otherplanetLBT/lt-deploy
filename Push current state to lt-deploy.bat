@echo off
cd /d "%~dp0"

REM Conversation-driven push. Update the commit message each run to match what
REM this session is shipping; the comment below records the intended changeset.
REM (For ad-hoc solo pushes outside a conversation, use Manual push.bat.)
REM
REM Shipping this run (give-up timeout, pivot-cup + riser-pad):
REM   - Tools/pivot-cup/index.html   added REQUEST_TIMEOUT_MS (45s). A request
REM   - Tools/riser-pad/index.html   that never settles -- dropped connection,
REM                                  or gunicorn killing a worker past its own
REM                                  60s --timeout -- previously left the UI
REM                                  stuck on "Generating..." forever, since
REM                                  nothing ever gave up on it. Now the
REM                                  client aborts after 45s, re-enables the
REM                                  Preview button, and shows an honest
REM                                  "Still not responding..." message instead
REM                                  of hanging silently.
REM                                  (Found testing the previous push: pivot
REM                                  cup worked, riser pad's heavier boolean-
REM                                  subtract geometry likely pushed a cold
REM                                  start over gunicorn's timeout.)

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
git commit -m "Add client-side give-up timeout so a hung request re-enables Preview instead of sticking on Generating forever (pivot-cup + riser-pad)"
git push origin main

pause
