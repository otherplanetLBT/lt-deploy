@echo off
cd /d "%~dp0"

REM Conversation-driven push. Update the commit message each run to match what
REM this session is shipping; the comment below records the intended changeset.
REM (For ad-hoc solo pushes outside a conversation, use Manual push.bat.)
REM
REM Shipping this run -- session 40:
REM
REM   Riser pad: fix preview 404 on attributed library templates.
REM     Session 38's template-attribution feature split each library style
REM     into a raw filename `id` (what the API needs to find the master STL)
REM     and a truncated display `name` (safe for filenames/logging). But
REM     Preview's fetch to /api/riser-pad/slice sent state.styleName (display
REM     name) instead of state.style (raw id) -- so any master with a
REM     bracketed credit suffix 404'd with "Master STL not found" the moment
REM     Preview ran, even though the library listing and selection worked
REM     fine (that endpoint never needs the raw id). Untitled masters with no
REM     brackets (Solid/Skeleton/Drop-thru, Test 3) were unaffected because
REM     their name and id are identical, which masked the bug.
REM     Fix: Tools/riser-pad/index.html line ~1096, style: state.styleName ->
REM     style: state.style. The other two state.styleName uses (download
REM     filename slug, Mission Report/log-event params) are correct as-is and
REM     untouched.
REM   Files: Tools/riser-pad/index.html.
REM
REM Removed the automatic glossary.db copy step (was: unconditional copy
REM before every push). Operator decision 2026-08-28 -- the glossary DB
REM doesn't change often enough to justify re-copying it on every push; the
REM committed Render/glossary.db just stays whatever was last checked in
REM until refreshed on purpose. To refresh it manually before a push, run
REM from deploy\:
REM   copy /Y "..\..\The Ultimate Longboard Wiki Project\Wiki\Glossary\glossary.db" "Render\glossary.db"

git add -A
git status
git commit -m "Riser pad: fix preview 404 on attributed library templates (state.styleName -> state.style)"
git push origin main

pause
