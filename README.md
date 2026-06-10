# Longboard Technology — Deploys

Source for the public-facing surfaces of [Longboard Technology](https://longboardtechnology.com).

## Layout

```
deploy/
├── render.yaml                ← Render Blueprint (declarative service config)
├── .gitignore
├── Landing/                   ← deploys to longboardtechnology.com (static)
│   ├── index.html
│   └── logo_frames/           ← animated-logo PNG sequence
├── Tools/                     ← deploys to tools.longboardtechnology.com (static)
│   ├── index.html             ← Tools page
│   ├── shared.css / shared.js ← shared chrome
│   ├── _redirects             ← proxies /api/* to the Render service
│   ├── pivot-cup/             ← Pivot Cup Generator
│   ├── riser-pad/             ← Riser Pad Generator
│   └── logo/                  ← Logo Animation Lab
├── Render/                    ← deploys to tools.longboardtechnology.com/api/* (Flask)
│   ├── site_app.py            ← Flask entry — /api/* only in production
│   ├── requirements.txt
│   ├── Run Flask.bat          ← Windows local-dev launcher (Flask + cloudflared)
│   ├── generators/            ← STL geometry modules (Flask-free)
│   └── assets/                ← master STL files for the Riser Pad Generator
└── Glossary/                  ← Glossary reader app (local preview; not yet deployed)
```

## Three targets

| Subfolder | Host | URL | Stack |
|---|---|---|---|
| `Landing/` | Netlify (static) | `longboardtechnology.com` | HTML/CSS/JS |
| `Tools/` | Netlify (static) | `tools.longboardtechnology.com` | HTML/CSS/JS |
| `Render/` | Render free tier | `tools.longboardtechnology.com/api/*` | Flask + gunicorn + manifold3d |

Since the 2026-05-08 migration, the static surfaces serve from Netlify CDN and Render runs the geometry **API only**. Page-side `fetch('/api/...')` calls stay same-origin via `Tools/_redirects` (`/api/*  https://lt-tools.onrender.com/api/:splat  200` — a transparent proxy, no CORS). Render's blueprint (`render.yaml`, `rootDir: Render`) builds from the `Render/` subfolder; the two Netlify projects each deploy from their own subdirectory.

## Deploy

All targets auto-deploy on push to `main`; if only one subdirectory changes, only that target rebuilds. See `render.yaml` comments for Render plan-upgrade and custom-domain notes. (`tools.longboardtechnology.com` is **not** a Render custom domain — it resolves to Netlify; Render's health check uses `/api/health`.)

## Local dev

For the Render side, double-click `Render/Run Flask.bat` on Windows and open <http://localhost:5000>. It wipes `__pycache__`, runs `python -B site_app.py` (source `.py` stays canonical — Drive's mtime lag has historically confused Python's bytecode cache), and opens a `cloudflared` tunnel in a second window for a shareable public preview URL. `site_app.py`'s static routes for the full site are `__main__`-gated, so localhost serves Tools + both generators single-origin while production ships API only.

For the static sides, open `Landing/index.html` or `Tools/index.html` directly, or serve with any static server (`python -m http.server`).
