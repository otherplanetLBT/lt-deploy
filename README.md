# Longboard Technology — Deploys

Source for the public-facing surfaces of [Longboard Technology](https://longboardtechnology.com).

## Layout

```
deploy/
├── render.yaml                ← Render Blueprint (declarative service config)
├── .gitignore
├── Render/                    ← deploys to tools.longboardtechnology.com (Flask + manifold3d)
│   ├── site_app.py
│   ├── requirements.txt
│   ├── Run Flask.bat          ← Windows local-dev launcher
│   ├── generators/            ← STL geometry modules
│   ├── assets/                ← master STL files for the Riser Pad Generator
│   └── site/                  ← Tools page + both generator pages (HTML/CSS/JS)
└── Netlify/                   ← deploys to longboardtechnology.com (the Landing page)
```

## What ships where

| Subfolder | Host | URL | Stack |
|---|---|---|---|
| `Render/` | Render free tier (Python web service) | `tools.longboardtechnology.com` | Flask + gunicorn + manifold3d |
| `Netlify/` | Netlify (static) | `longboardtechnology.com` | Static HTML/CSS/JS |

Render's blueprint is declared in `deploy/render.yaml` — it points at the `Render/` subdirectory via `rootDir: Render`, so the build runs `pip install -r requirements.txt` and `gunicorn site_app:app …` from inside that subfolder. Netlify uses its own dashboard config to deploy from the `Netlify/` subdirectory.

## Deploy

Both targets auto-deploy on push to `main`. If only files inside one subdirectory change, only that target rebuilds.

For the Render service specifically, see comments in `render.yaml` for plan upgrade and custom-domain notes.

## Local dev

For the Render side, double-click `Render/Run Flask.bat` on Windows and open <http://localhost:5000>. The script wipes `__pycache__` on every launch and runs `python -B site_app.py` so source `.py` files are the canonical truth (Google Drive's mtime lag has historically confused Python's bytecode cache).

For the Netlify side (static), open `Netlify/index.html` directly in a browser, or serve the folder with any static server (`python -m http.server` works fine).
