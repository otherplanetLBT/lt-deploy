/* shared.js — Longboard Technology cross-page helpers
   ─────────────────────────────────────────────────────
   Provides:
     LT.initStarfield(canvas, opts)                — starfield animation
     LT.fmt.{mmToDisplay, displayToMm,             — number/unit helpers
            formatLen, formatDeg, parseRaw}
     LT.Viewport({...})                            — Three.js scene + STL loader
     LT.SliderControl({...})                       — slider + text input + markers
     LT.UnitToggle({...})                          — mm/in switching
     LT.sessionId                                  — per-tab UUID for usage logs
     LT.logEvent({type, tool, ...})                — fire-and-forget POST to
                                                     /api/log-event

   The page owns the state and constraint resolution. SliderControl just
   renders what the page tells it to, and reports user input via callbacks.
   This keeps "drag-wins" logic in one place (the page), where the full
   constraint graph is visible. */

(function () {
  'use strict';

  const MM_PER_IN = 25.4;

  // ============================================================================
  // Logo mark (loading-overlay loader)
  // ============================================================================
  // Shipped from the Logo Animation Lab's export capability via
  // apply_logo_asset.py — see Logo Animation/Logo_Animation.md § Export
  // capability. LOGO_MARK_SVG is injected into every `.loading-ring` on
  // DOMContentLoaded (see injectLoaderMark below); the matching .lm-* CSS
  // (transforms + baked @keyframes) lives in shared.css between the same
  // markers. Re-run apply_logo_asset.py to update both together — never
  // hand-edit between the markers, it will be overwritten on the next run.
  /* LOGO-ASSET:BEGIN */
  // Shipped from Logo Animation Lab preset "loader" via apply_logo_asset.py. Re-run to update.
  const LOGO_MARK_SVG = `<svg class="lm" viewBox="0 0 540 340" width="96" height="60.44" xmlns="http://www.w3.org/2000/svg" overflow="visible">
  <g class="lm-slant"><g class="lm-wobble">
    <path class="lm-border" d="M 415.2,216.2 A 242.68,57.67 0 0 0 415.2,123.8 A 152.40,152.40 0 0 0 124.8,123.8 A 242.68,57.67 0 0 0 124.8,216.2 A 152.40,152.40 0 0 0 415.2,216.2 Z" fill="#ffffff" stroke="#ffffff" stroke-width="32" stroke-linejoin="round" stroke-linecap="round"/>
  </g></g>
  <g class="lm-slant"><g class="lm-wobble">
    <path class="lm-ring" d="M 513,170 L 435.93,170 L 433.67,176.74 L 425.07,184.57 L 410.39,191.82 L 390.2,198.22 L 336.65,207.49 L 272.74,210.94 L 208.41,208.02 L 153.64,199.19 L 132.61,192.96 L 116.97,185.82 L 107.33,178.07 L 104.07,170 L 27,170 L 28.2,175.72 L 31.77,181.38 L 45.89,192.32 L 68.8,202.38 L 99.6,211.17 L 137.09,218.34 L 172.39,222.88 L 218.17,226.42 L 265.98,227.74 L 313.95,226.79 L 360.2,223.62 L 402.91,218.34 L 440.4,211.17 L 471.2,202.38 L 494.11,192.32 L 508.23,181.38 L 511.8,175.72 L 513,170 Z" fill="#000000" stroke="#000000" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>
    <path class="lm-swoosh" d="M 415.41,123.73 L 352.86,115.72 L 343.81,100.13 L 332.6,86.02 L 321.78,75.61 L 307.25,64.95 L 291.33,56.52 L 277.24,51.31 L 259.66,47.37 L 241.69,46.02 L 223.72,47.28 L 206.11,51.14 L 189.26,57.51 L 173.5,66.25 L 159.18,77.19 L 146.6,90.08 L 136.01,104.67 L 126.5,123.4 L 124.59,123.73 L 133.78,101.23 L 146.43,80.46 L 162.22,61.97 L 180.75,46.23 L 201.54,33.62 L 224.07,24.48 L 243.76,19.68 L 267.97,17.42 L 292.23,19.03 L 315.93,24.48 L 338.46,33.62 L 359.25,46.23 L 377.78,61.97 L 393.57,80.46 L 406.22,101.23 L 415.41,123.73 Z" fill="#000000" stroke="#000000" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>
    <path class="lm-swoosh" d="M 124.59,216.26 L 133.78,238.77 L 146.43,259.54 L 162.22,278.03 L 180.75,293.77 L 201.54,306.38 L 224.07,315.52 L 243.76,320.32 L 267.97,322.58 L 292.23,320.97 L 315.93,315.52 L 338.46,306.38 L 359.25,293.77 L 377.78,278.03 L 393.57,259.54 L 406.22,238.77 L 415.41,216.26 L 413.5,216.6 L 403.99,235.34 L 393.4,249.92 L 380.82,262.81 L 366.5,273.75 L 350.74,282.49 L 333.89,288.86 L 316.29,292.72 L 298.31,293.98 L 280.34,292.63 L 262.76,288.69 L 248.67,283.48 L 232.75,275.05 L 218.22,264.39 L 207.4,253.98 L 196.19,239.87 L 187.14,224.28 L 124.59,216.26 Z" fill="#000000" stroke="#000000" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>
  </g></g>
  <g class="lm-gear">
    <path class="lm-gear-fill" d="M 212.96,290.19 L 230.31,268.16 L 254.03,274.67 L 280.25,275.38 L 290.65,301.42 L 345.56,279.49 L 335.17,253.45 L 353.68,234.87 L 366.39,213.81 L 394.14,217.82 L 402.6,159.3 L 374.86,155.29 L 368.02,129.97 L 356.14,108.43 L 373.49,86.4 L 327.04,49.81 L 309.69,71.84 L 285.97,65.33 L 259.75,64.62 L 249.35,38.58 L 194.44,60.51 L 204.83,86.55 L 186.32,105.13 L 173.61,126.19 L 145.86,122.17 L 137.4,180.7 L 165.15,184.71 L 171.98,210.03 L 183.86,231.57 L 166.51,253.6 Z" fill="#ffffff"/>
    <path class="lm-gear-body" d="M 226.88,254.02 L 211.05,274.11 L 182.58,251.69 L 198.41,231.59 L 189,218.55 L 181.93,204.09 L 177.84,190.61 L 175.68,174.67 L 150.36,171.01 L 155.55,135.14 L 180.87,138.8 L 186.5,125.89 L 195.2,112.36 L 206.07,100.49 L 218.8,90.65 L 209.31,66.89 L 242.97,53.45 L 252.45,77.21 L 268.46,75.58 L 282.52,76.4 L 298.23,79.88 L 313.12,85.98 L 328.95,65.89 L 357.42,88.31 L 341.59,108.41 L 351,121.45 L 358.07,135.91 L 362.16,149.39 L 364.32,165.33 L 389.64,168.99 L 384.45,204.86 L 359.13,201.2 L 353.5,214.11 L 344.8,227.64 L 333.93,239.51 L 321.2,249.35 L 330.69,273.11 L 297.04,286.55 L 287.55,262.79 L 271.54,264.43 L 257.48,263.6 L 241.77,260.12 L 226.88,254.02 Z M 212.96,290.19 L 230.31,268.16 L 254.03,274.67 L 280.25,275.38 L 290.65,301.42 L 345.56,279.49 L 335.17,253.45 L 353.68,234.87 L 366.39,213.81 L 394.14,217.82 L 402.6,159.3 L 374.86,155.29 L 368.02,129.97 L 356.14,108.43 L 373.49,86.4 L 327.04,49.81 L 309.69,71.84 L 285.97,65.33 L 259.75,64.62 L 249.35,38.58 L 194.44,60.51 L 204.83,86.55 L 186.32,105.13 L 173.61,126.19 L 145.86,122.17 L 137.4,180.7 L 165.15,184.71 L 171.98,210.03 L 183.86,231.57 L 166.51,253.6 Z" fill-rule="evenodd" fill="#000000" stroke="#000000" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>
  </g>
  <g class="lm-slant"><g class="lm-wobble">
    <path class="lm-ring" d="M 435.93,170 L 513,170 L 511.8,164.28 L 508.23,158.62 L 494.11,147.68 L 471.2,137.62 L 440.4,128.83 L 402.91,121.66 L 367.61,117.12 L 321.83,113.58 L 274.02,112.26 L 226.05,113.21 L 179.8,116.38 L 137.09,121.66 L 99.6,128.83 L 68.8,137.62 L 45.89,147.68 L 31.77,158.62 L 28.2,164.28 L 27,170 L 104.07,170 L 106.33,163.26 L 114.93,155.43 L 129.61,148.18 L 149.8,141.78 L 203.35,132.51 L 267.26,129.06 L 331.59,131.98 L 386.36,140.81 L 407.39,147.04 L 423.04,154.18 L 432.67,161.93 L 435.93,170 Z" fill="#000000" stroke="#000000" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>
  </g></g>
</svg>`;
  /* LOGO-ASSET:END */

  function injectLoaderMark() {
    if (!LOGO_MARK_SVG) return;
    document.querySelectorAll('.loading-ring').forEach(el => {
      el.innerHTML = LOGO_MARK_SVG;
    });
  }


  // ============================================================================
  // Starfield
  // ============================================================================
  // Static cosmos: stars are placed once, then breathe via a sinusoidal alpha
  // envelope. Drawn as circles with varying radius — feels like a night sky,
  // not snow. Match the original Landing page's character. `speed` is kept as
  // a knob in case a future caller wants drifting stars; default 0 = static.
  function initStarfield(canvas, opts) {
    opts = opts || {};
    // Defaults match the original Landing page math (Initial Documents/index.html):
    // density 1/6000 ≈ 0.000167, full-alpha twinkle, radius 0.2..1.6 px.
    // No devicePixelRatio scaling — keeps the look identical on Retina vs LowDPI
    // and avoids the soft-edge artefacts that came from drawing into a 2× bitmap.
    const density   = opts.density   != null ? opts.density   : 0.000167;
    const speed     = opts.speed     != null ? opts.speed     : 0;
    const baseAlpha = opts.baseAlpha != null ? opts.baseAlpha : 1.0;
    const minR      = opts.minR      != null ? opts.minR      : 0.2;
    const maxR      = opts.maxR      != null ? opts.maxR      : 1.6;
    const ctx = canvas.getContext('2d');
    let w = 0, h = 0, stars = [];

    function init() {
      // getBoundingClientRect() returns the layout-computed size in CSS pixels.
      // Reliable both for full-viewport canvases (CSS inset:0 → viewport size)
      // and for canvases inside constrained containers like the nav strip.
      const rect = canvas.getBoundingClientRect();
      const cssW = Math.max(1, Math.floor(rect.width));
      const cssH = Math.max(1, Math.floor(rect.height));
      // Avoid pointless re-seeding on identical-size resize events.
      if (canvas.width === cssW && canvas.height === cssH && stars.length) return;
      w = canvas.width  = cssW;
      h = canvas.height = cssH;
      const n = Math.floor(w * h * density);
      stars = [];
      for (let i = 0; i < n; i++) {
        stars.push({
          x:     Math.random() * w,
          y:     Math.random() * h,
          r:     minR + Math.random() * (maxR - minR),
          a:     Math.random(),                  // per-star peak alpha 0..1 (matches original)
          tw:    0.001 + Math.random() * 0.004,  // per-star twinkle frequency
          phase: Math.random() * Math.PI * 2,
        });
      }
    }

    function frame(t) {
      ctx.clearRect(0, 0, w, h);
      for (const s of stars) {
        if (speed) {
          s.y += speed;
          if (s.y > h) { s.y = 0; s.x = Math.random() * w; }
        }
        // Breathing envelope: 0.5 + 0.5 sin → range 0..1, full-dynamic twinkle.
        const env = 0.5 + 0.5 * Math.sin(t * s.tw + s.phase);
        ctx.globalAlpha = baseAlpha * s.a * env;
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
        ctx.fillStyle = '#ffffff';
        ctx.fill();
      }
      ctx.globalAlpha = 1;
      requestAnimationFrame(frame);
    }

    // ResizeObserver fires once on first observation (catching the initial
    // layout regardless of when init runs) and on every subsequent size
    // change. Cleaner than DOMContentLoaded + window.resize, which races the
    // initial paint and can leave stars seeded into a 1×1 coord space.
    if (window.ResizeObserver) {
      new ResizeObserver(init).observe(canvas);
    } else {
      window.addEventListener('resize', init);
      init();
    }
    requestAnimationFrame(frame);
  }

  // Last-interacted slider gets an `.active` class — pages style it to stay
  // slightly larger than its peers so the eye can track which control was
  // most recently engaged. Promotion fires on any of:
  //   - drag (input event on the range)
  //   - click without movement (pointerdown on the range)
  //   - focus on the paired text input (focusin on .value-input)
  // Pure hover does NOT promote — hover has its own scale transition and we
  // don't want passing the mouse over a slider to repaint others.
  function promoteRange(range) {
    if (!range) return;
    document.querySelectorAll('input[type=range].active').forEach(s => {
      if (s !== range) s.classList.remove('active');
    });
    range.classList.add('active');
  }
  document.addEventListener('input', (e) => {
    const t = e.target;
    if (t && t.matches && t.matches('input[type=range]')) promoteRange(t);
  });
  // pointerdown covers mouse + touch + pen. Click-to-promote is the user-
  // visible "I picked this slider" cue, even before they actually move it.
  document.addEventListener('pointerdown', (e) => {
    const t = e.target;
    if (t && t.matches && t.matches('input[type=range]')) promoteRange(t);
  });
  document.addEventListener('focusin', (e) => {
    const t = e.target;
    // Promote the sibling range when its paired text input gets focus —
    // the text field lives inside the same .control-row as the slider.
    if (t && t.matches && t.matches('.value-input')) {
      const row = t.closest('.control-row');
      if (row) promoteRange(row.querySelector('input[type=range]'));
    }
  });

  document.addEventListener('DOMContentLoaded', () => {
    // Full-viewport starfield (landing page background) — original Landing-page
    // intensity: density 1/6000, full-alpha twinkle, default radius range.
    document.querySelectorAll('canvas.starfield').forEach(c => {
      initStarfield(c);   // all defaults
    });
    // Constrained nav-strip starfield (top banner on tool pages + landing) —
    // higher per-pixel density since the strip is small, slight alpha pullback
    // so stars don't compete with the logo and links for attention.
    document.querySelectorAll('canvas.starfield-nav').forEach(c => {
      initStarfield(c, {
        density:   0.00060,
        baseAlpha: 0.85,
        minR:      0.3,
        maxR:      1.2,
      });
    });
  });

  // ============================================================================
  // Format helpers
  // ============================================================================
  const fmt = {
    mmToDisplay(mm, unit) {
      return unit === 'in' ? mm / MM_PER_IN : mm;
    },
    displayToMm(val, unit) {
      return unit === 'in' ? val * MM_PER_IN : val;
    },
    formatLen(mm, unit, dpMM, dpIN) {
      const dp = unit === 'in' ? (dpIN == null ? 3 : dpIN)
                               : (dpMM == null ? 1 : dpMM);
      const v  = fmt.mmToDisplay(mm, unit);
      return v.toFixed(dp) + ' ' + (unit === 'in' ? 'in' : 'mm');
    },
    formatDeg(deg, dp) {
      return deg.toFixed(dp == null ? 1 : dp) + '°';
    },
    parseRaw(str) {
      const cleaned = String(str).replace(/[^\d.\-]/g, '');
      if (cleaned === '' || cleaned === '-' || cleaned === '.') return NaN;
      return parseFloat(cleaned);
    },
  };

  // ============================================================================
  // SliderControl — slider + text input + min/max markers + clamp label
  // ============================================================================
  function SliderControl(opts) {
    const slider     = opts.slider;
    const valueInput = opts.valueInput;
    const minMarker  = opts.minMarker  || null;
    const maxMarker  = opts.maxMarker  || null;
    const clampLabel = opts.clampLabel || null;

    const sliderMinMM = opts.sliderMinMM;
    const sliderMaxMM = opts.sliderMaxMM;
    const stepMM      = opts.stepMM;
    const textMinMM   = opts.textMinMM == null ? sliderMinMM : opts.textMinMM;
    const textMaxMM   = opts.textMaxMM == null ? sliderMaxMM : opts.textMaxMM;

    const isAngle      = opts.isAngle === true;
    const decimalsMM   = opts.decimalsMM    == null ? 1 : opts.decimalsMM;
    const decimalsIN   = opts.decimalsIN    == null ? 3 : opts.decimalsIN;
    const decimalsDeg  = opts.decimalsAngle == null ? 1 : opts.decimalsAngle;

    const onInput        = opts.onInput        || function () {};
    const clampLabelText = opts.clampLabelText || {
      min:      'Min applied',
      max:      'Max applied',
      extended: 'Extended',
    };

    let storedMM = opts.initialMM == null ? sliderMinMM : opts.initialMM;
    let unit     = isAngle ? 'deg' : (opts.unit || 'mm');

    let lastView = {
      effMM:        storedMM,
      minBoundMM:   null,
      maxBoundMM:   null,
      clampReason:  null,
    };

    function valToMM(val) {
      if (isAngle) return val;
      return unit === 'in' ? val * MM_PER_IN : val;
    }
    function mmToVal(mm) {
      if (isAngle) return mm;
      return unit === 'in' ? mm / MM_PER_IN : mm;
    }
    function formatMM(mm) {
      if (isAngle) return fmt.formatDeg(mm, decimalsDeg);
      return fmt.formatLen(mm, unit, decimalsMM, decimalsIN);
    }

    function syncSliderRange() {
      if (isAngle) {
        slider.min  = sliderMinMM;
        slider.max  = sliderMaxMM;
        slider.step = stepMM;
      } else if (unit === 'in') {
        slider.min  = (sliderMinMM / MM_PER_IN).toFixed(4);
        slider.max  = (sliderMaxMM / MM_PER_IN).toFixed(4);
        slider.step = (stepMM      / MM_PER_IN).toFixed(5);
      } else {
        slider.min  = sliderMinMM;
        slider.max  = sliderMaxMM;
        slider.step = stepMM;
      }
    }

    function render() {
      const thumbMM = Math.max(sliderMinMM, Math.min(sliderMaxMM, storedMM));
      slider.value = mmToVal(thumbMM).toFixed(4);

      if (document.activeElement !== valueInput) {
        valueInput.value = formatMM(lastView.effMM);
      }

      function pctOf(mm) {
        return (mm - sliderMinMM) / (sliderMaxMM - sliderMinMM) * 100;
      }

      function placeMarker(el, mm) {
        if (!el) return;
        if (mm == null) { el.classList.remove('visible'); return; }
        if (mm <= sliderMinMM || mm >= sliderMaxMM) {
          el.classList.remove('visible'); return;
        }
        el.style.left = pctOf(mm) + '%';
        el.classList.add('visible');
      }
      placeMarker(minMarker, lastView.minBoundMM);
      placeMarker(maxMarker, lastView.maxBoundMM);

      // Track clamp percentages — pages use these CSS vars to shade portions of
      // the track that sit outside the active min/max bounds. A bound that's
      // off-slider contributes 0%/100% (i.e. that side is unrestricted within
      // the visible track).
      const minPct = (lastView.minBoundMM != null
                      && lastView.minBoundMM > sliderMinMM
                      && lastView.minBoundMM < sliderMaxMM)
                      ? pctOf(lastView.minBoundMM) : 0;
      const maxPct = (lastView.maxBoundMM != null
                      && lastView.maxBoundMM > sliderMinMM
                      && lastView.maxBoundMM < sliderMaxMM)
                      ? pctOf(lastView.maxBoundMM) : 100;
      slider.style.setProperty('--clamp-min-pct', minPct + '%');
      slider.style.setProperty('--clamp-max-pct', maxPct + '%');

      // Clamped state — thumb sits at a constraint boundary (the user's stored
      // intent is being pinned by an active soft-clamp). 'extended' (typed past
      // slider range) is a different signal and does NOT toggle this class.
      const isClamped = lastView.clampReason === 'min' || lastView.clampReason === 'max';
      slider.classList.toggle('clamped', isClamped);

      if (clampLabel) {
        if (lastView.clampReason && clampLabelText[lastView.clampReason]) {
          clampLabel.textContent = clampLabelText[lastView.clampReason];
          clampLabel.classList.add('visible');
        } else {
          clampLabel.classList.remove('visible');
        }
      }
    }

    function applyEffective(view) {
      lastView = {
        effMM:       view.effMM        == null ? storedMM : view.effMM,
        minBoundMM:  view.minBoundMM   == null ? null     : view.minBoundMM,
        maxBoundMM:  view.maxBoundMM   == null ? null     : view.maxBoundMM,
        clampReason: view.clampReason  == null ? null     : view.clampReason,
      };
      render();
    }

    function setStoredMM(mm, fireEvent) {
      storedMM = mm;
      render();
      if (fireEvent) onInput(storedMM, 'set');
    }

    function getStoredMM() { return storedMM; }
    function getUnit()     { return unit; }
    function isFocused()   { return document.activeElement === valueInput; }

    function setUnit(newUnit) {
      if (isAngle) return;
      if (newUnit === unit) return;
      unit = newUnit;
      syncSliderRange();
      render();
    }

    syncSliderRange();
    render();

    slider.addEventListener('input', function () {
      const val = parseFloat(slider.value);
      if (isNaN(val)) return;
      storedMM = valToMM(val);
      storedMM = Math.max(sliderMinMM, Math.min(sliderMaxMM, storedMM));
      onInput(storedMM, 'drag');
    });

    valueInput.addEventListener('focus', function () {
      if (isAngle) {
        valueInput.value = lastView.effMM.toFixed(decimalsDeg);
      } else {
        const v = fmt.mmToDisplay(lastView.effMM, unit);
        valueInput.value = v.toFixed(unit === 'in' ? decimalsIN : decimalsMM);
      }
      valueInput.select();
    });

    valueInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter')  { valueInput.blur(); }
      if (e.key === 'Escape') {
        valueInput.value = formatMM(lastView.effMM);
        valueInput.blur();
      }
    });

    valueInput.addEventListener('blur', function () {
      const raw = fmt.parseRaw(valueInput.value);
      if (isNaN(raw)) {
        valueInput.value = formatMM(lastView.effMM);
        return;
      }
      const typedMM = isAngle ? raw : fmt.displayToMm(raw, unit);
      storedMM = Math.max(textMinMM, Math.min(textMaxMM, typedMM));
      onInput(storedMM, 'type');
    });

    return {
      slider, valueInput, minMarker, maxMarker, clampLabel,
      sliderMinMM, sliderMaxMM, stepMM, textMinMM, textMaxMM,
      isAngle,
      applyEffective,
      setStoredMM,
      getStoredMM,
      getUnit,
      setUnit,
      isFocused,
      el: slider,
    };
  }

  // ============================================================================
  // UnitToggle — mm/in
  // ============================================================================
  function UnitToggle(opts) {
    const mmBtn = opts.mmButton;
    const inBtn = opts.inButton;
    const onChange = opts.onChange || function () {};
    let unit = opts.initial || 'mm';

    function setActive(u) {
      if (u === 'mm') { mmBtn.classList.add('active'); inBtn.classList.remove('active'); }
      else            { inBtn.classList.add('active'); mmBtn.classList.remove('active'); }
    }
    setActive(unit);

    mmBtn.addEventListener('click', () => {
      if (unit === 'mm') return;
      unit = 'mm'; setActive(unit); onChange(unit);
    });
    inBtn.addEventListener('click', () => {
      if (unit === 'in') return;
      unit = 'in'; setActive(unit); onChange(unit);
    });

    return {
      get unit() { return unit; },
      set: function (u) {
        if (u === unit) return;
        unit = u; setActive(unit); onChange(unit);
      },
    };
  }

  // ============================================================================
  // Viewport — Three.js scene with orbit/pan/zoom + STL loader
  // ============================================================================
  function Viewport(opts) {
    const canvas         = opts.canvas;
    const bgColor        = opts.bgColor        != null ? opts.bgColor        : 0x0a0c14;
    const meshColor      = opts.meshColor      != null ? opts.meshColor      : 0xb8a060;
    const loadingOverlay = opts.loadingOverlay || null;
    const loadingMsg     = opts.loadingMsg     || null;
    const viewportStatus = opts.viewportStatus || null;
    const customizeMesh  = opts.customizeMesh  || null;
    const initial        = opts.initialSpherical || { theta: Math.PI/4, phi: Math.PI/3, radius: 200 };

    if (!window.THREE) {
      throw new Error('LT.Viewport: THREE.js must be loaded before constructing a Viewport.');
    }

    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(bgColor);
    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 2000);

    scene.add(new THREE.AmbientLight(0xffffff, 0.4));
    const dA = new THREE.DirectionalLight(0xffffff, 0.85); dA.position.set(100,150,100); scene.add(dA);
    const dB = new THREE.DirectionalLight(0x8ab4f8, 0.3);  dB.position.set(-100,50,-80); scene.add(dB);
    scene.add(new THREE.GridHelper(200, 20, 0x2e3350, 0x1a1d27));

    let mesh = null;
    let sph  = { theta: initial.theta, phi: initial.phi, radius: initial.radius };
    let pan  = new THREE.Vector3();

    function resize() {
      const p = canvas.parentElement;
      renderer.setSize(p.clientWidth, p.clientHeight, false);
      camera.aspect = p.clientWidth / p.clientHeight;
      camera.updateProjectionMatrix();
    }
    resize();
    window.addEventListener('resize', resize);

    function updateCam() {
      const { theta, phi, radius } = sph;
      camera.position.set(
        pan.x + radius * Math.sin(phi) * Math.sin(theta),
        pan.y + radius * Math.cos(phi),
        pan.z + radius * Math.sin(phi) * Math.cos(theta)
      );
      camera.lookAt(pan.x, pan.y, pan.z);
    }
    updateCam();

    let drag = false, rDrag = false, lx = 0, ly = 0;
    canvas.addEventListener('mousedown', e => {
      drag = true; rDrag = e.button === 2; lx = e.clientX; ly = e.clientY; e.preventDefault();
    });
    canvas.addEventListener('contextmenu', e => e.preventDefault());
    window.addEventListener('mouseup', () => { drag = false; });
    window.addEventListener('mousemove', e => {
      if (!drag) return;
      const dx = e.clientX - lx, dy = e.clientY - ly; lx = e.clientX; ly = e.clientY;
      if (rDrag) {
        const r = new THREE.Vector3();
        r.crossVectors(camera.getWorldDirection(new THREE.Vector3()), new THREE.Vector3(0,1,0)).normalize();
        pan.addScaledVector(r, -dx * 0.15);
        pan.addScaledVector(new THREE.Vector3(0,1,0), dy * 0.15);
      } else {
        sph.theta -= dx * 0.005;
        sph.phi   = Math.max(0.05, Math.min(Math.PI - 0.05, sph.phi + dy * 0.005));
      }
      updateCam();
    });
    canvas.addEventListener('wheel', e => {
      sph.radius = Math.max(20, Math.min(600, sph.radius + e.deltaY * 0.3));
      updateCam(); e.preventDefault();
    }, { passive: false });

    let lastPinch = null, t0x = 0, t0y = 0;
    canvas.addEventListener('touchstart', e => {
      e.preventDefault();
      if (e.touches.length === 1) { t0x = e.touches[0].clientX; t0y = e.touches[0].clientY; }
      if (e.touches.length === 2) {
        const dx = e.touches[0].clientX - e.touches[1].clientX,
              dy = e.touches[0].clientY - e.touches[1].clientY;
        lastPinch = Math.sqrt(dx*dx + dy*dy);
      }
    }, { passive: false });
    canvas.addEventListener('touchmove', e => {
      e.preventDefault();
      if (e.touches.length === 1) {
        const dx = e.touches[0].clientX - t0x, dy = e.touches[0].clientY - t0y;
        t0x = e.touches[0].clientX; t0y = e.touches[0].clientY;
        sph.theta -= dx * 0.005;
        sph.phi   = Math.max(0.05, Math.min(Math.PI - 0.05, sph.phi + dy * 0.005));
        updateCam();
      } else if (e.touches.length === 2) {
        const dx = e.touches[0].clientX - e.touches[1].clientX,
              dy = e.touches[0].clientY - e.touches[1].clientY;
        const dist = Math.sqrt(dx*dx + dy*dy);
        if (lastPinch) { sph.radius = Math.max(20, Math.min(600, sph.radius - (dist - lastPinch) * 0.5)); updateCam(); }
        lastPinch = dist;
      }
    }, { passive: false });
    canvas.addEventListener('touchend', e => { if (e.touches.length < 2) lastPinch = null; });

    (function loop() { requestAnimationFrame(loop); renderer.render(scene, camera); })();

    function parseSTL(buf) {
      const v = new DataView(buf), n = v.getUint32(80, true);
      const pos = new Float32Array(n * 9), nrm = new Float32Array(n * 9);
      let o = 84;
      for (let i = 0; i < n; i++) {
        const nx = v.getFloat32(o, true), ny = v.getFloat32(o + 4, true), nz = v.getFloat32(o + 8, true); o += 12;
        for (let j = 0; j < 3; j++) {
          const b = i * 9 + j * 3;
          pos[b]   = v.getFloat32(o,     true);
          pos[b+1] = v.getFloat32(o + 4, true);
          pos[b+2] = v.getFloat32(o + 8, true);
          nrm[b] = nx; nrm[b+1] = ny; nrm[b+2] = nz; o += 12;
        }
        o += 2;
      }
      return { pos, nrm, count: n };
    }

    function loadSTL(buf) {
      if (mesh) { scene.remove(mesh); mesh.geometry.dispose(); mesh.material.dispose(); mesh = null; }
      const { pos, nrm, count } = parseSTL(buf);
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
      geo.setAttribute('normal',   new THREE.BufferAttribute(nrm, 3));

      const mat = new THREE.MeshPhongMaterial({
        color: meshColor, specular: 0x333333, shininess: 30, side: THREE.DoubleSide
      });
      mesh = new THREE.Mesh(geo, mat);

      geo.applyMatrix4(new THREE.Matrix4().makeRotationX(-Math.PI / 2));
      geo.computeBoundingBox();
      const b = geo.boundingBox;
      geo.translate(-(b.min.x + b.max.x) / 2, -b.min.y, -(b.min.z + b.max.z) / 2);
      geo.computeBoundingBox();

      if (typeof customizeMesh === 'function') customizeMesh(mesh, geo);

      scene.add(mesh);

      const bb   = geo.boundingBox;
      const size = Math.max(bb.max.x - bb.min.x, bb.max.y - bb.min.y, bb.max.z - bb.min.z);
      sph.radius = size * 2.4;
      pan.set(0, (bb.max.y + bb.min.y) / 2, 0);
      updateCam();

      if (viewportStatus) {
        viewportStatus.textContent = count.toLocaleString() + ' triangles';
        viewportStatus.style.display = '';
      }
      return count;
    }

    // Toggle the viewport's loading overlay.
    //   on:     boolean — show/hide the overlay
    //   msg:    string  — primary message (e.g. "Building mesh…"). Skipped if falsy.
    //   submsg: string  — optional secondary line below the primary message. Used
    //                     for cold-start hints on the first preview after page
    //                     load. Pass '' (empty string) to clear; pass undefined
    //                     to leave whatever's there (so toggling off doesn't
    //                     wipe the text mid-fade-out). The sub element is
    //                     resolved lazily — pages can add `id="loading-sub"`
    //                     inside the overlay markup to enable.
    function setLoading(on, msg, submsg) {
      if (loadingOverlay) loadingOverlay.classList.toggle('visible', !!on);
      if (msg && loadingMsg) loadingMsg.textContent = msg;
      if (submsg !== undefined) {
        const subEl = loadingOverlay && loadingOverlay.querySelector('#loading-sub, .loading-sub');
        if (subEl) {
          subEl.textContent = submsg;
          subEl.style.display = submsg ? 'block' : 'none';
        }
      }
    }

    return {
      loadSTL, setLoading, resize,
      get scene()    { return scene; },
      get camera()   { return camera; },
      get renderer() { return renderer; },
      get mesh()     { return mesh; },
    };
  }

  // ============================================================================
  // Tally form modal (Mission Report + Library Submission share this)
  // ============================================================================
  // Opens an in-page modal hosting a Tally form, with prefilled URL params
  // captured from the page. Same modal infrastructure is reused for any
  // Tally form the project hosts — Mission Report is the original use; the
  // pivot-cup library submission form was added in session 12.
  //
  // SETUP per form: each Tally form is built in the Tally dashboard, its
  // share URL grabbed (`tally.so/r/<id>`), and the URL parameter names of its
  // fields configured to match what the page sends. The page passes the URL
  // either via `opts.formUrl` (per-call) or via `LT.feedbackConfig.formUrl`
  // (global default for backward-compatible Mission Report calls).
  //
  // Mission Report form fields (URL-parameter names — original use):
  //   tool         — short answer (hidden)   e.g. "Pivot Cup"
  //   inputs       — long answer  (hidden)   e.g. "Mode: pointed | Pivot diameter: 10.0 mm | …"
  //   page_url     — short answer (hidden)
  //   browser      — short answer (hidden)
  //   suggestions  — long answer  (visible: "Suggestions/Problems")
  //   comments     — long answer  (visible: "Comments")
  //   email        — email        (visible, optional)
  //
  // Library Submission form fields (URL-parameter names — pivot-cup library):
  //   mode         — short answer (hidden)   e.g. "pointed"
  //   pivot_d      — number       (hidden)
  //   pivot_l      — number       (hidden)
  //   socket_d     — number       (hidden)
  //   socket_depth — number       (hidden)
  //   page_url     — short answer (hidden)
  //   browser      — short answer (hidden)
  //   truck_brand  — short answer (visible, REQUIRED)
  //   truck_model  — short answer (visible, optional)
  //   source       — single select (visible, REQUIRED, options: "measured", "dialed")
  //   handle       — short answer (visible, optional, prompt for an alias not real name)
  //   notes        — long answer  (visible, optional)
  //
  // The URL-parameter-name mapping is set in Tally's per-field settings.
  const feedbackConfig = {
    formUrl: 'https://tally.so/r/9q2Wxp',
  };

  function ensureFeedbackModal() {
    let modal = document.getElementById('lt-feedback-modal');
    if (modal) return modal;
    modal = document.createElement('div');
    modal.id = 'lt-feedback-modal';
    modal.className = 'feedback-modal';
    modal.innerHTML =
      '<div class="feedback-backdrop" data-close></div>' +
      '<div class="feedback-frame" role="dialog" aria-modal="true" aria-label="Mission Report">' +
        '<div class="feedback-header">' +
          '<span class="feedback-title">Mission Report</span>' +
          '<button class="feedback-close" type="button" data-close aria-label="Close">×</button>' +
        '</div>' +
        '<div class="feedback-body">' +
          '<iframe class="feedback-iframe" frameborder="0" loading="lazy" title="Feedback form"></iframe>' +
        '</div>' +
      '</div>';
    document.body.appendChild(modal);
    modal.querySelectorAll('[data-close]').forEach(el => {
      el.addEventListener('click', closeFeedbackModal);
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && modal.classList.contains('visible')) closeFeedbackModal();
    });

    // Tally posts the form's measured content height when dynamicHeight=1 is
    // set on the embed URL. We resize the iframe to match so the form fits
    // without an internal scrollbar. Tally's payload comes as a JSON string
    // with shape { event: 'Tally.FormHeightChanged', payload: { height: N } }
    // — we parse defensively and fall through silently on anything unexpected.
    window.addEventListener('message', (e) => {
      if (!e || typeof e.origin !== 'string' || e.origin.indexOf('tally.so') === -1) return;
      let data = e.data;
      if (typeof data === 'string') {
        try { data = JSON.parse(data); } catch (_) { return; }
      }
      if (!data) return;
      const h = (data.payload && data.payload.height) || data.height;
      if (typeof h !== 'number' || !isFinite(h) || h <= 0) return;
      const iframe = modal.querySelector('.feedback-iframe');
      if (iframe) iframe.style.height = h + 'px';
    });

    return modal;
  }

  function closeFeedbackModal() {
    const modal = document.getElementById('lt-feedback-modal');
    if (!modal) return;
    modal.classList.remove('visible');
    document.body.style.overflow = '';
    // Clear iframe src so the form doesn't keep state between opens.
    setTimeout(() => {
      const iframe = modal.querySelector('.feedback-iframe');
      if (iframe) iframe.src = 'about:blank';
    }, 250);
  }

  function openFeedback(opts) {
    opts = opts || {};

    // Form URL: explicit per-call wins; else fall back to the global Mission
    // Report config (back-compat for the original feedback callers).
    const cfg     = (window.LT && window.LT.feedbackConfig) || feedbackConfig;
    const formUrl = opts.formUrl || cfg.formUrl;
    const title   = opts.title   || 'Mission Report';

    if (!formUrl || formUrl.indexOf('REPLACE') !== -1) {
      alert('This form is not wired up yet — sit tight!');
      return;
    }
    let url;
    try { url = new URL(formUrl); }
    catch (e) { console.error('Bad form URL:', formUrl); return; }

    // Convert tally.so/r/<id> → tally.so/embed/<id> for clean iframe embedding.
    url.pathname = url.pathname.replace('/r/', '/embed/');

    // Tally embed display flags. We keep Tally's form title visible — our
    // modal header above it carries the action label (e.g. "Mission Report");
    // the two stack cleanly.
    url.searchParams.set('transparentBackground', '1');
    url.searchParams.set('dynamicHeight', '1');     // Tally posts height events; see listener below
    url.searchParams.set('alignLeft', '1');

    // Auto-context — every form gets these.
    url.searchParams.set('page_url', window.location.href);
    url.searchParams.set('browser',  navigator.userAgent);

    // Mission-Report-style prefill: a `tool` label + a flattened `inputs`
    // string. Used by the original feedback caller; kept for back-compat.
    if (opts.tool) url.searchParams.set('tool', opts.tool);
    if (opts.params) {
      const params = opts.params;
      const inputs = Object.keys(params).map(k => k + ': ' + params[k]).join(' | ');
      if (inputs) url.searchParams.set('inputs', inputs);
    }

    // Library-style prefill: structured fields go straight to their own Tally
    // URL parameter (one column each in the connected Google Sheet). Pass any
    // raw key/value pairs the form expects.
    if (opts.fields) {
      Object.keys(opts.fields).forEach(k => {
        url.searchParams.set(k, opts.fields[k]);
      });
    }

    const modal = ensureFeedbackModal();
    // Title is per-open — the same modal hosts different forms with different
    // headers ("Mission Report" / "Submit to Library" / etc.).
    modal.querySelector('.feedback-title').textContent = title;
    modal.querySelector('.feedback-iframe').src = url.toString();
    modal.classList.add('visible');
    document.body.style.overflow = 'hidden';
  }

  // ============================================================================
  // Tooltips — info icon + popover (tap/click to toggle)
  // ============================================================================
  // Delegated handler: any `.info-btn` with a `data-tooltip` attribute opens
  // a popover next to itself when clicked or tapped. Stops propagation so an
  // info button inside a clickable card doesn't fire the card's handler.
  // Outside-click and Escape close. Only one popover open at a time.
  function initTooltips() {
    let openPopover = null;
    let openButton  = null;

    function close() {
      if (!openPopover) return;
      const p = openPopover, b = openButton;
      openPopover = null; openButton = null;
      if (b) {
        b.classList.remove('active');
        b.setAttribute('aria-expanded', 'false');
      }
      p.classList.remove('visible');
      // Remove after fade-out
      setTimeout(() => { if (p.parentNode) p.parentNode.removeChild(p); }, 200);
    }

    function open(btn) {
      close();
      const text = btn.getAttribute('data-tooltip');
      if (!text) return;
      const pop = document.createElement('div');
      pop.className = 'tooltip-popover';
      pop.setAttribute('role', 'tooltip');
      pop.textContent = text;
      document.body.appendChild(pop);

      // Position: prefer below the button, flip above if no room.
      // Horizontally center on the button, then nudge to stay on-screen.
      const margin = 8;
      const rect = btn.getBoundingClientRect();
      const popRect = pop.getBoundingClientRect();
      const vw = window.innerWidth, vh = window.innerHeight;
      const sx = window.scrollX, sy = window.scrollY;

      let top  = rect.bottom + sy + 6;
      let left = rect.left + sx + rect.width / 2 - popRect.width / 2;

      if (left < margin)                  left = margin;
      if (left + popRect.width > vw - margin) left = vw - popRect.width - margin;

      // Flip above if it would overflow the viewport bottom
      if (rect.bottom + popRect.height + 12 > vh) {
        top = rect.top + sy - popRect.height - 6;
        if (top < sy + margin) top = sy + margin;
      }

      pop.style.top  = top  + 'px';
      pop.style.left = left + 'px';
      requestAnimationFrame(() => pop.classList.add('visible'));

      btn.classList.add('active');
      btn.setAttribute('aria-expanded', 'true');
      openPopover = pop;
      openButton  = btn;
    }

    document.addEventListener('click', (e) => {
      const btn = e.target.closest('.info-btn');
      if (btn) {
        e.preventDefault();
        e.stopPropagation();   // don't bubble to mode/pattern card handlers
        if (btn === openButton) close();
        else open(btn);
        return;
      }
      // Click outside the popover and not on an info button → close
      if (openPopover && !openPopover.contains(e.target)) close();
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && openPopover) { close(); return; }
      // Synthesize click on Enter/Space for span+role="button" info icons
      // (used inside mode/style cards, where nesting <button> is invalid HTML).
      const a = document.activeElement;
      if (a && a.classList && a.classList.contains('info-btn')
          && (e.key === 'Enter' || e.key === ' ')) {
        e.preventDefault();
        if (a === openButton) close(); else open(a);
      }
    });

    // Reposition on resize/scroll — simplest correct behaviour is to close.
    window.addEventListener('resize', close);
    window.addEventListener('scroll', close, true);
  }

  // ============================================================================
  // Usage logging
  // ============================================================================
  // Per-tab session ID, generated lazily on first use and persisted in
  // sessionStorage so all events from the same browser tab share an ID. The
  // backing Sheet uses this column to distinguish "1 person previewed 30
  // times" from "30 people previewed once each." sessionStorage scope means
  // the ID resets when the tab closes — no cross-session tracking, no
  // fingerprinting. If sessionStorage is blocked (Safari private mode, etc.)
  // we fall back to an in-memory ID prefixed `nostore_` so the column stays
  // populated and the failure is visible in the data.
  const sessionId = (function () {
    const KEY = 'lt_session_id';
    try {
      let id = sessionStorage.getItem(KEY);
      if (!id) {
        id = (crypto && crypto.randomUUID)
          ? crypto.randomUUID()
          : (Date.now().toString(36) + Math.random().toString(36).slice(2, 10));
        sessionStorage.setItem(KEY, id);
      }
      return id;
    } catch (_) {
      return 'nostore_' + Math.random().toString(36).slice(2, 12);
    }
  })();

  // Fire-and-forget event logger. Sends to /api/log-event on the same origin;
  // the Flask side enriches with Referer + User-Agent headers and forwards to
  // the Apps Script webhook. All errors are swallowed — usage logging must
  // never break a download or a preview.
  function logEvent(payload) {
    try {
      fetch('/api/log-event', {
        method:    'POST',
        headers:   { 'Content-Type': 'application/json' },
        body:      JSON.stringify(Object.assign({ session_id: sessionId }, payload || {})),
        keepalive: true,
      }).catch(() => {});
    } catch (_) { /* never throw from a logger */ }
  }

  // ============================================================================
  // Render warmup ping
  // ============================================================================
  // Fires a fire-and-forget GET to /api/health so Render's free-tier service
  // starts warming up while the visitor reads the page. Render spins down after
  // ~15 min idle; without the ping, the first /api/.../generate or /slice call
  // eats the full ~30s cold start. The Landing page fires its own ping too;
  // this one covers direct visitors to a tool page (URL share, bookmark).
  //
  // Hits the Render origin directly with `mode: 'no-cors'` so it works the
  // same regardless of where the page itself is served (Render in pre-migration
  // state, Netlify post-migration). Opaque response — we don't read the body,
  // we only care that the request lands. Errors are swallowed; warmup is best-
  // effort, never a user-visible failure.
  function pingApi() {
    try {
      fetch('https://lt-tools.onrender.com/api/health', {
        mode: 'no-cors', cache: 'no-store',
      }).catch(() => {});
    } catch (_) { /* never throw from a warmup ping */ }
  }

  // ============================================================================
  // Expose
  // ============================================================================
  window.LT = window.LT || {};
  Object.assign(window.LT, {
    initStarfield,
    fmt,
    SliderControl,
    UnitToggle,
    Viewport,
    MM_PER_IN,
    openFeedback,
    feedbackConfig,
    initTooltips,
    sessionId,
    logEvent,
    pingApi,
  });

  // Auto-init on DOMContentLoaded so pages don't have to call it.
  function autoInit() {
    initTooltips();
    pingApi();
    injectLoaderMark();
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', autoInit, { once: true });
  } else {
    autoInit();
  }
})();
