@echo off
cd /d "%~dp0"

REM Conversation-driven push. Update the commit message each run to match what
REM this session is shipping; the comment below records the intended changeset.
REM (For ad-hoc solo pushes outside a conversation, use Manual push.bat.)
REM
REM Shipping this run (cold-start UX fixes, pivot-cup + riser-pad):
REM   - Tools/pivot-cup/index.html   cold-start hint now latency-triggered (any
REM                                  request, not just first-ever), overlay
REM                                  shows on manual Preview clicks too, and a
REM                                  request-generation + AbortController guard
REM                                  so a superseded selection can't clobber a
REM                                  newer one's preview/download.
REM   - Tools/riser-pad/index.html   same three fixes, mirrored.
REM   - Tools/shared.js              fixed setLoading()'s sub-message display
REM                                  bug (was set via style.display = '' which
REM                                  falls back to the stylesheet's display:none
REM                                  -- the cold-start hint text was never
REM                                  actually visible before this).

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
git commit -m "Cold-start UX fixes: latency-triggered hint, overlay on manual clicks, fix hidden sub-message display bug, request-generation guard (pivot-cup + riser-pad)"
git push origin main

pause
