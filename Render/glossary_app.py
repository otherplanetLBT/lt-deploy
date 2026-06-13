#!/usr/bin/env python3
"""
Glossary Reader — The Ultimate Longboard Wiki Project
Public-facing Flask app serving glossary terms. Read-only — never writes to the DB.

v2: glossary-first landing (alphabetical, esoteric-1 default), Advanced /
Third-eye toggles, tag-hierarchy filtering, mode-aware prev/next, search nudge.
Design spec: Design Documents/GLOSSARY_APP.md (single source of truth).

Usage:
    pip install flask
    python glossary_app.py [--db <path>] [--port 5001] [--debug] [--canonical-only]

    --canonical-only   hide candidate terms (launch state).
                       Default INCLUDES candidates rendered as canonical
                       (design-phase preview at full scale).
                       Env override: GLOSSARY_CANONICAL_ONLY=1

Browse at:  http://localhost:5001 (local dev — run deploy/Glossary/glossary_app.py directly)
Deployment: tools.longboardtechnology.com/glossary (mounted via DispatcherMiddleware
in site_app.py; gunicorn runs site_app:application, not this module directly).

Env vars (production):
    GLOSSARY_DB_PATH         Path to glossary.db. Default: glossary.db beside this file.
    GLOSSARY_CANONICAL_ONLY  Set "1" to hide candidates (launch state).
                             Unset = candidates shown (design-preview default).
"""

import argparse
import json
import os
import re
import sqlite3

from flask import Flask, g, redirect, render_template_string, request, url_for

app = Flask(__name__)
app.secret_key = 'lt-glossary-reader-2026'
# ── WSGI / production init ─────────────────────────────────────────────────────
# DB_PATH and INCLUDE_CANDIDATES must be set before the first request.
# main() sets them for CLI dev; reading env vars here means gunicorn can import
# this module and have them ready without ever calling main().

_script_dir = os.path.dirname(os.path.abspath(__file__))
DB_PATH: str = os.environ.get('GLOSSARY_DB_PATH',
                               os.path.join(_script_dir, 'glossary.db'))
INCLUDE_CANDIDATES: bool = os.environ.get('GLOSSARY_CANONICAL_ONLY', '') != '1'


# ── Tier config ───────────────────────────────────────────────────────────────
# One constant feeds the server queries AND the client toggle logic.
# Retuning thresholds later is a one-line edit.

TIERS = {
    'default':   [1],          # always visible
    'advanced':  [2, 3, 4],    # + Advanced toggle
    'third_eye': [5],          # + Third-eye Open (requires Advanced)
}


# ── Category tag hierarchy ────────────────────────────────────────────────────
# Display-layer only (DB is untouched). Atomic tags come from comma-splitting
# the DB's compound category strings. Parents filter to themselves plus all
# descendants. Tags found in the DB but missing here fall back to top-level
# with a startup warning. Red-penned 2026-06-07; Trucks←Parts←Hardware nest
# is provisional pending preview validation.

CATEGORY_TREE = {
    'Trucks':      {'Bushings': {}, 'Parts': {'Hardware': {}}},
    'Geometry':    {},
    'Wheels':      {'Bearings': {}},
    'Decks':       {'Deck Profile': {}, 'Deck Shape': {}, 'Deck Shapes': {},
                    'Deck Setup': {}},
    'Materials':   {},
    'Technique':   {'Techniques': {}, 'Riding technique': {}, 'How to Ride': {},
                    'How-to-Ride': {}},
    'Disciplines': {'DH': {}, 'LDP': {}, 'Freeride': {}, 'Slalom': {},
                    'Freestyle': {}, 'Racing': {}, 'Dancing': {}},
    'Esk8':        {'Motor': {}, 'Battery': {}, 'Drive Train': {},
                    'Motor Control': {}, 'Software': {}, 'DC Electrical': {},
                    'Electric Longboard': {}},
    'Safety':      {'FAR': {}, 'Equipment': {}, 'First Aid': {}, 'Helmets': {},
                    'Helmet standards': {}, 'Protective gear': {}},
    'Physics':     {},
    'History':     {'Vendor': {}, 'Brands': {}, 'Organizations': {}},
    'Cultural':    {},
    'People':      {},
    'DIY':         {'Board Building': {}, 'Maintenance': {}},
    'Setup':       {},
    'Events':      {'Venues': {}},
    'General':     {},
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def slugify(s: str) -> str:
    s = s.lower()
    s = re.sub(r'[^a-z0-9]+', '-', s)
    return s.strip('-')


def split_tags(cat) -> list:
    """'Geometry, Trucks' → ['Geometry', 'Trucks'] (atomic tags)."""
    return [t.strip() for t in (cat or '').split(',') if t.strip()]


def first_sentence(text: str, max_len: int = 150) -> str:
    if not text:
        return ''
    m = re.match(r'(.+?[.!?])(?:\s|$)', text)
    if m:
        return m.group(1)
    return text[:max_len].rstrip() + ('…' if len(text) > max_len else '')


# Flattened tag model: NODES[slug] = {name, children[slugs], subtree[slugs incl self]}
NODES: dict = {}
TOP: list = []           # top-level slugs, tree order; unmapped appended at startup


def _subtree_slugs(name, sub) -> list:
    out = [slugify(name)]
    for c, s in sub.items():
        out += _subtree_slugs(c, s)
    return out


def _walk_tree(name, sub):
    NODES[slugify(name)] = {
        'name': name,
        'children': [slugify(c) for c in sub],
        'subtree': _subtree_slugs(name, sub),
    }
    for c, s in sub.items():
        _walk_tree(c, s)


for _p, _s in CATEGORY_TREE.items():
    _walk_tree(_p, _s)
    TOP.append(slugify(_p))


def register_unmapped_tags(db_path: str):
    """Tags in the DB but absent from CATEGORY_TREE become top-level chips.
    Startup warning keeps drift visible, never silent."""
    con = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
    tags = {}
    for (cat,) in con.execute(
            f"SELECT category FROM terms WHERE {visible_where()} "
            "AND category IS NOT NULL"):
        for t in split_tags(cat):
            tags.setdefault(slugify(t), t)
    con.close()
    unmapped = sorted((s, n) for s, n in tags.items() if s not in NODES)
    for s, n in unmapped:
        NODES[s] = {'name': n, 'children': [], 'subtree': [s]}
        TOP.append(s)
    if unmapped:
        print(f'WARNING: {len(unmapped)} tag(s) not in CATEGORY_TREE '
              f'(shown top-level): {", ".join(n for _, n in unmapped)}')


# Populate the tag tree at import time so the filter bar is ready on the first
# WSGI request. Skipped silently when the DB isn't present (test / lint env).
if DB_PATH and os.path.exists(DB_PATH):
    try:
        register_unmapped_tags(DB_PATH)
    except Exception as _exc:
        print(f'WARNING: glossary tag registration failed at startup: {_exc}')


# ── Mode handling ─────────────────────────────────────────────────────────────

def mode_args():
    """Read mode context from the query string. eye requires adv."""
    adv = request.args.get('adv') == '1'
    eye = adv and request.args.get('eye') == '1'
    cat = request.args.get('cat', '').strip()
    if cat and cat not in NODES:
        cat = ''
    return adv, eye, cat


def mode_tiers(adv: bool, eye: bool) -> list:
    tiers = list(TIERS['default'])
    if adv:
        tiers += TIERS['advanced']
        if eye:
            tiers += TIERS['third_eye']
    return tiers


def mode_params(adv, eye, cat=''):
    """Query-param dict for propagating mode context through links."""
    p = {}
    if adv:
        p['adv'] = 1
        if eye:
            p['eye'] = 1
    if cat:
        p['cat'] = cat
    return p


def term_tier(t) -> int:
    """Missing rating → advanced bucket (never leaks into the default view)."""
    return t['esoteric_rating'] if t['esoteric_rating'] else max(TIERS['advanced'])


def term_matches(t, tiers, cat) -> bool:
    if term_tier(t) not in tiers:
        return False
    if cat:
        allowed = set(NODES[cat]['subtree'])
        if not any(slugify(x) in allowed for x in split_tags(t['category'])):
            return False
    return True


# ── Database ──────────────────────────────────────────────────────────────────

def visible_where() -> str:
    """Status clause. Candidates (with rating + definition) render as canonical
    while INCLUDE_CANDIDATES is on — design-phase preview at full scale."""
    if INCLUDE_CANDIDATES:
        return ("((status='canonical') OR (status='candidate' "
                "AND esoteric_rating IS NOT NULL "
                "AND definition IS NOT NULL AND definition!=''))")
    return "status='canonical'"


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(f'file:{DB_PATH}?mode=ro', uri=True)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_=None):
    db = g.pop('db', None)
    if db:
        db.close()


def all_visible_terms(db) -> list:
    return db.execute(
        f"SELECT * FROM terms WHERE {visible_where()} "
        "ORDER BY term COLLATE NOCASE"
    ).fetchall()


def resolve_slug(db, slug: str):
    """slug → (term_dict, redirect_slug|None) | (None, None).
    Order: term name → also_called alias → redirects table."""
    terms = db.execute(f"SELECT * FROM terms WHERE {visible_where()}").fetchall()
    for t in terms:
        if slugify(t['term']) == slug:
            return dict(t), None
    for t in terms:
        if t['also_called']:
            for alias in (a.strip() for a in t['also_called'].split(',') if a.strip()):
                if slugify(alias) == slug:
                    return dict(t), slugify(t['term'])
    for r in db.execute("SELECT synonym, canonical_term FROM redirects").fetchall():
        if slugify(r['synonym']) == slug:
            target = db.execute(
                f"SELECT * FROM terms WHERE term=? COLLATE NOCASE AND {visible_where()}",
                (r['canonical_term'],)).fetchone()
            if target:
                return dict(target), slugify(target['term'])
    return None, None


def get_adjacent(db, term_id: int, adv, eye, cat):
    """Mode-aware prev/next: adjacency within the VISIBLE set (tiers + filter),
    alphabetical — 'next' never lands on an invisible term."""
    tiers = mode_tiers(adv, eye)
    rows = all_visible_terms(db)
    visible = [r for r in rows if term_matches(r, tiers, cat) or r['id'] == term_id]
    ids = [r['id'] for r in visible]
    try:
        idx = ids.index(term_id)
    except ValueError:
        return None, None
    prev = dict(visible[idx - 1]) if idx > 0 else None
    nxt = dict(visible[idx + 1]) if idx < len(ids) - 1 else None
    return prev, nxt


def search_terms(db, q: str) -> list:
    """Search across EVERYTHING visible_where allows (all tiers);
    the route partitions results by mode. exact > prefix > substring."""
    q_l = q.lower().strip()
    if not q_l:
        return []
    exact, prefix, sub = [], [], []
    for t in all_visible_terms(db):
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
  --eye:#8b5fd6;--eye-bright:#b693e0;--eye-dim:rgba(107,70,193,.18);
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

/* ── Page title + mode controls ── */
.pt{display:flex;align-items:flex-end;justify-content:space-between;
    flex-wrap:wrap;gap:.75rem;margin-bottom:1.25rem}
.pt h1{font-family:var(--font-d);font-size:1.35rem;font-weight:700;
       letter-spacing:.03em;margin-bottom:.25rem}
.pt .sub{font-size:.8rem;color:var(--muted)}
.modes{display:flex;gap:.5rem;align-items:center}
.mode-btn{font-family:var(--font-d);font-size:.62rem;font-weight:700;
  letter-spacing:.14em;text-transform:uppercase;cursor:pointer;
  background:transparent;border:1px solid var(--border);border-radius:4px;
  color:var(--muted);padding:.45rem .8rem;transition:color .15s,border-color .15s,background .15s}
.mode-btn:hover{color:var(--accent);border-color:var(--accent-dim)}
.mode-btn.on{color:var(--accent);border-color:var(--accent);
  background:var(--accent-glow)}
.mode-btn.eye{display:none}
.mode-btn.eye.avail{display:inline-block}
.mode-btn.eye:hover{color:var(--eye-bright);border-color:var(--eye)}
.mode-btn.eye.on{color:var(--eye-bright);border-color:var(--eye);
  background:var(--eye-dim)}

/* ── Search box (landing) ── */
.search-box{background:var(--surface);border:1px solid var(--border);
  border-radius:8px;padding:1rem 1.25rem;display:flex;gap:.5rem;margin-bottom:1.25rem}
.search-box input{flex:1;background:var(--surface2);border:1px solid var(--border);
  border-radius:4px;color:var(--text);font-family:var(--font-b);
  font-size:.875rem;padding:.45rem .75rem;outline:none}
.search-box input:focus{border-color:var(--accent-dim)}
.search-box button{background:var(--accent-dim);border:none;border-radius:4px;
  color:#fff;cursor:pointer;font-family:var(--font-b);font-size:.8rem;
  padding:.45rem 1.1rem;transition:background .15s}
.search-box button:hover{background:var(--accent)}

/* ── Filter bar (advanced only) ── */
.filterbar{display:none;margin-bottom:1.25rem;border:1px solid var(--border);
  border-radius:8px;background:var(--surface);padding:.85rem 1rem;
  opacity:0;transform:translateY(-4px);transition:opacity .15s,transform .15s}
.filterbar.show{display:block}
.filterbar.in{opacity:1;transform:none}
.fb-lbl{font-family:var(--font-d);font-size:.6rem;font-weight:700;
  letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin-bottom:.5rem}
.fb-row{display:flex;flex-wrap:wrap;gap:.35rem}
.fb-row+.fb-row{margin-top:.5rem;padding-top:.5rem;border-top:1px dashed var(--border)}
.chip{font-size:.72rem;cursor:pointer;background:var(--surface2);
  border:1px solid var(--border);border-radius:12px;color:var(--muted);
  padding:.18rem .7rem;transition:color .15s,border-color .15s,background .15s}
.chip:hover{color:var(--accent);border-color:var(--accent-dim)}
.chip.on{color:#04130a;background:var(--accent);border-color:var(--accent);font-weight:700}
.chip .n{opacity:.7;font-size:.65rem;margin-left:.3rem}
.chip.on .n{opacity:.85}

/* ── Term list ── */
.term-list{display:flex;flex-direction:column;gap:.4rem}
.entry{background:var(--surface);border:1px solid var(--border);border-radius:8px;
    padding:.85rem 1.1rem;transition:background .15s,border-color .15s}
.entry:hover{background:var(--surface2);border-color:var(--accent-dim)}
.entry.t5{border-left:2px solid var(--eye)}
.entry-head{display:flex;align-items:baseline;gap:.6rem;flex-wrap:wrap}
.entry-name{font-family:var(--font-d);font-size:.85rem;font-weight:600;
         color:var(--accent)}
.entry-name:hover{color:var(--accent-bright)}
.entry-tags{display:flex;flex-wrap:wrap;gap:.25rem;margin-left:auto}
.tag{font-size:.62rem;padding:1px 8px;border-radius:9px;
  border:1px solid var(--border);color:var(--muted);background:transparent;
  pointer-events:none}
body.adv .tag{pointer-events:auto;cursor:pointer;transition:color .15s,border-color .15s}
body.adv .tag:hover{color:var(--accent);border-color:var(--accent-dim)}
.entry-def{color:var(--muted);font-size:.8rem;line-height:1.55;margin-top:.3rem}
.entry-def .full{display:none}
.entry.open .entry-def .short{display:none}
.entry.open .entry-def .full{display:inline}
.more{color:var(--accent);cursor:pointer;font-size:.72rem;margin-left:.3rem;
  user-select:none}
.more:hover{color:var(--accent-bright)}

/* ── Term detail ── */
.bc{font-size:.775rem;color:var(--muted);margin-bottom:1.25rem;
    display:flex;gap:.4rem;align-items:center;flex-wrap:wrap}
.bc a{color:var(--muted)}.bc a:hover{color:var(--accent)}
.bc .sep{opacity:.4}
.term-heading{font-family:var(--font-d);font-size:1.5rem;font-weight:700;
  letter-spacing:.03em;color:#fff;margin-bottom:.75rem;line-height:1.3}
.term-meta{display:flex;flex-wrap:wrap;gap:.45rem;align-items:center;margin-bottom:1.5rem}
.meta-tag{font-size:.7rem;padding:2px 9px;border-radius:10px;display:inline-block}
.meta-cat{background:var(--surface2);border:1px solid var(--border);color:var(--muted)}
.meta-cat a{color:var(--muted)}.meta-cat a:hover{color:var(--accent);text-decoration:none}
.meta-eso{background:transparent;border:1px dashed var(--border);color:var(--muted)}
.meta-adv{background:var(--eye-dim);border:1px solid var(--eye);color:var(--eye-bright)}
.term-def{font-size:.9375rem;line-height:1.85;color:var(--text);
  background:var(--surface);border:1px solid var(--border);
  border-radius:8px;padding:1.25rem 1.5rem;margin-bottom:1.25rem}
.term-sec{margin-bottom:.75rem}
.term-sec-lbl{font-size:.68rem;font-weight:700;text-transform:uppercase;
  letter-spacing:.1em;color:var(--muted);margin-bottom:.4rem}
.alias-list{display:flex;flex-wrap:wrap;gap:.35rem}
.alias-chip{background:var(--surface2);border:1px solid var(--border);
  border-radius:12px;padding:2px 10px;font-size:.8rem;color:var(--muted)}

/* ── Prev/Next ── */
.term-nav{display:flex;justify-content:space-between;align-items:center;
  margin-top:2rem;padding-top:1rem;border-top:1px solid var(--border);gap:.75rem}
.tn-btn{color:var(--muted);font-size:.78rem;display:flex;align-items:center;
  gap:.35rem;padding:.4rem .75rem;border-radius:6px;
  border:1px solid var(--border);background:var(--surface);
  transition:background .15s,color .15s;max-width:46%;text-decoration:none!important}
.tn-btn:hover{background:var(--surface2);color:var(--text)}
.tn-term{font-family:var(--font-d);font-size:.68rem;color:var(--text);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}

/* ── Search page ── */
.result-count{font-size:.8rem;color:var(--muted);margin-bottom:.75rem}
.nudge{margin-top:1rem;padding:.7rem 1rem;border:1px dashed var(--border);
  border-radius:8px;font-size:.8rem;color:var(--muted)}
.nudge a{font-family:var(--font-d);font-size:.66rem;letter-spacing:.1em;
  text-transform:uppercase}

/* ── Empty state ── */
.empty{text-align:center;padding:3rem 1rem;color:var(--muted)}
.empty .icon{font-size:2.5rem;margin-bottom:.75rem}

@media(max-width:640px){
  .wrap{padding:1.25rem 1rem}
  .nav-search{display:none}
  .term-heading{font-size:1.15rem}
  .entry-tags{margin-left:0;width:100%}
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

# Client-side mode/filter logic for the landing page.
GLOSSARY_JS = r"""
(function(){
  var TIERS = window.GLOSSARY_TIERS, NODES = window.GLOSSARY_NODES, TOP = window.GLOSSARY_TOP;
  var state = {adv:false, eye:false, cat:''};

  // restore from URL
  var sp = new URLSearchParams(location.search);
  state.adv = sp.get('adv') === '1';
  state.eye = state.adv && sp.get('eye') === '1';
  var cat0 = sp.get('cat') || '';
  if (cat0 && NODES[cat0]) state.cat = cat0;

  var entries = [].slice.call(document.querySelectorAll('.entry'));
  var data = entries.map(function(el){
    return {el:el, tier:+el.dataset.tier,
            tags:(el.dataset.tags||'').split(' ').filter(Boolean)};
  });

  function visibleTiers(){
    var t = TIERS.default.slice();
    if (state.adv){ t = t.concat(TIERS.advanced);
      if (state.eye) t = t.concat(TIERS.third_eye); }
    return t;
  }
  function inSubtree(tags, cat){
    if (!cat) return true;
    var sub = NODES[cat].subtree;
    return tags.some(function(tg){ return sub.indexOf(tg) >= 0; });
  }

  var btnAdv = document.getElementById('btn-adv'),
      btnEye = document.getElementById('btn-eye'),
      fbar   = document.getElementById('filterbar'),
      fbTop  = document.getElementById('fb-top'),
      fbSub  = document.getElementById('fb-sub'),
      countEl= document.getElementById('term-count');

  function chipHtml(slug, n, on){
    var node = NODES[slug];
    return '<button class="chip'+(on?' on':'')+'" data-cat="'+slug+'">'
         + node.name + '<span class="n">' + n + '</span></button>';
  }

  function counts(tiers){
    var m = {};
    data.forEach(function(d){
      if (tiers.indexOf(d.tier) < 0) return;
      var seen = {};
      d.tags.forEach(function(tg){
        for (var slug in NODES){
          if (!seen[slug] && NODES[slug].subtree.indexOf(tg) >= 0){
            seen[slug] = true; m[slug] = (m[slug]||0)+1;
          }
        }
      });
    });
    return m;
  }

  function renderChips(){
    var tiers = visibleTiers(), n = counts(tiers), html = '';
    TOP.forEach(function(slug){
      if (!n[slug]) return;
      var on = state.cat === slug ||
               (state.cat && NODES[slug].subtree.indexOf(state.cat) >= 0);
      html += chipHtml(slug, n[slug], on);
    });
    fbTop.innerHTML = html;
    // sub-row: children of the active node (drill-in)
    var subHtml = '';
    if (state.cat){
      var kids = NODES[state.cat].children;
      kids.forEach(function(k){ if (n[k]) subHtml += chipHtml(k, n[k], false); });
      if (subHtml) subHtml = '<span class="fb-lbl" style="margin:0 .4rem 0 0">'
        + NODES[state.cat].name + ' ›</span>' + subHtml;
    }
    fbSub.innerHTML = subHtml;
    fbSub.style.display = subHtml ? 'flex' : 'none';
  }

  function anchorEntry(){
    // If the mode controls are still in view the user is at the top of the
    // list: keep the page where it is — anchoring from here shoves the
    // viewport down past the new alphabetically-earlier entries.
    var hdr = document.querySelector('.pt');
    if (hdr && hdr.getBoundingClientRect().bottom > 0) return null;
    for (var i = 0; i < data.length; i++){
      var r = data[i].el.getBoundingClientRect();
      if (r.bottom > 60 && data[i].el.style.display !== 'none')
        return {el:data[i].el, top:r.top};
    }
    return null;
  }

  function apply(keepAnchor){
    var a = keepAnchor ? anchorEntry() : null;
    var tiers = visibleTiers(), shown = 0;
    data.forEach(function(d){
      var ok = tiers.indexOf(d.tier) >= 0 && inSubtree(d.tags, state.cat);
      d.el.style.display = ok ? '' : 'none';
      if (ok) shown++;
    });
    countEl.textContent = shown;
    document.body.classList.toggle('adv', state.adv);
    btnAdv.classList.toggle('on', state.adv);
    btnEye.classList.toggle('avail', state.adv);
    btnEye.classList.toggle('on', state.eye);
    fbar.classList.toggle('show', state.adv);
    requestAnimationFrame(function(){ fbar.classList.toggle('in', state.adv); });
    renderChips();
    syncUrl();
    if (a){
      var r = a.el.getBoundingClientRect();
      window.scrollBy(0, r.top - a.top);
    }
  }

  function params(){
    var p = new URLSearchParams();
    if (state.adv) p.set('adv','1');
    if (state.eye) p.set('eye','1');
    if (state.cat) p.set('cat',state.cat);
    var s = p.toString();
    return s ? '?'+s : '';
  }
  function syncUrl(){
    history.replaceState(null,'',location.pathname + params());
    // carry mode context into permalinks + search form
    var f = document.getElementById('search-form');
    if (f){
      f.querySelector('[name=adv]').value = state.adv ? '1' : '';
      f.querySelector('[name=eye]').value = state.eye ? '1' : '';
    }
  }

  btnAdv.addEventListener('click', function(){
    state.adv = !state.adv;
    if (!state.adv){ state.eye = false; state.cat = ''; }
    apply(true);
  });
  btnEye.addEventListener('click', function(){
    state.eye = !state.eye; apply(true);
  });
  fbar.addEventListener('click', function(e){
    var c = e.target.closest('.chip');
    if (!c) return;
    var slug = c.dataset.cat;
    state.cat = (state.cat === slug) ? '' : slug;
    apply(false);
  });
  document.querySelector('.term-list').addEventListener('click', function(e){
    var more = e.target.closest('.more');
    if (more){
      more.closest('.entry').classList.toggle('open');
      more.textContent = more.closest('.entry').classList.contains('open') ? 'less' : 'more';
      return;
    }
    var tag = e.target.closest('.tag');
    if (tag && state.adv){
      state.cat = (state.cat === tag.dataset.cat) ? '' : tag.dataset.cat;
      apply(false);
      return;
    }
    var link = e.target.closest('a.entry-name');
    if (link) link.href = link.pathname + params();
  });

  apply(false);
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
<style>{{ css|safe }}</style>
</head>
<body>

<nav class="nav">
  <canvas id="sf"></canvas>
  <a class="nav-brand" href="{{ url_for('index') }}">Longboard <span>Glossary</span></a>
  <form class="nav-search" method="get" action="{{ url_for('search') }}">
    <input type="search" name="q" placeholder="Search terms…" value="{{ nav_q or '' }}" autocomplete="off">
    {% if adv %}<input type="hidden" name="adv" value="1">{% endif %}
    {% if eye %}<input type="hidden" name="eye" value="1">{% endif %}
    <button type="submit">→</button>
  </form>
</nav>

<div class="wrap">

{# ═══════════════════ GLOSSARY (LANDING) ═════════════════ #}
{% if view == 'index' %}

<div class="pt">
  <div>
    <h1>Longboard Glossary</h1>
    <div class="sub"><span id="term-count">…</span> terms, A→Z</div>
  </div>
  <div class="modes">
    <button class="mode-btn" id="btn-adv" type="button">Advanced</button>
    <button class="mode-btn eye" id="btn-eye" type="button">Third-eye Open</button>
  </div>
</div>

<div class="search-box">
  <form method="get" action="{{ url_for('search') }}" style="display:contents" id="search-form">
    <input type="search" name="q" placeholder="Search the glossary…" autocomplete="off">
    <input type="hidden" name="adv" value=""><input type="hidden" name="eye" value="">
    <button type="submit">Search</button>
  </form>
</div>

<div class="filterbar" id="filterbar">
  <div class="fb-lbl">Filter by category</div>
  <div class="fb-row" id="fb-top"></div>
  <div class="fb-row" id="fb-sub" style="display:none"></div>
</div>

<div class="term-list">
{% for e in entries %}
<div class="entry{% if e.tier == 5 %} t5{% endif %}" data-tier="{{ e.tier }}" data-tags="{{ e.tag_slugs|join(' ') }}">
  <div class="entry-head">
    <a class="entry-name" href="{{ url_for('term_page', slug=e.slug) }}">{{ e.term }}</a>
    <span class="entry-tags">
      {% for i in range(e.tags|length) %}
      <button class="tag" type="button" data-cat="{{ e.tag_slugs[i] }}">{{ e.tags[i] }}</button>
      {% endfor %}
    </span>
  </div>
  {% if e.def_short %}
  <div class="entry-def">
    <span class="short">{{ e.def_short }}</span><span class="full">{{ e.def_full }}</span>
    {%- if e.def_full != e.def_short %}<span class="more">more</span>{% endif %}
  </div>
  {% endif %}
</div>
{% endfor %}
</div>

<script>
window.GLOSSARY_TIERS = {{ tiers_json|safe }};
window.GLOSSARY_NODES = {{ nodes_json|safe }};
window.GLOSSARY_TOP   = {{ top_json|safe }};
</script>


{# ═══════════════════ TERM DETAIL ════════════════════════ #}
{% elif view == 'term' %}

<div class="bc">
  <a href="{{ url_for('index', **mode_p) }}">Glossary</a>
  <span class="sep">›</span>
  <span>{{ term.term }}</span>
</div>

<div class="term-heading">{{ term.term }}</div>

<div class="term-meta">
  {% for i in range(tags|length) %}
  <span class="meta-tag meta-cat">
    <a href="{{ url_for('index', adv=1, eye=(1 if eye else None), cat=tag_slugs[i]) }}">{{ tags[i] }}</a>
  </span>
  {% endfor %}
  {% if term.esoteric_rating %}
  <span class="meta-tag meta-eso">esoteric {{ term.esoteric_rating }}/5</span>
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
  <a class="tn-btn" href="{{ url_for('term_page', slug=slugify(prev_term.term), **mode_p) }}">
    ← <span class="tn-term">{{ prev_term.term }}</span>
  </a>
  {% else %}<span></span>{% endif %}

  {% if next_term %}
  <a class="tn-btn" href="{{ url_for('term_page', slug=slugify(next_term.term), **mode_p) }}" style="justify-content:flex-end">
    <span class="tn-term">{{ next_term.term }}</span> →
  </a>
  {% else %}<span></span>{% endif %}
</div>


{# ═══════════════════ SEARCH ═════════════════════════════ #}
{% elif view == 'search' %}

<div class="bc">
  <a href="{{ url_for('index', **mode_p) }}">Glossary</a>
  <span class="sep">›</span>
  <span>Search</span>
</div>

<div class="search-box">
  <form method="get" action="{{ url_for('search') }}" style="display:contents">
    <input type="search" name="q" value="{{ q or '' }}" placeholder="Search terms…" autofocus autocomplete="off">
    {% if adv %}<input type="hidden" name="adv" value="1">{% endif %}
    {% if eye %}<input type="hidden" name="eye" value="1">{% endif %}
    <button type="submit">Search</button>
  </form>
</div>

{% if q %}
  {% if results %}
  <p class="result-count">{{ results|length }} result{{ 's' if results|length != 1 }} for "<strong>{{ q }}</strong>"</p>
  <div class="term-list">
  {% for t in results %}
  <div class="entry">
    <div class="entry-head">
      <a class="entry-name" href="{{ url_for('term_page', slug=slugify(t.term), **mode_p) }}">{{ t.term }}</a>
    </div>
    {% if t.definition %}
    <div class="entry-def"><span class="short">{{ first_sentence(t.definition) }}</span></div>
    {% endif %}
  </div>
  {% endfor %}
  </div>
  {% endif %}

  {% if hidden_count %}
  <div class="nudge">
    {{ hidden_count }} more result{{ 's' if hidden_count != 1 }} beyond
    {{ 'Advanced' if adv else 'the default view' }} —
    <a href="{{ nudge_url }}">show {{ 'them' if hidden_count != 1 else 'it' }}</a>
  </div>
  {% endif %}

  {% if not results and not hidden_count %}
  <div class="empty">
    <div class="icon">🔍</div>
    <p>No terms found for "<strong>{{ q }}</strong>".</p>
    <p style="margin-top:.5rem;font-size:.8rem">
      <a href="{{ url_for('index', **mode_p) }}">Back to the glossary</a>
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
    <a href="{{ url_for('index') }}">Back to the glossary</a> or
    <a href="{{ url_for('search') }}">search</a>.
  </p>
</div>

{% endif %}

</div>{# /wrap #}

<script>{{ starfield_js|safe }}</script>
{% if view == 'index' %}<script>{{ glossary_js|safe }}</script>{% endif %}
</body>
</html>"""


def _render(view, page_title, meta_desc='', nav_q='', **kwargs):
    adv, eye, cat = mode_args()
    return render_template_string(
        TMPL,
        view=view, page_title=page_title, meta_desc=meta_desc, nav_q=nav_q,
        css=CSS, starfield_js=STARFIELD_JS, glossary_js=GLOSSARY_JS,
        slugify=slugify, first_sentence=first_sentence,
        adv=adv, eye=eye, mode_p=mode_params(adv, eye, cat),
        **kwargs,
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    """The glossary: alphabetical entries, tier-filtered client-side.
    Default = esoteric 1; Advanced + Third-eye expand; filter bar at Advanced."""
    db = get_db()
    entries = []
    for t in all_visible_terms(db):
        tags = split_tags(t['category'])
        d = t['definition'] or ''
        short = first_sentence(d)
        entries.append({
            'term': t['term'], 'slug': slugify(t['term']),
            'tier': term_tier(t),
            'tags': tags, 'tag_slugs': [slugify(x) for x in tags],
            'def_short': short, 'def_full': d if d != short else short,
        })
    return _render(
        'index', 'Longboard Glossary',
        meta_desc='The Ultimate Longboard Wiki glossary — longboarding terms, defined.',
        entries=entries,
        tiers_json=json.dumps(TIERS),
        nodes_json=json.dumps(NODES),
        top_json=json.dumps(TOP),
    )


@app.route('/categories')
def categories():
    """v1 URL kept alive: the landing page in Advanced mode IS the browse surface."""
    return redirect(url_for('index', adv=1))


@app.route('/category/<cat_slug>')
def category(cat_slug):
    """v1 URL kept alive: a category page is the landing page pre-filtered."""
    if cat_slug not in NODES:
        return _render('404', 'Category not found'), 404
    return redirect(url_for('index', adv=1, cat=cat_slug))


@app.route('/search')
def search():
    q = request.args.get('q', '').strip()
    if not q:
        return redirect(url_for('index'))
    db = get_db()
    adv, eye, _ = mode_args()
    tiers = mode_tiers(adv, eye)

    hits = search_terms(db, q)
    results = [t for t in hits if term_tier(t) in tiers]
    hidden = [t for t in hits if term_tier(t) not in tiers]

    # exact name match visible in-mode → straight to the term page
    if results and results[0]['term'].lower() == q.lower():
        return redirect(url_for('term_page', slug=slugify(results[0]['term']),
                                **mode_params(adv, eye)))

    # nudge: enable whatever the hidden matches need
    nudge_url = ''
    if hidden:
        need_eye = eye or any(term_tier(t) in TIERS['third_eye'] for t in hidden)
        nudge_url = url_for('search', q=q, adv=1, eye=(1 if need_eye else None))

    return _render(
        'search', f'Search: {q}', nav_q=q, q=q,
        results=results, hidden_count=len(hidden), nudge_url=nudge_url,
    )


@app.route('/<slug>')
def term_page(slug):
    db = get_db()
    term, redirect_slug = resolve_slug(db, slug)
    if term is None:
        return _render('404', 'Not found'), 404

    adv, eye, cat = mode_args()
    if redirect_slug and redirect_slug != slug:
        return redirect(url_for('term_page', slug=redirect_slug,
                                **mode_params(adv, eye, cat)), 301)

    prev_term, next_term = get_adjacent(db, term['id'], adv, eye, cat)
    tags = split_tags(term['category'])
    meta = first_sentence(term.get('definition') or '', max_len=160)

    return _render(
        'term', term['term'], meta_desc=meta, nav_q='',
        term=term, tags=tags, tag_slugs=[slugify(x) for x in tags],
        prev_term=prev_term, next_term=next_term,
    )


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    global DB_PATH, INCLUDE_CANDIDATES
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_db = os.path.join(
        script_dir, '..', '..', '..',
        'The Ultimate Longboard Wiki Project', 'Wiki', 'Glossary', 'glossary.db')

    p = argparse.ArgumentParser(description='Glossary Reader App')
    p.add_argument('--db', default=default_db, help='Path to glossary.db')
    p.add_argument('--port', type=int, default=5001)
    p.add_argument('--debug', action='store_true')
    p.add_argument('--canonical-only', action='store_true',
                   help='Hide candidate terms (launch state). Default shows them.')
    args = p.parse_args()

    if args.canonical_only or os.environ.get('GLOSSARY_CANONICAL_ONLY') == '1':
        INCLUDE_CANDIDATES = False

    DB_PATH = os.path.abspath(args.db)
    if not os.path.exists(DB_PATH):
        print(f'Error: database not found at {DB_PATH}')
        print('Check the --db path or confirm glossary.db exists.')
        return 1

    try:
        conn = sqlite3.connect(f'file:{DB_PATH}?mode=ro', uri=True)
        n_canon = conn.execute(
            "SELECT COUNT(*) FROM terms WHERE status='canonical'").fetchone()[0]
        n_vis = conn.execute(
            f"SELECT COUNT(*) FROM terms WHERE {visible_where()}").fetchone()[0]
        conn.close()
        register_unmapped_tags(DB_PATH)
        print('Glossary Reader App (v2)')
        print(f'Database    : {DB_PATH}')
        print(f'Canonical   : {n_canon} terms')
        print(f'Candidates  : {"INCLUDED (design preview)" if INCLUDE_CANDIDATES else "hidden (--canonical-only)"}')
        print(f'Visible     : {n_vis} terms')
        print(f'Tiers       : {TIERS}')
        print(f'Open        : http://localhost:{args.port}')
        print()
    except Exception as e:
        print(f'Error reading database: {e}')
        return 1

    app.run(host='0.0.0.0', port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
