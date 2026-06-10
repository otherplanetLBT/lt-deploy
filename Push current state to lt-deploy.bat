@echo off
cd /d "%~dp0"

REM Conversation-driven push. Update the commit message each run to match what
REM this session is shipping; the comment below records the intended changeset.
REM (For ad-hoc solo pushes outside a conversation, use Manual push.bat.)
REM
REM Shipping this run (audit batch 1):
REM   - README.md                  rewrite to current 3-target architecture
REM   - Glossary/GLOSSARY_APP.md    delete retired divergent design doc
REM   - Tools/logo/index.html.bak   remove stray backup
REM   - Manual push.bat             newly tracked
REM   - Glossary/glossary_app.py    pre-existing working-tree edit, rides along

git add -A
git status
git commit -m "Audit batch 1: rewrite deploy README, drop retired glossary doc + logo .bak, track Manual push.bat"
git push origin main

pause
