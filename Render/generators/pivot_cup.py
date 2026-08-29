"""
generators/pivot_cup.py — Pivot Cup geometry module
Longboard Technology

Importable module — no Flask, no I/O. Two public entry points:
    validate(mode, pivot_d, pivot_l, socket_d, socket_depth)
        raises ValueError on first failing constraint, else returns None
    build_stl(mode, pivot_d, pivot_l, socket_d, socket_depth) -> bytes
        returns binary STL bytes ready to send to the client

Modes:
  pointed   — Cone top tapering to a near-apex (default).
              2.5 mm min flat tip for printability (silent, not user-visible).
              Hard constraint: socket_depth - pivot_l >= MIN_CEILING_MM.
  flat      — Same as pointed but cone truncated at midpoint of cone height.
              socket_depth is total height including the half-cone.
              Hard constraint: socket_depth - pivot_l >= MIN_CEILING_MM.
  hemi      — Outer shell is cylinder + hemispherical dome of radius r_outer.
              Hard constraints: the shared ceiling rule, plus MIN_WALL_MM of
              measured material beside the bore equator (the dome's flank curves
              in, so the flat wall rule doesn't describe it).
  tube      — Simple hollow cylinder. No cavity, no top geometry.
              Parameters: socket_d, pivot_d, socket_depth only.
"""

import math
import struct
import manifold3d as m3d
import numpy as np


# ── Global geometry constants ─────────────────────────────────────────────────
CONE_DEG       = 30.0   # outer cone wall angle from horizontal (pointed + flat)
OVERHANG_DEG   = 40.0   # inner bore overhang limit from horizontal
MIN_TIP_R      = 1.25   # mm — min cone/dome tip radius for printability
MIN_CEILING_MM = 2.0    # mm — min ceiling thickness (pointed + flat modes)
MIN_WALL_MM    = 1.8    # mm — min wall thickness per side
N_CONE         = 64     # profile points along outer cone / dome arc
N_HEMI         = 64     # profile points along inner hemisphere arc
N_REVOLVE      = 128    # angular steps for revolution

# FP slack (mm) for boundary comparisons. Values arrive from the JS soft-clamp
# rounded to 3 decimals (.toFixed(3)) — at exact constraint boundaries this
# round-trip can land 1e-15 below the bound, e.g. (16.9 - 13.3)/2 evaluates to
# 1.7999999999999998 instead of 1.8. Without slack the validator rejects values
# that the UI presents as "right at the limit." 1e-3 mm is one micron — well
# below any meaningful manufacturing tolerance, so the slack is invisible to
# physical outcomes but absorbs all realistic FP noise.
EPS_FP_MM      = 1e-3

CUP_MODES = {'pointed', 'flat', 'hemi'}
ALL_MODES = {'pointed', 'flat', 'hemi', 'tube'}


# ════════════════════════════════════════════════════════════════════════════════
# CONSTRAINTS
# ════════════════════════════════════════════════════════════════════════════════

def _cone_height(sd):
    return (sd / 2.0) * math.tan(math.radians(CONE_DEG))


# ── Hemi clearance ────────────────────────────────────────────────────────────
# The old hemi rule was `pivot_l < socket_depth - socket_d/2` — "the dome cannot
# overlap the cavity". It forced the cavity roof below the dome's equator plane,
# which pinned the minimum ceiling to r_outer (6.05 mm on a 12.1 mm cup, ~3x
# thicker than printing needs) and had nothing to do with MIN_CEILING_MM. It also
# measured the wrong thing: the cavity roof is not a disc of radius r_outer — the
# OVERHANG_DEG blend narrows it to a flat of radius ~0.364 * r_inner.
#
# Ceiling thickness is now the same `socket_depth - pivot_l` rule the other cup
# modes use (see CONSTRAINTS). Every cup mode has a sloping top, so that figure
# always reads a little high at the roof's outer edge — 0 mm on flat, up to
# 0.41 mm on hemi, 0.72-1.58 mm on pointed. That slack is the project's baked-in
# compromise and MIN_CEILING_MM is sized to absorb it (see
# Design Documents/PIVOT_CUP_GENERATOR.md).
#
# What hemi still needs on its own is the check below. Once the cavity rises past
# the dome's equator the outer surface starts curving inward, so the flat
# `(socket_d - pivot_d)/2` wall rule stops describing the real wall there. No
# other cup mode has that failure — their tops sit above a full-radius cylinder.

def _shell_clearance(r, z, sd, sdep):
    """Material between an inner point [r, z] and the hemi outer shell."""
    r_outer       = sd / 2.0
    dome_center_z = sdep - r_outer
    if z <= dome_center_z:
        return r_outer - r                              # cylindrical body
    return r_outer - math.hypot(r, z - dome_center_z)   # dome


def _hemi_bore_wall(pd, pl, sd, sdep):
    """Material beside the bore equator — the cavity's widest point."""
    r_inner = pd / 2.0
    return _shell_clearance(r_inner, pl - r_inner, sd, sdep)


CONSTRAINTS = [

    # ── Universal positivity ──────────────────────────────────────────────────
    {
        'modes':     ALL_MODES,
        'condition': lambda m,pd,pl,sd,sdep: sd <= 0,
        'user_msg':  "Socket Diameter must be greater than zero.",
    },
    {
        'modes':     ALL_MODES,
        'condition': lambda m,pd,pl,sd,sdep: sdep <= 0,
        'user_msg':  "Socket Depth must be greater than zero.",
    },
    {
        'modes':     ALL_MODES,
        'condition': lambda m,pd,pl,sd,sdep: pd <= 0,
        'user_msg':  "Pivot Diameter must be greater than zero.",
    },
    {
        'modes':     ALL_MODES,
        'condition': lambda m,pd,pl,sd,sdep: pd >= sd,
        'user_msg':  "Pivot Diameter must be smaller than Socket Diameter — no wall material would remain.",
    },
    {
        'modes':     ALL_MODES,
        'condition': lambda m,pd,pl,sd,sdep: pd < sd and (sd-pd)/2 < MIN_WALL_MM - EPS_FP_MM,
        'user_msg':  f"Wall is too thin — Socket Diameter minus Pivot Diameter must be at least {MIN_WALL_MM*2:.1f} mm ({MIN_WALL_MM:.1f} mm per side).",
    },

    # ── Cup modes: pivot_l checks ─────────────────────────────────────────────
    {
        'modes':     CUP_MODES,
        'condition': lambda m,pd,pl,sd,sdep: pl <= 0,
        'user_msg':  "Pivot Depth must be greater than zero.",
    },
    {
        'modes':     CUP_MODES,
        'condition': lambda m,pd,pl,sd,sdep: pl <= pd / 2.0,
        'user_msg':  "Pivot Depth must be greater than half the Pivot Diameter — the hemisphere needs room above the bore.",
    },
    {
        'modes':     CUP_MODES,
        'condition': lambda m,pd,pl,sd,sdep: pl >= sdep,
        'user_msg':  "Pivot Depth must be less than Socket Depth — the cavity cannot exceed the cup height.",
    },

    # ── Pointed + flat: cone must fit ─────────────────────────────────────────
    {
        'modes':     {'pointed', 'flat'},
        'condition': lambda m,pd,pl,sd,sdep: _cone_height(sd) >= sdep,
        'user_msg':  (
            f"Socket Depth is too shallow for the {CONE_DEG}° outer cone. "
            f"Minimum = Socket Diameter ÷ 2 × tan({CONE_DEG}°)."
        ),
    },

    # ── All cup modes: ceiling thickness ──────────────────────────────────────
    # One rule for pointed, flat and hemi: the material over the pin, measured on
    # the centre line. In flat mode that is the literal flat-roof thickness; in
    # pointed it is the height from pin tip to the cone's apex; in hemi, to the
    # dome's apex. Every one of those tops slopes, so the real thinnest ceiling at
    # the roof's outer edge is a little less than this figure — MIN_CEILING_MM is
    # sized to absorb that. Tube has no top, so it has no ceiling rule.
    {
        'modes':     CUP_MODES,
        'condition': lambda m,pd,pl,sd,sdep: (sdep - pl) < MIN_CEILING_MM - EPS_FP_MM,
        'user_msg':  (
            f"Ceiling is too thin — Socket Depth minus Pivot Depth must be at least "
            f"{MIN_CEILING_MM} mm. Reduce Pivot Depth or increase Socket Depth."
        ),
    },

    # ── Hemi only: the bore must stay inside the curving dome flank ───────────
    {
        'modes':     {'hemi'},
        'condition': lambda m,pd,pl,sd,sdep: _hemi_bore_wall(pd,pl,sd,sdep) < MIN_WALL_MM - EPS_FP_MM,
        'user_msg':  (
            f"Wall is too thin where the bore meets the dome — at least {MIN_WALL_MM} mm "
            f"is needed. Reduce Pivot Depth or Pivot Diameter, or increase Socket Depth."
        ),
    },
]


def validate(mode, pd, pl, sd, sdep):
    """Raises ValueError with user message on first failing constraint."""
    if mode not in ALL_MODES:
        raise ValueError(f"Unknown mode '{mode}'.")
    for rule in CONSTRAINTS:
        if mode in rule['modes']:
            if rule['condition'](mode, pd, pl, sd, sdep):
                raise ValueError(rule['user_msg'])


# ════════════════════════════════════════════════════════════════════════════════
# PROFILE BUILDERS
# ════════════════════════════════════════════════════════════════════════════════

def _cavity_points(pd, pl):
    """
    Shared inner cavity segment for all cup modes.
    Returns [r,z] list from (0, hemi_top_z) [ceiling axis] to (r_inner, 0).
    """
    r_inner       = pd / 2.0
    hemi_center_z = pl - r_inner
    hemi_top_z    = pl
    ov_rad        = math.radians(OVERHANG_DEG)
    cutoff_r      = r_inner * math.sin(ov_rad)
    cutoff_z      = hemi_center_z + r_inner * math.cos(ov_rad)
    tan_end_r     = cutoff_r - (hemi_top_z - cutoff_z) / math.tan(ov_rad)

    pts = []
    pts.append([0.0,       hemi_top_z])   # ceiling: axis corner
    pts.append([tan_end_r, hemi_top_z])   # ceiling: inner edge
    pts.append([cutoff_r,  cutoff_z])     # tangent end / cutoff
    for i in range(1, N_HEMI + 1):       # hemisphere arc
        t     = i / N_HEMI
        theta = ov_rad + t * (math.pi / 2.0 - ov_rad)
        pts.append([r_inner * math.sin(theta),
                    hemi_center_z + r_inner * math.cos(theta)])
    pts.append([r_inner, hemi_center_z])  # equator
    pts.append([r_inner, 0.0])            # bore base
    return pts


def profile_pointed(pd, pl, sd, sdep):
    """Cone top with MIN_TIP_R flat face for printability."""
    r_inner     = pd / 2.0
    r_outer     = sd / 2.0
    cone_height = _cone_height(sd)
    shoulder_z  = sdep - cone_height

    pts = []
    pts.append([r_inner, 0.0])
    pts.append([r_outer, 0.0])
    pts.append([r_outer, shoulder_z])

    tip_z = None
    for i in range(1, N_CONE + 1):
        t = i / N_CONE
        r = r_outer * (1.0 - t)
        z = shoulder_z + t * cone_height
        if r <= MIN_TIP_R:
            pts.append([MIN_TIP_R, z])
            tip_z = z
            break
        pts.append([r, z])

    if tip_z is None:
        tip_z = sdep
    pts.append([0.0, tip_z])
    pts.extend(_cavity_points(pd, pl))
    return np.array(pts, dtype=np.float64)


def profile_flat(pd, pl, sd, sdep):
    """
    Flat top — cone truncated at midpoint of full cone height.
    socket_depth is the total cup height; the flat face sits at socket_depth.
    """
    r_inner          = pd / 2.0
    r_outer          = sd / 2.0
    full_cone_height = _cone_height(sd)
    shoulder_z       = sdep - full_cone_height
    used_frac        = 0.5

    pts = []
    pts.append([r_inner, 0.0])
    pts.append([r_outer, 0.0])
    pts.append([r_outer, shoulder_z])

    for i in range(1, N_CONE + 1):
        t = i / N_CONE
        r = r_outer * (1.0 - t * used_frac)
        z = shoulder_z + t * full_cone_height
        pts.append([max(r, MIN_TIP_R), min(z, sdep)])
        if z >= sdep - 1e-6:
            break

    pts.append([0.0, sdep])
    pts.extend(_cavity_points(pd, pl))
    return np.array(pts, dtype=np.float64)


def profile_hemi(pd, pl, sd, sdep):
    """
    Hemispherical top — dome of radius r_outer centred at (0, sdep - r_outer).
    """
    r_inner       = pd / 2.0
    r_outer       = sd / 2.0
    dome_center_z = sdep - r_outer

    pts = []
    pts.append([r_inner, 0.0])
    pts.append([r_outer, 0.0])
    pts.append([r_outer, dome_center_z])

    for i in range(1, N_CONE + 1):
        t     = i / N_CONE
        theta = math.pi / 2.0 * (1.0 - t)
        r     = r_outer * math.sin(theta)
        z     = dome_center_z + r_outer * math.cos(theta)
        pts.append([r, z])

    pts.append([0.0, sdep])
    pts.extend(_cavity_points(pd, pl))
    return np.array(pts, dtype=np.float64)


def profile_tube(pd, sd, sdep):
    """Hollow cylinder — no cone, dome, or inner cavity."""
    r_inner = pd / 2.0
    r_outer = sd / 2.0
    return np.array([
        [r_inner, 0.0],
        [r_outer, 0.0],
        [r_outer, sdep],
        [r_inner, sdep],
    ], dtype=np.float64)


def build_profile(mode, pd, pl, sd, sdep):
    if mode == 'pointed': return profile_pointed(pd, pl, sd, sdep)
    if mode == 'flat':    return profile_flat(pd, pl, sd, sdep)
    if mode == 'hemi':    return profile_hemi(pd, pl, sd, sdep)
    if mode == 'tube':    return profile_tube(pd, sd, sdep)
    raise ValueError(f"Unknown mode: {mode!r}")


# ── STL builder ───────────────────────────────────────────────────────────────

def build_stl(mode, pd, pl, sd, sdep):
    """Build the cup mesh and return binary STL bytes."""
    profile = build_profile(mode, pd, pl, sd, sdep)
    m3d.set_circular_segments(N_REVOLVE)
    solid = m3d.CrossSection([profile]).revolve(circular_segments=N_REVOLVE)
    mesh  = solid.to_mesh()
    verts = mesh.vert_properties
    tris  = mesh.tri_verts

    header = b"Pivot Cup Generator - Longboard Technology" + b" " * 38
    buf    = bytearray(header)
    buf   += struct.pack('<I', len(tris))

    for tri in tris:
        v0, v1, v2 = verts[tri[0]], verts[tri[1]], verts[tri[2]]
        ax, ay, az = float(v1[0]-v0[0]), float(v1[1]-v0[1]), float(v1[2]-v0[2])
        bx, by, bz = float(v2[0]-v0[0]), float(v2[1]-v0[1]), float(v2[2]-v0[2])
        nx = ay*bz - az*by
        ny = az*bx - ax*bz
        nz = ax*by - ay*bx
        mag = math.sqrt(nx*nx + ny*ny + nz*nz)
        if mag > 1e-12: nx, ny, nz = nx/mag, ny/mag, nz/mag
        else:           nx, ny, nz = 0.0, 0.0, 1.0
        buf += struct.pack('<fff', nx, ny, nz)
        for v in (v0, v1, v2):
            buf += struct.pack('<fff', float(v[0]), float(v[1]), float(v[2]))
        buf += struct.pack('<H', 0)

    return bytes(buf)


def filename_for(mode, pd, pl, sd, sdep):
    """Standard filename for a generated STL."""
    parts = [f"pd{pd}", f"sd{sd}", f"sdep{sdep}"]
    if mode != 'tube':
        parts.insert(1, f"pl{pl}")
    return f"pivot_{mode}_{'_'.join(parts)}.stl"
