# Glossary App — Design Spec

Public-facing reader surface for the Ultimate Longboard Wiki glossary. This document is the design spec and implementation plan for building that surface. It is not the editorial tool — that is `Wiki/Glossary/glossary_tools/glossary_ui.py`.

**Current state:** Pre-build. Spec written; no app code yet.

---

## What this is

A Flask web app that serves the canonical terms from `glossary.db` to readers. It is read-only — it never writes to the database. Its job is to make the 106+ (and growing) canonical glossary terms browsable and searchable by anyone reading the wiki.

The editorial counterpart (`glossary_ui.py`) handles candidate review, promotion, rejection, and redirect management. This app is the publication surface.

---

## Relationship to other surfaces

| Surface | Role | Status |
|---|---|---|
| `glossary_ui.py` | Editorial — review, promote, reject candidates | Live (local) |
| **This app (`glossary_app.py`)** | **Reader — browse, search, read canonical terms** | **Pre-build** |
| Wiki (Astro) | Long-term publication platform for all wiki content | Parked — future |
| `longboardtechnology.com` | Brand landing page | Live |
| `tools.longboardtechnology.com` | STL generator tools | Live |

The Flask reader app is a local-first development and preview surface. When the Astro wiki eventually comes online, this app's functionality either migrates into Astro's static pages (generated from the DB at build time) or is exposed as a live API endpoint that Astro queries. That decision is deferred.

---

## Feature scope — v1

### 1. Individual term pages

**URL:** `/glossary/<slug>`

A permalink-style page for each canonical term. Displays:
- Term name (h1)
- Definition (the canonical text)
- Category or categories (linked to the category page)
- Also Called (alias list)
- Esoteric rating (displayed as a quiet meta label, not prominently)

**Slug scheme:** lowercase, spaces and special characters replaced with hyphens (e.g. `reverse-kingpin-truck`). Slugs are generated from `term` at serve time — no slug column needed in the DB.

**Redirect / alias resolution:** If a user arrives at a slug that matches a term in the `redirects` table, they are redirected (HTTP 301) to the canonical term's page. If a slug matches an `also_called` alias of any term, redirect to that term. This makes deep links from wiki articles resilient to naming variations.

*(Note: redirect resolution was not explicitly in v1 scope but is cheap to add alongside term pages and makes the URL scheme trustworthy from day one. Listed here as included.)*

### 2. Browse by category

**URL:** `/glossary/category/<category-slug>`

A page listing all canonical terms in a given category, sorted alphabetically. Each term is a link to its term page.

**Category index:** `/glossary/categories` — a page listing all categories with their term counts, linked to the per-category browse pages.

### 3. Search by term name / alias

**URL:** `/glossary/search?q=<query>` (or live AJAX — see implementation notes)

Text search across canonical term names and their `also_called` aliases. Returns matching terms, ranked by relevance (exact match first, then prefix match, then substring).

The search bar lives on the homepage and is replicated in the site nav on all glossary pages.

### Homepage

Deferred. No homepage in v1 — root URL (`/`) redirects to `/categories` (the category index). The category index is the de facto landing page for now.

---

## Architecture

```
deploy/Glossary/
├── GLOSSARY_APP.md          ← this file
├── glossary_app.py          ← Flask app (read-only DB access)
└── Run Glossary App.bat     ← Windows local dev launcher
```

Single-file Flask app, same pattern as `glossary_ui.py`. No separate templates directory — HTML rendered via `render_template_string`. No writes to the DB.

**Brand:** Wears the LT brand DNA — navy backgrounds, kelly green accent, Orbitron + Space Mono, animated starfield in the nav strip. Same CSS variable system as `shared.css` on the tools side. The glossary reader is a brand surface, not a neutral admin tool.

**Port:** 5001 (editorial UI runs on 5000; both can be open simultaneously during local development).

---

## DB connection

The canonical source of truth is `Wiki/Glossary/glossary.db`, owned by the Wiki project. The reader app connects to it read-only.

**Relative path from `deploy/Glossary/`:**

```
../../../The Ultimate Longboard Wiki Project/Wiki/Glossary/glossary.db
```

(Three levels up to `Projects/`, then into the Wiki project tree.)

The app accepts a `--db` CLI argument to override this path, identical to the editorial UI pattern. The default is computed relative to the script's own location so it works from any working directory.

**Read-only mode:** SQLite connection opened with `uri=True` and `?mode=ro` to enforce the no-write constraint at the connection level:

```python
sqlite3.connect(f'file:{DB_PATH}?mode=ro', uri=True)
```

This prevents any accidental writes from reader-app code.

---

## URL scheme

**Domain:** `glossary.longboardtechnology.com` (its own subdomain, not a path prefix).

| Path | Page |
|---|---|
| `/` | Redirects to `/categories` |
| `/search?q=...` | Search results |
| `/categories` | All categories with counts |
| `/category/<slug>` | Terms in a category |
| `/<term-slug>` | Individual term page |

**Slug generation:** `term.lower().replace(' ', '-')` with non-alphanumeric-non-hyphen characters stripped. Applied consistently at URL generation and at lookup. Collision handling: if two canonical terms produce the same slug, the app logs a warning at startup and the second term is reachable by its exact term name as a fallback. (Collisions are unlikely given the domain vocabulary.)

**Flask `url_for` alignment:** All internal links use `url_for` — no hardcoded paths — so the app runs at root locally (`http://localhost:5001/`) and maps cleanly to `glossary.longboardtechnology.com/` in production without URL changes.

---

## What it shows (data rules)

- Only `status='canonical'` terms are shown. Candidates and rejected terms are invisible to readers.
- Terms with `esoteric_rating >= 4` are shown but tagged with a subtle "Advanced" label. No toggle in v1 — show everything, just signal the advanced ones.
- The `needed_by`, `confidence`, `date_added`, and `date_reviewed` fields are internal metadata — not shown to readers.
- `sources` field: not shown in v1 (sources are raw intake references, not polished citations). Deferred to a future editorial pass that cleans them up for publication.

---

## Implementation notes

**Search:** SQLite `LIKE '%query%'` across `term` and `also_called` is sufficient for v1 with ~100 terms. If the canonical count grows past a few hundred, consider FTS5 virtual table (SQLite's built-in full-text search). The schema already supports it — no migration needed, just `CREATE VIRTUAL TABLE terms_fts USING fts5(...)` on the read side.

**Live search vs. form submit:** v1 uses a standard form submit (no JS fetch). If the response feels sluggish at scale, upgrade to a `fetch`-based live search that calls `/glossary/search?q=...&format=json` — the same Flask route can detect `Accept: application/json` and return a JSON payload.

**Starfield:** The animated starfield from `shared.js` / `shared.css` is inlined into the app's nav strip, same as the tools pages. No external CDN dependency — the JS is small enough to inline directly in the single-file app.

**Static assets:** None externally fetched. All CSS and JS inlined. Google Fonts (Orbitron + Space Mono) loaded from `fonts.googleapis.com` same as the existing tool pages.

---

## Local dev notes

- **Launch:** `Run Glossary App.bat` — same pattern as `Run Flask.bat` in Render. Wipes `__pycache__`, runs `python -B glossary_app.py`.
- **Port:** `http://localhost:5001` — different from editorial UI (5000) so both can run simultaneously.
- **DB path:** App defaults to the relative path above. Override with `python glossary_app.py --db <path>` if your folder layout differs.
- **Read-only connection:** Opening the DB with `mode=ro` means the file doesn't need to be writable — safe to run while the editorial UI has it open.

---

## Deployment path (future)

**Subdomain:** `glossary.longboardtechnology.com` — its own Netlify project (or Render service), same monorepo pattern as the existing tools. DNS: CNAME at Squarespace the same way `tools.longboardtechnology.com` was set up.

When the time comes, options in order of preference:

1. **Render (new service, same repo)** — add a second Render service pointing at `deploy/Glossary/`, DB path provided via env var. `glossary.longboardtechnology.com` CNAMEs to it. Flask serves all routes directly; no Netlify proxy needed (no static/API split — it's all dynamic).
2. **Netlify + Render split** — same proxy pattern as tools: static shell on Netlify CDN, search calls proxy to Render. More infra complexity; only worth it if CDN edge caching matters for term pages.
3. **Astro static pages** — when the wiki ships in Astro, the glossary reader migrates into it as statically generated term pages. The Flask reader becomes a local preview tool only.

The Flask app is written to be deployable as-is to option 1 — no hard-coded localhost assumptions, DB path via `--db` flag or env var.

---

## Out of scope for v1

- **Writing to the DB** — no submissions, no "suggest a term" form. Read-only.
- **User accounts / favorites** — deferred.
- **Esoteric toggle** (show/hide advanced terms) — show all in v1, just label the advanced ones.
- **"Needed by" / article cross-links** — the `needed_by` field links terms to article IDs. Surfacing this requires the article map, which is a separate publishing pipeline. Deferred until article pages exist.
- **Full citation sources** — sources field is raw intake metadata. Requires a cleanup pass before being reader-ready. Deferred.
- **Pronunciation / IPA** — not in the DB schema. Future addition.

---

## Decisions made

- **Homepage:** Deferred. Root redirects to `/categories`. The category index is the landing page for v1.
- **Subdomain:** `glossary.longboardtechnology.com`. Flask app runs at root; no path prefix needed.
- **Alias search results:** Straight to the canonical term page — no intermediate redirect annotation shown to the user.

## Open questions

- **Category slug strategy:** Categories stored as plain strings (`Trucks`, `Bushings`, `How to Ride`). Slugs generated the same way as term slugs. Edge case: multi-word category names with special characters — confirm no existing categories cause slug collisions before first run.
- **DB path at deployment:** Render env var name for the DB path TBD at deploy time. Locally, the relative path default is sufficient.
