@echo off
cd /d "%~dp0"

REM Conversation-driven push. Update the commit message each run to match what
REM this session is shipping; the comment below records the intended changeset.
REM (For ad-hoc solo pushes outside a conversation, use Manual push.bat.)
REM
REM Shipping this run (fix riser-pad's missing boot auto-preview):
REM   - Tools/riser-pad/index.html   added the missing `runPreview(true);` to
REM                                  the boot sequence (pivot-cup already had
REM                                  it). Without it, riser-pad never sent a
REM                                  preview request on page load at all --
REM                                  the loading overlay's static HTML (already
REM                                  class="visible", text "Generating
REM                                  preview...") just sat there forever with
REM                                  nothing to clear it, on warm OR cold
REM                                  Render. Confirmed via the user's own
REM                                  DevTools Network tab: no /slice request
REM                                  present at all until an interaction
REM                                  (style click, slider drag, Preview
REM                                  button) fired one manually. Not a
REM                                  cold-start issue -- the give-up-timeout
REM                                  fix from the previous push is unrelated
REM                                  but still shipped and still good.

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
git commit -m "Fix riser-pad: add missing boot-time runPreview(true) call so the initial preview actually loads on page open"
git push origin main

pause
