"""
site_app.py — Longboard Technology API server (Render)

In production, Render serves /api/* only. The static surfaces
(Tools index + both generator pages + shared.css/js) are hosted on
Netlify at tools.longboardtechnology.com, which transparently proxies
/api/* back here via deploy/Tools/_redirects (status 200 = same-origin
proxy, so the page-side fetch calls just hit /api/... with no CORS
plumbing).

Routes:
    /api/health                    GET  -> 200 'ok' (warmup/cold-start ping)
    /api/log-event                 POST -> 204 (forwards usage event to Sheet)
    /api/pivot-cup/generate        POST -> STL bytes
    /api/riser-pad/library         GET  -> JSON list of library style names
    /api/riser-pad/slice           POST -> STL bytes
    /api/riser-pad/validate        POST -> validation JSON

Local dev: `python site_app.py` (or Run Flask.bat) registers an extra
batch of static-fallback routes inside the __main__ block, pointing at
../Tools/. Those let localhost:5000 serve the full site (static + API,
single origin) without standing up a separate static server. Production
gunicorn imports this module and never enters __main__, so those routes
do not ship.
"""

import io
import os
import math
import sys

import requests
from flask import Flask, request, jsonify, send_file, send_from_directory

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
ASSETS    = os.path.join(BASE_DIR, 'assets')

# Make ./generators importable
sys.path.insert(0, BASE_DIR)
from generators import pivot_cup
from generators import riser_pad as rp


# -- Riser pad master STL registry --------------------------------------------
RISER_STL_DIR = os.path.join(ASSETS, 'riser-pad-stls')

# The three defaults are hardcoded in the UI with icons/tooltips/order.
# Everything else in RISER_STL_DIR is a library item returned by /api/riser-pad/library.
# To add a library item: drop <Name>.stl into assets/riser-pad-stls/ and push.
DEFAULT_STYLE     = 'Solid'
DEFAULT_STL_NAMES = {'Solid', 'Skeleton', 'Drop-thru'}


# -- Usage logging webhook ----------------------------------------------------
# Apps Script web-app URL that receives preview/download events and appends
# them to a Google Sheet. Set in the Render dashboard env vars (NOT in git) --
# see download_log_setup.md at the project root for the one-time setup. If
# unset, /api/log-event is a no-op (returns 204 without forwarding). Local dev
# without the env var works the same way: events are silently dropped.
LOG_WEBHOOK_URL = os.environ.get('LOG_WEBHOOK_URL', '').strip()


def get_master_path(style):
    path = os.path.join(RISER_STL_DIR, f'{style}.stl')
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Master STL not found: '{style}.stl'")
    return path


# -- Flask app ----------------------------------------------------------------
app = Flask(__name__, static_folder=None)


# -- Warmup / health ----------------------------------------------------------
# Cold-start absorber. Render's free tier spins down after 15 min idle; the
# next request triggers a ~30s wake-up. Tool pages on Netlify fire a
# fire-and-forget fetch to this endpoint on DOMContentLoaded (LT.pingApi in
# shared.js) so Render starts warming up the moment a visitor lands. By the
# time they hit Preview the cold-start delay is mostly absorbed by their
# reading time. Returns a tiny string so the response is cheap; no CORS
# headers needed because the page-side fetch uses `mode: 'no-cors'`.

@app.route('/api/health')
def health():
    return 'ok', 200


# -- Usage logging ------------------------------------------------------------
# Receives fire-and-forget JSON events from the page (LT.logEvent in
# shared.js) and forwards to the Apps Script webhook. We enrich with Referer
# + User-Agent server-side so the page payload stays small. The endpoint
# returns 204 unconditionally -- even if the webhook is unset or the upstream
# call fails -- because the page doesn't read the response, and we never want
# logging plumbing to surface as a user-visible error.
#
# Payload shapes (the page guarantees these):
#   preview:  {type: 'preview',  tool, session_id}
#   download: {type: 'download', tool, session_id, unit, params: {...}}

@app.route('/api/log-event', methods=['POST'])
def api_log_event():
    if not LOG_WEBHOOK_URL:
        return '', 204  # logger not wired -- silently drop
    try:
        payload = request.get_json(force=True, silent=True) or {}
        payload['referrer']   = request.headers.get('Referer', '')
        payload['user_agent'] = request.headers.get('User-Agent', '')
        requests.post(LOG_WEBHOOK_URL, json=payload, timeout=2)
    except Exception:
        # Never let a webhook hiccup propagate. The download/preview the user
        # actually cares about already succeeded by the time we get here.
        pass
    return '', 204


# -- Pivot cup API ------------------------------------------------------------

@app.route('/api/pivot-cup/generate', methods=['POST'])
def api_pivot_cup_generate():
    try:
        data = request.get_json(force=True)
        mode = str(data.get('mode', 'pointed')).lower()
        pd   = float(data.get('pivot_d',      0))
        pl   = float(data.get('pivot_l',      0))
        sd   = float(data.get('socket_d',     0))
        sdep = float(data.get('socket_depth', 0))

        pivot_cup.validate(mode, pd, pl, sd, sdep)
        stl_bytes = pivot_cup.build_stl(mode, pd, pl, sd, sdep)
        filename  = pivot_cup.filename_for(mode, pd, pl, sd, sdep)

        return send_file(
            io.BytesIO(stl_bytes),
            mimetype='application/octet-stream',
            as_attachment=False,
            download_name=filename,
        )

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        app.logger.exception("Pivot cup generation error")
        return jsonify({'error': f'Generation failed: {e}'}), 500


# -- Riser pad API ------------------------------------------------------------

@app.route('/api/riser-pad/library', methods=['GET'])
def api_riser_pad_library():
    """Return a sorted list of library style names (all STLs except the 3 defaults)."""
    names = []
    if os.path.isdir(RISER_STL_DIR):
        for fname in sorted(os.listdir(RISER_STL_DIR)):
            if fname.endswith('.stl'):
                name = fname[:-4]
                if name not in DEFAULT_STL_NAMES:
                    names.append(name)
    return jsonify(names)


@app.route('/api/riser-pad/slice', methods=['POST'])
def api_riser_pad_slice():
    data          = request.get_json()
    style         = data.get('style', DEFAULT_STYLE)
    center_height = float(data.get('center_height', 5.0))
    angle_deg     = float(data.get('angle', 0.0))

    try:
        master_path   = get_master_path(style)
        master_height = rp.get_master_height(master_path)
        rp.validate(center_height, angle_deg, master_height)
    except (FileNotFoundError, ValueError) as e:
        return jsonify({'error': str(e)}), 400

    try:
        manifold  = rp.slice_master(master_path, center_height, angle_deg)
        stl_bytes = rp.to_stl_bytes(manifold)
    except Exception as e:
        app.logger.exception("Riser pad slice error")
        return jsonify({'error': f'Slice failed: {e}'}), 500

    filename = rp.filename_for(style, center_height, angle_deg)
    return send_file(io.BytesIO(stl_bytes),
                     mimetype='application/octet-stream',
                     as_attachment=False,
                     download_name=filename)


@app.route('/api/riser-pad/validate', methods=['POST'])
def api_riser_pad_validate():
    data          = request.get_json()
    style         = data.get('style', DEFAULT_STYLE)
    center_height = float(data.get('center_height', 5.0))
    angle_deg     = float(data.get('angle', 0.0))

    try:
        master_path   = get_master_path(style)
        master_height = rp.get_master_height(master_path)
    except FileNotFoundError as e:
        return jsonify({'valid': False, 'error': str(e)})

    thin  = rp.thin_end_height(center_height, angle_deg)
    thick = center_height + 39.0 * math.tan(math.radians(angle_deg))
    min_h = rp.min_center_height(angle_deg)

    try:
        rp.validate(center_height, angle_deg, master_height)
        valid, error = True, None
    except ValueError as e:
        valid, error = False, str(e)

    return jsonify({
        'valid': valid, 'error': error,
        'thick_end': round(thick, 2), 'thin_end': round(thin, 2),
        'min_height': round(min_h, 2), 'master_height': round(master_height, 2),
    })


# -- Glossary sub-app ---------------------------------------------------------
# Mount the glossary Flask app at /glossary so Netlify-Tools can proxy
# /glossary* here via _redirects (same pattern as /api/*).
#
# DispatcherMiddleware sets SCRIPT_NAME=/glossary before forwarding to the
# glossary sub-app, which makes url_for() inside the glossary templates
# automatically produce /glossary/... paths — no template edits needed.
#
# IMPORTANT: gunicorn must run `site_app:application`, not `site_app:app`.
# The health check at /api/health still works because unmatched paths fall
# through to the default `app`.

from werkzeug.middleware.dispatcher import DispatcherMiddleware
import glossary_app as _glossary_module

application = DispatcherMiddleware(app, {
    '/glossary': _glossary_module.app,
})


# -- Boot ---------------------------------------------------------------------

if __name__ == '__main__':
    # ===== LOCAL DEV ONLY =====================================================
    # Production gunicorn imports this module and never reaches __main__, so
    # everything below ships nowhere -- it exists purely so `python site_app.py`
    # (or Run Flask.bat) can serve the full site at localhost:5000 without
    # standing up a separate static server. Static surfaces are read from
    # ../Tools/ (the canonical static source -- the same directory Netlify
    # builds from in production), keeping a single source of truth.

    LOCAL_TOOLS_DIR = os.path.normpath(os.path.join(BASE_DIR, '..', 'Tools'))

    @app.route('/')
    def _local_root():
        return send_from_directory(LOCAL_TOOLS_DIR, 'index.html')

    @app.route('/shared.css')
    def _local_shared_css():
        return send_from_directory(LOCAL_TOOLS_DIR, 'shared.css')

    @app.route('/shared.js')
    def _local_shared_js():
        return send_from_directory(LOCAL_TOOLS_DIR, 'shared.js')

    @app.route('/pivot-cup/')
    @app.route('/pivot-cup/index.html')
    def _local_pivot_cup_page():
        return send_from_directory(os.path.join(LOCAL_TOOLS_DIR, 'pivot-cup'),
                                   'index.html')

    @app.route('/riser-pad/')
    @app.route('/riser-pad/index.html')
    def _local_riser_pad_page():
        return send_from_directory(os.path.join(LOCAL_TOOLS_DIR, 'riser-pad'),
                                   'index.html')

    print()
    print('  Longboard Technology - Local Dev Server')
    print(f'  Static surfaces from: {LOCAL_TOOLS_DIR}')
    print('  Tools:  /pivot-cup/   /riser-pad/')
    print()
    print('  http://localhost:5000')
    print()
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
