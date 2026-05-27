#!/usr/bin/env python3
"""
Glossary Reader — The Ultimate Longboard Wiki Project
Public-facing Flask app serving canonical glossary terms.
Read-only — never writes to the DB.

Usage:
    pip install flask
    python glossary_app.py [--db <path>] [--port 5001] [--debug]

Browse at:  http://localhost:5001
Deployment: glossary.longboardtechnology.com
"""

import argparse
import os
import re
import sqlite3

from flask import Flask, g, redirect, render_template_string, request, url_for

app = Flask(__name__)
app.secret_key = 'lt-glossary-reader-2026'
DB_PATH: str = ''


# ── Helpers ───────────────────────────────────────────────────────────────────

def slugify(s: str) -> str:
    """Convert any string to a URL-safe slug."""
    s = s.lower()
    s = re.sub(r'[^a-z0-9]+', '-', s)
    return s.strip('-')


def cat_display(cat: str) -> str:
    """'Esk8, Motor'  →  'Esk8 › Motor'"""
    return ' › '.join(p.strip() for p in cat.split(','))


def first_sentence(text: str, max_len: int = 150) -> str:
    """First sentence of a definition, for card previews."""
    if not text:
        return ''
    m = re.match(r'(.+?[.!?])(?:\s|$)', text)
    if m:
        return m.group(1)
    return text[:max_len].rstrip() + ('…' if len(text) > max_len else '')


# ── Database ──────────────────────────────────────────────────────────────────

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_=None):
    db = g.pop('db', None)
    if db:
        db.close()


def get_categories_grouped(db: sqlite3.Connection) -> dict:
    """
    Returns dict: { parent_key: [(cat_name, count, slug), ...] }
    Groups hierarchical category names ('Esk8, Motor') under their
    first segment ('Esk8'). Sorted alphabetically at both levels.
    """
    rows = db.execute(
        "SELECT category, COUNT(*) AS n FROM terms "
        "WHERE status='canonical' AND category IS NOT NULL AND TRIM(category) != '' "
        "GROUP BY category ORDER BY category"
    ).fetchall()

    groups: dict = {}
    for r in rows:
        cat = r['category']
        parent = cat.split(',')[0].strip()
        groups.setdefault(parent, []).append((cat, r['n'], slugify(cat)))

    return dict(sorted(groups.items()))


def get_category_terms(db: sqlite3.Connection, cat_slug: str):
    """Return (category_name, [term_dicts]) for a slug, or (None, []) if not found."""
    rows = db.execute(
        "SELECT * FROM terms "
        "WHERE status='canonical' AND category IS NOT NULL "
        "ORDER BY term"
    ).fetchall()
    matched_cat = None
    terms = []
    for t in rows:
        if t['category'] and slugify(t['category']) == cat_slug:
            matched_cat = t['category']
            terms.append(dict(t))
    return matched_cat, terms


def resolve_slug(db: sqlite3.Connection, slug: str):
    """
    Resolve a URL slug to a canonical term.
    Resolution order:
      1. Direct slug match on term name
      2. Slug match on an also_called alias → 301 to canonical slug
      3. Slug match on a redirects.synonym → 301 to canonical slug
    Returns (term_dict, redirect_slug|None), or (None, None) if unresolved.
    """
    terms = db.execute("SELECT * FROM terms WHERE status='canonical'").fetchall()

    # 1. Direct term slug
    for t in terms:
        if slugify(t['term']) == slug:
            return dict(t), None

    # 2. also_called alias → redirect
    for t in terms:
        if t['also_called']:
            for alias in (a.strip() for a in t['also_called'].split(',') if a.strip()):
                if slugify(alias) == slug:
                    return dict(t), slugify(t['term'])

    # 3. Redirects table → redirect
    for r in db.execute("SELECT synonym, canonical_term FROM redirects").fetchall():
        if slugify(r['synonym']) == slug:
            target = db.execute(
                "SELECT * FROM terms WHERE term=? COLLATE NOCASE AND status='canonical'",
                (r['canonical_term'],)
            ).fetchone()
            if target:
                return dict(target), slugify(target['term'])

    return None, None


def get_adjacent(db: sqlite3.Connection, term_id: int):
    """Return (prev_term_dict|None, next_term_dict|None) in alphabetical order."""
    ids = [r['id'] for r in db.execute(
        "SELECT id FROM terms WHERE status='canonical' ORDER BY term"
    ).fetchall()]
    try:
        idx = ids.index(term_id)
    except ValueError:
        return None, None

    def fetch(tid):
        row = db.execute("SELECT id, term FROM terms WHERE id=?", (tid,)).fetchone()
        return dict(row) if row else None

    prev = fetch(ids[idx - 1]) if idx > 0 else None
    nxt  = fetch(ids[idx + 1]) if idx < len(ids) - 1 else None
    return prev, nxt


def search_terms(db: sqlite3.Connection, q: str) -> list:
    """
    Search canonical term names and also_called aliases.
    Ranked: exact match > prefix > substring.
    """
    q_l = q.lower().strip()
    if not q_l:
        return []
    terms = db.execute(
        "SELECT * FROM terms WHERE status='canonical' ORDER BY term"
    ).fetchall()

    exact, prefix, sub = [], [], []
    for t in terms:
        names = [t['term'].lower()]
        if t['also_called']:
            names += [a.strip().lower() for a in t['also_called'].split(',') if a.strip()]
        td = dict(t)
        if q_l in names:
            exact.append(td)
        elif any(n.startswith(q_l) for n in names):
            prefix.append(td)
        elif any(q_l in n for n in names):
            sub.append(td)

    return exact + prefix + sub


# ── Assets ────────────────────────────────────────────────────────────────────

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700&family=Space+Mono:ital,wght@0,400;0,700;1,400&display=swap');

*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#07091a;--surface:#141f33;--surface2:#1d2742;--surface3:#283355;
  --border:#2a3a5c;--text:#e8eaf0;--muted:#8a9cc0;
  --accent:#1ec73d;--accent-bright:#24f048;--accent-dim:#0f7a22;
  --accent-glow:rgba(30,199,61,.12);
  --font-d:'Orbitron',sans-serif;--font-b:'Space Mono',monospace;
}
html,body{min-height:100%}
body{font-family:var(--font-b);background:var(--bg);color:var(--text);
     font-size:14px;line-height:1.6}
a{color:var(--accent);text-decoration:none}
a:hover{color:var(--accent-bright);text-decoration:underline}

/* ── Nav ── */
.nav{position:relative;overflow:hidden;background:#04050f;
     border-bottom:1px solid var(--border);height:52px;
     display:flex;align-items:center;padding:0 1.5rem;gap:1.25rem;z-index:10}
#sf{position:absolute;inset:0;width:100%;height:100%;z-index:0}
.nav>*{position:relative;z-index:1}
.nav-brand{font-family:var(--font-d);font-size:.875rem;font-weight:700;
           color:#fff;letter-spacing:.06em;text-decoration:none!important}
.nav-brand span{color:var(--accent)}
.nav-links{display:flex;gap:.1rem}
.nav-links a{color:#8fa8cc;font-size:.775rem;padding:.3rem .7rem;
             border-radius:4px;transition:background .15s,color .15s}
.nav-links a:hover,.nav-links a.active{background:rgba(255,255,255,.08);
  color:#fff;text-decoration:none}
.nav-search{margin-left:auto;display:flex}
.nav-search input{background:var(--surface2);border:1px solid var(--border);
  border-right:none;border-radius:4px 0 0 4px;color:var(--text);
  font-family:var(--font-b);font-size:.775rem;padding:.28rem .65rem;
  width:195px;outline:none}
.nav-search input:focus{border-color:var(--accent-dim)}
.nav-search button{background:var(--accent-dim);border:1px solid var(--accent-dim);
  border-radius:0 4px 4px 0;color:#fff;cursor:pointer;font-family:var(--font-b);
  font-size:.775rem;padding:.28rem .7rem;transition:background .15s}
.nav-search button:hover{background:var(--accent);border-color:var(--accent)}

/* ── Layout ── */
.wrap{max-width:900px;margin:0 auto;padding:2rem 1.5rem}

/* ── Breadcrumb ── */
.bc{font-size:.775rem;color:var(--muted);margin-bottom:1.25rem;
    display:flex;gap:.4rem;align-items:center;flex-wrap:wrap}
.bc a{color:var(--muted)}.bc a:hover{color:var(--accent)}
.bc .sep{opacity:.4}

/* ── Page title ── */
.pt h1{font-family:var(--font-d);font-size:1.35rem;font-weight:700;
       letter-spacing:.03em;margin-bottom:.25rem}
.pt .sub{font-size:.8rem;color:var(--muted);margin-bottom:1.5rem}

/* ── Category index ── */
.cat-section{margin-bottom:2rem}
.cat-section-hdr{font-family:var(--font-d);font-size:.7rem;font-weight:700;
  letter-spacing:.12em;text-transform:uppercase;color:var(--muted);
  border-bottom:1px solid var(--border);padding-bottom:.4rem;margin-bottom:.75rem}
.cat-grid{display:flex;flex-wrap:wrap;gap:.4rem}
.cat-chip{display:inline-flex;align-items:center;gap:.45rem;
  background:var(--surface);border:1px solid var(--border);border-radius:6px;
  padding:.4rem .85rem;color:var(--text);text-decoration:none!important;
  font-size:.8rem;transition:background .15s,border-color .15s}
.cat-chip:hover{background:var(--surface2);border-color:var(--accent-dim);color:#fff}
.cat-chip .n{color:var(--accent);font-size:.7rem;font-weight:700}
.cat-chip.parent{font-family:var(--font-d);font-size:.72rem}

/* ── Term list cards ── */
.term-list{display:flex;flex-direction:column;gap:.4rem}
.tc{background:var(--surface);border:1px solid var(--border);border-radius:8px;
    padding:.85rem 1.1rem;display:block;color:inherit;
    text-decoration:none!important;transition:background .15s,border-color .15s}
.tc:hover{background:var(--surface2);border-color:var(--accent-dim)}
.tc-name{font-family:var(--font-d);font-size:.85rem;font-weight:600;
         color:var(--accent);margin-bottom:.3rem}
.tc:hover .tc-name{color:var(--accent-bright)}
.tc-def{color:var(--muted);font-size:.8rem;line-height:1.55}

/* ── Term detail ── */
.term-heading{font-family:var(--font-d);font-size:1.5rem;font-weight:700;
  letter-spacing:.03em;color:#fff;margin-bottom:.75rem;line-height:1.3}
.term-meta{display:flex;flex-wrap:wrap;gap:.45rem;align-items:center;margin-bottom:1.5rem}
.meta-tag{font-size:.7rem;padding:2px 9px;border-radius:10px;display:inline-block}
.meta-cat{background:var(--surface2);border:1px solid var(--border);color:var(--muted)}
.meta-cat a{color:var(--muted)}.meta-cat a:hover{color:var(--accent);text-decoration:none}
.meta-adv{background:rgba(107,70,193,.15);border:1px solid rgba(107,70,193,.4);color:#b693e0}
.term-def{font-size:.9375rem;line-height:1.85;color:var(--text);
  background:var(--surface);border:1px solid var(--border);
  border-radius:8px;padding:1.25rem 1.5rem;margin-bottom:1.25rem}
.term-sec{margin-bottom:.75rem}
.term-sec-lbl{font-size:.68rem;font-weight:700;text-transform:uppercase;
  letter-spacing:.1em;color:var(--muted);margin-bottom:.4rem}
.alias-list{display:flex;flex-wrap:wrap;gap:.35rem}
.alias-chip{background:var(--surface2);border:1px solid var(--border);
  border-radius:12px;padding:2px 10px;font-size:.8rem;color:var(--muted)}

/* ── Prev/Next nav ── */
.term-nav{display:flex;justify-content:space-between;align-items:center;
  margin-top:2rem;padding-top:1rem;border-top:1px solid var(--border);gap:.75rem}
.tn-btn{color:var(--muted);font-size:.78rem;display:flex;align-items:center;
  gap:.35rem;padding:.4rem .75rem;border-radius:6px;
  border:1px solid var(--border);background:var(--surface);
  transition:background .15s,color .15s;max-width:46%;text-decoration:none!important}
.tn-btn:hover{background:var(--surface2);color:var(--text)}
.tn-term{font-family:var(--font-d);font-size:.68rem;color:var(--text);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}

/* ── Search ── */
.search-box{background:var(--surface);border:1px solid var(--border);
  border-radius:8px;padding:1rem 1.25rem;display:flex;gap:.5rem;margin-bottom:1.5rem}
.search-box input{flex:1;background:var(--surface2);border:1px solid var(--border);
  border-radius:4px;color:var(--text);font-family:var(--font-b);
  font-size:.875rem;padding:.45rem .75rem;outline:none}
.search-box input:focus{border-color:var(--accent-dim)}
.search-box button{background:var(--accent-dim);border:none;border-radius:4px;
  color:#fff;cursor:pointer;font-family:var(--font-b);font-size:.8rem;
  padding:.45rem 1.1rem;transition:background .15s}
.search-box button:hover{background:var(--accent)}
.result-count{font-size:.8rem;color:var(--muted);margin-bottom:.75rem}

/* ── Empty state ── */
.empty{text-align:center;padding:3rem 1rem;color:var(--muted)}
.empty .icon{font-size:2.5rem;margin-bottom:.75rem}

@media(max-width:640px){
  .wrap{padding:1.25rem 1rem}
  .nav-search{display:none}
  .term-heading{font-size:1.15rem}
}
"""

STARFIELD_JS = """
(function(){
  var c=document.getElementById('sf');
  if(!c)return;
  var ctx=c.getContext('2d'),W,H,stars=[];
  function rs(){W=c.width=c.offsetWidth;H=c.height=c.offsetHeight;}
  function ms(){stars=[];for(var i=0;i<80;i++)stars.push(
    {x:Math.random()*W,y:Math.random()*H,r:Math.random()*.8+.2,s:Math.random()*.22+.04});}
  function draw(){
    ctx.clearRect(0,0,W,H);
    for(var i=0;i<stars.length;i++){
      var s=stars[i];s.x-=s.s;if(s.x<-2){s.x=W+2;s.y=Math.random()*H;}
      ctx.globalAlpha=Math.random()*.35+.2;ctx.fillStyle='#fff';
      ctx.beginPath();ctx.arc(s.x,s.y,s.r,0,Math.PI*2);ctx.fill();
    }
    ctx.globalAlpha=1;requestAnimationFrame(draw);
  }
  rs();ms();draw();
  window.addEventListener('resize',function(){rs();ms();});
})();
"""


# ── Template ──────────────────────────────────────────────────────────────────

TMPL = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ page_title }} — Longboard Glossary</title>
{% if meta_desc %}
<meta name="description" content="{{ meta_desc }}">
{% endif %}
<style>{{ css }}</style>
</head>
<body>

<nav class="nav">
  <canvas id="sf"></canvas>
  <a class="nav-brand" href="{{ url_for('categories') }}">Longboard <span>Glossary</span></a>
  <div class="nav-links">
    <a href="{{ url_for('categories') }}"{% if view=='categories' %} class="active"{% endif %}>Browse</a>
  </div>
  <form class="nav-search" method="get" action="{{ url_for('search') }}">
    <input type="search" name="q" placeholder="Search terms…" value="{{ nav_q or '' }}" autocomplete="off">
    <button type="submit">→</button>
  </form>
</nav>

<div class="wrap">

{# ═══════════════════ CATEGORIES INDEX ═══════════════════ #}
{% if view == 'categories' %}

<div class="pt">
  <h1>Longboard Glossary</h1>
  <div class="sub">{{ total_terms }} canonical terms across {{ total_cats }} categories</div>
</div>

{% for parent, entries in groups.items() %}
<div class="cat-section">
  <div class="cat-section-hdr">{{ parent }}</div>
  <div class="cat-grid">
    {% for cat_name, count, slug in entries %}
    <a class="cat-chip{% if cat_name == parent %} parent{% endif %}"
       href="{{ url_for('category', cat_slug=slug) }}">
      {{ cat_display(cat_name) }}<span class="n">{{ count }}</span>
    </a>
    {% endfor %}
  </div>
</div>
{% endfor %}

{% if not groups %}
<div class="empty"><div class="icon">📖</div><p>No terms yet.</p></div>
{% endif %}


{# ═══════════════════ CATEGORY PAGE ══════════════════════ #}
{% elif view == 'category' %}

<div class="bc">
  <a href="{{ url_for('categories') }}">Browse</a>
  <span class="sep">›</span>
  <span>{{ cat_display(cat_name) }}</span>
</div>

<div class="pt">
  <h1>{{ cat_display(cat_name) }}</h1>
  <div class="sub">{{ terms|length }} term{{ 's' if terms|length != 1 }}</div>
</div>

{% if terms %}
<div class="term-list">
{% for t in terms %}
<a class="tc" href="{{ url_for('term_page', slug=slugify(t.term)) }}">
  <div class="tc-name">{{ t.term }}</div>
  {% if t.definition %}
  <div class="tc-def">{{ first_sentence(t.definition) }}</div>
  {% endif %}
</a>
{% endfor %}
</div>
{% else %}
<div class="empty"><div class="icon">📂</div><p>No terms in this category.</p></div>
{% endif %}


{# ═══════════════════ TERM DETAIL ════════════════════════ #}
{% elif view == 'term' %}

<div class="bc">
  <a href="{{ url_for('categories') }}">Browse</a>
  {% if term.category %}
  <span class="sep">›</span>
  <a href="{{ url_for('category', cat_slug=slugify(term.category)) }}">{{ cat_display(term.category) }}</a>
  {% endif %}
  <span class="sep">›</span>
  <span>{{ term.term }}</span>
</div>

<div class="term-heading">{{ term.term }}</div>

<div class="term-meta">
  {% if term.category %}
  <span class="meta-tag meta-cat">
    <a href="{{ url_for('category', cat_slug=slugify(term.category)) }}">{{ cat_display(term.category) }}</a>
  </span>
  {% endif %}
  {% if term.esoteric_rating and term.esoteric_rating >= 4 %}
  <span class="meta-tag meta-adv">Advanced</span>
  {% endif %}
</div>

{% if term.definition %}
<div class="term-def">{{ term.definition }}</div>
{% endif %}

{% if term.also_called %}
<div class="term-sec">
  <div class="term-sec-lbl">Also known as</div>
  <div class="alias-list">
    {% for alias in term.also_called.split(',') %}{% set alias = alias.strip() %}{% if alias %}
    <span class="alias-chip">{{ alias }}</span>
    {% endif %}{% endfor %}
  </div>
</div>
{% endif %}

<div class="term-nav">
  {% if prev_term %}
  <a class="tn-btn" href="{{ url_for('term_page', slug=slugify(prev_term.term)) }}">
    ← <span class="tn-term">{{ prev_term.term }}</span>
  </a>
  {% else %}<span></span>{% endif %}

  {% if next_term %}
  <a class="tn-btn" href="{{ url_for('term_page', slug=slugify(next_term.term)) }}" style="justify-content:flex-end">
    <span class="tn-term">{{ next_term.term }}</span> →
  </a>
  {% else %}<span></span>{% endif %}
</div>


{# ═══════════════════ SEARCH ═════════════════════════════ #}
{% elif view == 'search' %}

<div class="bc">
  <a href="{{ url_for('categories') }}">Browse</a>
  <span class="sep">›</span>
  <span>Search</span>
</div>

<div class="search-box">
  <form method="get" action="{{ url_for('search') }}" style="display:contents">
    <input type="search" name="q" value="{{ q or '' }}" placeholder="Search terms…" autofocus autocomplete="off">
    <button type="submit">Search</button>
  </form>
</div>

{% if q %}
  {% if results %}
  <p class="result-count">{{ results|length }} result{{ 's' if results|length != 1 }} for "<strong>{{ q }}</strong>"</p>
  <div class="term-list">
  {% for t in results %}
  <a class="tc" href="{{ url_for('term_page', slug=slugify(t.term)) }}">
    <div class="tc-name">{{ t.term }}</div>
    {% if t.definition %}
    <div class="tc-def">{{ first_sentence(t.definition) }}</div>
    {% endif %}
  </a>
  {% endfor %}
  </div>
  {% else %}
  <div class="empty">
    <div class="icon">🔍</div>
    <p>No terms found for "<strong>{{ q }}</strong>".</p>
    <p style="margin-top:.5rem;font-size:.8rem">
      <a href="{{ url_for('categories') }}">Browse all categories</a>
    </p>
  </div>
  {% endif %}
{% endif %}


{# ═══════════════════ 404 ════════════════════════════════ #}
{% elif view == '404' %}

<div class="empty" style="padding-top:4rem">
  <div class="icon">🛹</div>
  <p style="font-family:var(--font-d);font-size:.9rem;margin-bottom:.75rem">Term not found</p>
  <p style="font-size:.8rem;color:var(--muted)">
    <a href="{{ url_for('categories') }}">Browse all categories</a> or
    <a href="{{ url_for('search') }}">search the glossary</a>.
  </p>
</div>

{% endif %}

</div>{# /wrap #}

<script>{{ starfield_js }}</script>
</body>
</html>"""


# ── Template globals ──────────────────────────────────────────────────────────

@app.template_global()
def slugify_tmpl(s):
    return slugify(s)


# Pass helpers into all template renders via a shared kwargs dict
def _render(view, page_title, meta_desc='', nav_q='', **kwargs):
    return render_template_string(
        TMPL,
        view=view,
        page_title=page_title,
        meta_desc=meta_desc,
        nav_q=nav_q,
        css=CSS,
        starfield_js=STARFIELD_JS,
        slugify=slugify,
        cat_display=cat_display,
        first_sentence=first_sentence,
        **kwargs,
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return redirect(url_for('categories'))


@app.route('/categories')
def categories():
    db = get_db()
    groups = get_categories_grouped(db)
    total_terms = db.execute(
        "SELECT COUNT(*) FROM terms WHERE status='canonical'"
    ).fetchone()[0]
    total_cats = db.execute(
        "SELECT COUNT(DISTINCT category) FROM terms "
        "WHERE status='canonical' AND category IS NOT NULL AND TRIM(category) != ''"
    ).fetchone()[0]
    return _render(
        'categories', 'Browse',
        groups=groups,
        total_terms=total_terms,
        total_cats=total_cats,
    )


@app.route('/category/<cat_slug>')
def category(cat_slug):
    db = get_db()
    cat_name, terms = get_category_terms(db, cat_slug)
    if cat_name is None:
        return _render('404', 'Category not found'), 404
    return _render(
        'category',
        cat_display(cat_name),
        meta_desc=f'Longboard glossary terms in the {cat_display(cat_name)} category.',
        cat_name=cat_name,
        terms=terms,
    )


@app.route('/search')
def search():
    q = request.args.get('q', '').strip()
    db = get_db()

    if not q:
        return redirect(url_for('categories'))

    results = search_terms(db, q)

    # Top result is an exact term name match → go straight to the term page
    if results and results[0]['term'].lower() == q.lower():
        return redirect(url_for('term_page', slug=slugify(results[0]['term'])))

    return _render(
        'search', f'Search: {q}' if q else 'Search',
        nav_q=q,
        q=q,
        results=results,
    )


@app.route('/<slug>')
def term_page(slug):
    db = get_db()
    term, redirect_slug = resolve_slug(db, slug)

    if term is None:
        return _render('404', 'Not found'), 404

    if redirect_slug and redirect_slug != slug:
        return redirect(url_for('term_page', slug=redirect_slug), 301)

    prev_term, next_term = get_adjacent(db, term['id'])

    # Build a clean meta description from the definition
    defn = term.get('definition') or ''
    meta = first_sentence(defn, max_len=160)

    return _render(
        'term', term['term'],
        meta_desc=meta,
        nav_q='',
        term=term,
        prev_term=prev_term,
        next_term=next_term,
    )


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    global DB_PATH
    script_dir  = os.path.dirname(os.path.abspath(__file__))
    # Default DB path: 3 levels up to Projects/, then into the Wiki project
    default_db  = os.path.join(
        script_dir, '..', '..', '..',
        'The Ultimate Longboard Wiki Project',
        'Wiki', 'Glossary', 'glossary.db'
    )
    p = argparse.ArgumentParser(description='Glossary Reader App')
    p.add_argument('--db',    default=default_db, help='Path to glossary.db')
    p.add_argument('--port',  type=int, default=5001)
    p.add_argument('--debug', action='store_true')
    args = p.parse_args()

    DB_PATH = os.path.abspath(args.db)
    if not os.path.exists(DB_PATH):
        print(f'Error: database not found at {DB_PATH}')
        print('Check the --db path or confirm glossary.db exists.')
        return 1

    # Startup sanity check
    try:
        conn = sqlite3.connect(DB_PATH)
        count = conn.execute("SELECT COUNT(*) FROM terms WHERE status='canonical'").fetchone()[0]
        conn.close()
        print(f'Glossary Reader App')
        print(f'Database    : {DB_PATH}')
        print(f'Canonical   : {count} terms')
        print(f'Open        : http://localhost:{args.port}')
        print()
    except Exception as e:
        print(f'Error reading database: {e}')
        return 1

    app.run(host='0.0.0.0', port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()