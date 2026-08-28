@echo off
cd /d "%~dp0"

REM Conversation-driven push. Update the commit message each run to match what
REM this session is shipping; the comment below records the intended changeset.
REM (For ad-hoc solo pushes outside a conversation, use Manual push.bat.)
REM
REM Shipping this run (loading-overlay message cohesion, staged since
REM session 33-34, plus the logo-asset export capability built session 36):
REM   - Tools/shared.css   .loading-msg is the single source of truth
REM                        (0.7rem -> 0.95rem). .loading-ring is now a 96px
REM                        flex-sized mount for the real animated brand mark
REM                        (LOGO-ASSET-marker block: baked .lm-slant /
REM                        .lm-wobble / .lm-gear rules + keyframes), replacing
REM                        the old plain 44px spinner.
REM   - Tools/shared.js    LOGO_MARK_SVG (LOGO-ASSET-marker block) + 
REM                        injectLoaderMark(), called from autoInit(), swaps
REM                        the real mark into every .loading-ring on load.
REM   - Tools/pivot-cup/index.html, Tools/riser-pad/index.html
REM                        local .loading-overlay/.loading-ring/.loading-msg
REM                        override drift removed; both now use shared.css's
REM                        single definition and the real animated mark.
REM   - Tools/logo/index.html   the Logo Animation Lab itself: new
REM                        LogoAsset reducer/baker/emitter, PRESETS
REM                        (hero/loader), export preview panel (renders the
REM                        emitted string, not a live-SVG approximation),
REM                        Vars/Literal color-mode toggle, Export Ship JSON.
REM                        Shipped design: colorMode "literal", visible
REM                        border, eye-tuned gear/wobble timing -- see
REM                        Logo Animation/STLPreviewPageLoadingLogo.json for
REM                        the exact params (round-trips into a Lab preset).
REM   Full detail: Logo Animation/Logo_Animation.md, SESSION_LOG.md session 36.

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
git commit -m "Ship animated logo-mark loading overlay (Logo Asset Lab export capability) + unify loading message text/size"
git push origin main

pause
