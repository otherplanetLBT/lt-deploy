@echo off
cd /d "%~dp0"

REM Conversation-driven push. Update the commit message each run to match what
REM this session is shipping; the comment below records the intended changeset.
REM (For ad-hoc solo pushes outside a conversation, use Manual push.bat.)
REM
REM Shipping this run -- session 41:
REM
REM   1. Download STL now generates on demand, and can no longer ship a
REM      mislabelled file.  BOTH generators.
REM      Download served state.stlBlob (the mesh from the last successful
REM      preview) but built the filename from the CURRENT slider values at
REM      click time.  Slider changes only called recompute() -- they never
REM      dropped the blob or re-previewed -- so dragging a slider after a
REM      preview and hitting Download handed over the OLD mesh under a NEW
REM      name, with the viewport showing the same stale geometry so nothing
REM      on screen contradicted it.  Confirmed byte-exact: a file named
REM      pivot_hemi_pd5.7_pl6.9_sd12.1_sdep15.2.stl rebuilt bit-for-bit from
REM      hemi pd12.5 pl12.2 sd16.1 sdep27.0 -- a different cup, 14.8 mm
REM      ceiling vs the 8.3 mm the name implies.
REM      Fix: the blob is keyed to the parameters it was built from
REM      (previewKey()); syncDownloadState() -- called at the end of
REM      recompute() and after a preview lands -- drops it the moment they
REM      diverge.  Covers slider drag, typed value, click-to-promote, mode
REM      switch, and a request resolving after the controls moved
REM      (runPreview snapshots its key BEFORE awaiting).
REM      Rather than greying the button out, downloadSTL() fetches a mesh
REM      itself when the held one doesn't match -- "Generating..." + spinner
REM      on the button, then saves.  runPreview() now returns a success
REM      boolean so the download can wait on it and stay silent on failure,
REM      and re-checks previewKey() after the await so controls moved
REM      mid-flight can't ship a mislabelled file.  downloadBusy blocks
REM      double-clicks.  Call sites use invalidateMesh() instead of
REM      disabling the button by hand (which would strand it now that
REM      Download is the regenerator).  Riser pad has no state.valid -- its
REM      soft-clamp leaves every height/angle pair buildable -- so its
REM      button is unconditionally live.
REM
REM   2. Pivot cup: hemisphere minimum ceiling was ~3x thicker than needed.
REM      Hemi's only ceiling-side rule was pivot_l < socket_depth - sd/2
REM      ("the dome cannot overlap the cavity").  That forced the cavity roof
REM      below the dome's EQUATOR PLANE, pinning the minimum ceiling to
REM      r_outer -- 6.1 mm on a 12.1 mm cup, unrelated to MIN_CEILING_MM, and
REM      the Ceiling stat could never approach its own limit.  It measured
REM      the wrong thing: the cavity roof is not a disc of radius r_outer,
REM      the 40 deg overhang blend narrows it to a flat of ~0.364*r_inner.
REM      Replaced with the same centre-line rule the other cup modes use --
REM      socket_depth - pivot_l >= MIN_CEILING_MM, now 'modes': CUP_MODES --
REM      so all three modes share one rule and the stat matches the
REM      constraint exactly.  Full-grid sweep vs the old rule: 0 regressions
REM      in any mode, ~220k hemi combinations unlocked, all three modes floor
REM      at exactly 2.000 mm.  On pd5.7/sd12.1/sdep15.2 the floor goes
REM      6.10 mm -> 2.00 mm.
REM      Hemi keeps ONE extra rule of its own, _hemi_bore_wall: once the
REM      cavity rises past the dome equator the outer surface curves inward
REM      and the flat (sd-pd)/2 wall rule stops describing the real wall
REM      beside the bore.  No other cup mode has that failure.  In the UI it
REM      is one closed-form bound in plRange/sdepRange:
REM        pivot_l <= (socket_depth - r_outer) + hemiHeadroom(pd, sd)
REM        hemiHeadroom = r_inner + sqrt((r_outer - MIN_WALL)^2 - r_inner^2)
REM      Verified equivalent to the Python validator over 6000 configs.
REM      Also: hemi no longer caps Socket Diameter from above at all -- a
REM      wider dome is a FLATTER dome, so it only adds material over the
REM      roof.  The old sd <= 2*(sdep-pl) cap was wrong in sign.
REM      NOT changed, deliberately: Pointed's cone is truncated to a
REM      MIN_TIP_R flat tip, so socket_depth - pivot_l reads 0.72-1.58 mm
REM      high there.  That is intended -- baseplate socket castings are flat
REM      at the bottom and calipers have a flat depth rod, so the truncated
REM      figure matches what users measure, and slicer tests at the extremes
REM      confirm 2.0 mm already carries the margin.
REM
REM   3. Pivot cup: hemisphere sliders stopped where the other styles didn't.
REM      Regression introduced while building (2) and caught in testing.  The
REM      bore-wall rule was ALSO bisected against pivot/socket diameter,
REM      which was redundant (the bound above already covers it) and could
REM      only report "unsatisfiable" by inverting a range -- and an inverted
REM      range is what othersInverted() reads as "brackets would cross",
REM      which physically stops the drag.  So hemi hard-stopped socket depth
REM      at 19.2 mm where pointed/flat kept going to 8.30 on the same
REM      numbers.  Both bisections removed.  All four modes now stop at the
REM      same place, sdep = pd/2 + EPS + MIN_CEILING, which is the real
REM      bracket-crossing point.  Sliders stop only when brackets would
REM      actually cross; every other constraint yields.
REM
REM   Files: Render/generators/pivot_cup.py, Tools/pivot-cup/index.html,
REM          Tools/riser-pad/index.html, Tools/shared.css (.spinner-ghost --
REM          the base .spinner is navy-on-green for the primary button and
REM          would be invisible on the transparent secondary one).
REM
REM Verification: full-grid constraint sweep (1.09M hemi combinations, 0
REM regressions); JS/Python parity over 6000 configs; 120k simulated drag
REM walks from the page defaults with 0 invalid configs on pure hemi
REM dragging; jsdom click-through of both pages (16 download assertions each,
REM all passing).

REM ---------------------------------------------------------------------------
REM Standing note (not per-session): the automatic glossary.db copy step was
REM removed 2026-08-28 by operator decision -- the glossary DB doesn't change
REM often enough to justify re-copying it on every push, so the committed
REM Render/glossary.db stays whatever was last checked in until refreshed on
REM purpose. To refresh it manually before a push, run from deploy\:
REM   copy /Y "..\..\The Ultimate Longboard Wiki Project\Wiki\Glossary\glossary.db" "Render\glossary.db"
REM ---------------------------------------------------------------------------

git add -A
git status
git commit -m "Pivot cup: replace hemi dome-clearance rule with the shared ceiling rule; Download STL generates on demand instead of greying out"
git push origin main

pause
