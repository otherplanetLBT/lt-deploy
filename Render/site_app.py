"""
site_app.py — Longboard Technology unified site server
Serves the landing page and both generator tools.

Usage:
    python site_app.py
    Open http://localhost:5000

Routes:
    /                              landing / tools hub
    /pivot-cup/                    pivot cup generator UI
    /riser-pad/                    riser pad generator UI
    /api/pivot-cup/generate        POST → STL bytes
    /api/riser-pad/slice           POST → STL bytes
    /api/riser-pad/validate        POST → validation JSON

The /wiki/ route is intentionally absent until publishable wiki content exists.
"""

import io
import os
import math
import sys

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
