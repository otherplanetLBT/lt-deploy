"""
site_app.py — Longboard Technology unified site server
Serves the Tools page and both generator pages.

Usage:
    python site_app.py
    Open http://localhost:5000

Routes:
    /                              Tools page (index/hub for the generators)
    /pivot-cup/                    Pivot Cup Generator UI
    /riser-pad/                    Riser Pad Generator UI
    /api/health                    GET  → 200 'ok' (warmup/cold-start ping)
    /api/log-event                 POST → 204 (forwards usage event to Sheet)
    /api/pivot-cup/generate        POST → STL bytes
    /api/riser-pad/slice           POST → STL bytes
    /api/riser-pad/validate        POST → validation JSON

The /wiki/ route is intentionally absent until publishable wiki content exists.
The Landing page (longboardtechnology.com) is served separately by Netlify
from `deploy/Netlify/`; this app handles the `tools.` subdomain only.
"""

import io
import os
import math
import sys

import requests
from flask import Flask, request, jsonify, send_file, send_from_directory

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
SITE_DIR  = os.path.join(BASE_DIR, 'site')
ASSETS    = os.path.join(BASE_DIR, 'assets')

# Make ./generators importable
sys.path.insert(0, BASE_DIR)
from generators import pivot_cup
from generators import riser_pad as rp


# ── Riser pad master STL registry ─────────────────────────────────────────────
RISER_STL_DIR = os.path.join(ASSETS, 'riser-pad-stls')

# ── Style → master STL — fixed naming convention ─────────────────────────────
# Style name is the lowercase identifier used in the API + UI.
# Master STL filename is the capitalised style name + '.stl'.
#   solid    → Solid.stl
#   skeleton → Skeleton.stl
# To add a new style: register the name here AND drop a matching
# `<Stylename>.stl` file into assets/riser-pad-stls/. No other code changes.
KNOWN_STYLES  = ['solid', 'skeleton']
DEFAULT_STYLE = 'solid'


# ── Usage logging webhook ─────────────────────────────────────────────────────
# Apps Script web-app URL that receives preview/download events and appends
# them to a Google Sheet. Set in the Render dashboard env vars (NOT in git) —
# see download_log_setup.md at the project root for the one-time setup. If
# unset, /api/log-event is a no-op (returns 204 without forwarding). Local dev
# without the env var works the same way: events are silently dropped.
LOG_WEBHOOK_URL = os.environ.get('LOG_WEBHOOK_URL', '').strip()


def get_master_path(style):
    if style not in KNOWN_STYLES:
        raise FileNotFoundError(f"Unknown style '{style}'.")
    path = os.path.join(RISER_STL_DIR, f'{style.capitalize()}.stl')
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"Master STL for style '{style}' is missing. Expected: {path}")
    return path


# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder=None)


# ── Static file serving ───────────────────────────────────────────────────────

@app.route('/')
def root():
    return send_from_directory(SITE_DIR, 'index.html')

@app.route('/shared.css')
def shared_css():
    return send_from_directory(SITE_DIR, 'shared.css')

@app.route('/shared.js')
def shared_js():
    return send_from_directory(SITE_DIR, 'shared.js')

@app.route('/assets/<path:filename>')
def assets(filename):
    return send_from_directory(SITE_DIR, os.path.join('assets', filename))

@app.route('/pivot-cup/')
@app.route('/pivot-cup/index.html')
def pivot_cup_page():
    return send_from_directory(os.path.join(SITE_DIR, 'pivot-cup'), 'index.html')

@app.route('/riser-pad/')
@app.route('/riser-pad/index.html')
def riser_pad_page():
    return send_from_directory(os.path.join(SITE_DIR, 'riser-pad'), 'index.html')


# ── Warmup / health ───────────────────────────────────────────────────────────
# Cold-start absorber. Render's free tier spins down after 15 min idle; the
# next request triggers a ~30s wake-up. The Landing page (Netlify, instant)
# fires a fire-and-forget fetch to this endpoint on page load so Render starts
# warming up while the visitor is reading. By the time they navigate to a tool
# page the cold-start delay is mostly absorbed by their reading time. Returns
# a tiny string so the response is cheap; no CORS headers needed because the
# Landing-page fetch uses `mode: 'no-cors'` (we don't care about the body, we
# only care that the request lands).

@app.route('/api/health')
def health():
    return 'ok', 200


# ── Usage logging ─────────────────────────────────────────────────────────────
# Receives fire-and-forget JSON events from the page (LT.logEvent in
# shared.js) and forwards to the Apps Script webhook. We enrich with Referer
# + User-Agent server-side so the page payload stays small. The endpoint
# returns 204 unconditionally — even if the webhook is unset or the upstream
# call fails — because the page doesn't read the response, and we never want
# logging plumbing to surface as a user-visible error.
#
# Payload shapes (the page guarantees these):
#   preview:  {type: 'preview',  tool, session_id}
#   download: {type: 'download', tool, session_id, unit, params: {...}}

@app.route('/api/log-event', methods=['POST'])
def api_log_event():
    if not LOG_WEBHOOK_URL:
        return '', 204  # logger not wired — silently drop
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


# ── Pivot cup API ─────────────────────────────────────────────────────────────

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


# ── Riser pad API ─────────────────────────────────────────────────────────────

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


# ── Boot ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print()
    print('  Longboard Technology — Local Dev Server')
    print('  Tools:  /pivot-cup/   /riser-pad/')
    print()
    print('  http://localhost:5000')
    print()
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
