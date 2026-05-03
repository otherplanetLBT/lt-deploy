/* shared.js — Longboard Technology cross-page helpers
   ─────────────────────────────────────────────────────
   Provides:
     LT.initStarfield(canvas, opts)                — starfield animation
     LT.fmt.{mmToDisplay, displayToMm,             — number/unit helpers
            formatLen, formatDeg, parseRaw}
     LT.Viewport({...})                            — Three.js scene + STL loader
     LT.SliderControl({...})                       — slider + text input + markers
     LT.UnitToggle({...})                          — mm/in switching

   The page owns the state and constraint resolution. SliderControl just
   renders what the page tells it to, and reports user input via callbacks.
   This keeps "drag-wins" logic in one place (the page), where the full
   constraint graph is visible. */

(function () {
  'use strict';

  const MM_PER_IN = 25.4;

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

    function setLoading(on, msg) {
      if (loadingOverlay) loadingOverlay.classList.toggle('visible', !!on);
      if (msg && loadingMsg) loadingMsg.textContent = msg;
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
  });

  // Auto-init on DOMContentLoaded so pages don't have to call it.
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTooltips, { once: true });
  } else {
    initTooltips();
  }
})();
