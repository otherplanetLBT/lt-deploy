@echo off
cd /d "%~dp0"

REM Conversation-driven push. Update the commit message each run to match what
REM this session is shipping; the comment below records the intended changeset.
REM (For ad-hoc solo pushes outside a conversation, use Manual push.bat.)
REM
REM Shipping this run -- TWO changesets landed unstaged together:
REM
REM   1) Riser pad: template attribution + library popout (session 38).
REM      * Attribution rides in the master STL's filename as bracketed suffix
REM        fields, e.g. "Skoa Vapor 26 [Template by X] [printables.com+@X].stl".
REM        parse_style_stem() in Render/site_app.py splits it;
REM        /api/riser-pad/library now returns {id, name, credit, link} objects
REM        instead of bare strings (id stays the raw stem, so master lookup is
REM        unchanged). Shown as a plain-text .viewport-credit pill in the
REM        preview -- site-time only, never in the download filename.
REM      * Library is now a popout built into document.body and positioned off
REM        its toggle, replacing the inline drawer that pushed the sidebar down
REM        on every open; the toggle collapses to the selected template's name.
REM      * The four test masters in Render/assets/riser-pad-stls/ are RENAMED
REM        into the new grammar with FILLER credits (Filler Contributor,
REM        example.com handles) -- git sees these as deletes + adds. Operator
REM        has okayed them going live as tests.
REM      Files: Render/site_app.py, Render/assets/riser-pad-stls/* (renames),
REM      Tools/shared.css, Tools/riser-pad/index.html.
REM      Full detail: SESSION_LOG.md session 38.
REM
REM   2) Favicon random orientation (session 39): favicon-2/3/4.svg + .ico added
REM      to both Landing/ and Tools/ (favicon.svg/.ico from session 37 is
REM      variant 1); a small inline script on all 5 pages + the Lab source picks
REM      one at random and persists it via sessionStorage for the rest of that
REM      tab's session (revised same day from every-page-load, which flickered
REM      visibly on navigation). apple-touch-icon.png untouched (stays static).
REM      Full detail: SESSION_LOG.md session 39.
REM
REM The project root moved off Google Drive to D:\Projects\Website Generators
REM (session 38). The glossary.db copy step below was flagged as unverified
REM against the new root -- VERIFIED 2026-08-28 and correct: from deploy\,
REM ..\..\ resolves to D:\Projects\, and the Wiki project sits at
REM D:\Projects\The Ultimate Longboard Wiki Project\Wiki\Glossary\glossary.db.
REM No change needed.

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
git commit -m "Riser pad: filename-based template attribution + library popout; random favicon orientation per session"
git push origin main

pause
