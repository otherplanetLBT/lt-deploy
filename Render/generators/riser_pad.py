"""
generators/riser_pad.py — Riser Pad slicer
Longboard Technology

Takes a master STL (full-height riser body, 0 ≤ Z ≤ master_height) and returns
a watertight STL clipped to the requested center height + wedge angle.

Implementation: 3D boolean subtract via `manifold3d`. The cap face is generated
implicitly by the boolean op — manifold3d guarantees the output is manifold
(watertight) when both inputs are manifold. No 2D triangulation, no Delaunay,
no cap tessellation algorithm.

Coordinate convention (must match master STLs):
    X — pad length, origin at center  (-39 to +39 mm)
    Y — pad width,  origin at center  (-28 to +28 mm)
    Z — height, bottom at Z=0, top at Z=master_height

Cutting plane:
    Defined by (plane_point, plane_normal). For a flat cut, plane_point =
    (0, 0, center_height) and plane_normal = (0, 0, 1). For a wedge, the plane
    is rotated around the Y axis through plane_point by `angle_deg`. After
    rotation, plane_normal = (sin α, 0, cos α). At α > 0 the +X end of the
    pad gets cut more aggressively (becomes thinner).

Public surface:
    read_stl(path)                          → list of (v0, v1, v2) tuples
    get_master_height(path)                 → max Z of master, for validation
    validate(center_h, angle_deg, master_h) → raises ValueError on failure
    slice_master(path, center_h, angle_deg) → manifold3d.Manifold (watertight)
    to_stl_bytes(manifold)                  → bytes (binary STL)
    min_center_height(angle_deg)            → minimum valid center height
    thin_end_height(center_h, angle_deg)    → height at -X end of pad
    filename_for(style, center_h, angle)    → standard download filename
"""

import math
import struct
import numpy as np
import manifold3d as m3d


# ── Constants ─────────────────────────────────────────────────────────────────
MIN_WALL_MM   = 0.5     # minimum thickness at the thin end of a wedge
MAX_ANGLE_DEG = 20.0
PAD_HALF_LEN  = 39.0    # half of the 78 mm pad length

# Cutter sizing — must extend well past the master in X/Y so a wedge cut
# doesn't leave a fringe on the perimeter.
CUTTER_PAD    = 50.0    # mm of buffer past the master bbox
CUTTER_HEIGHT = 100.0   # mm of cutter height above the cut plane

# STL vertex deduplication tolerance when ingesting a master STL.
SNAP = 1e-4


# ── STL I/O ───────────────────────────────────────────────────────────────────

def read_stl(path):
    """Read a binary STL → list of (v0, v1, v2) triangle tuples."""
    tris = []
    with open(path, 'rb') as f:
        f.read(80)
        n = struct.unpack('<I', f.read(4))[0]
        for _ in range(n):
            f.read(12)
            v0 = struct.unpack('<fff', f.read(12))
            v1 = struct.unpack('<fff', f.read(12))
            v2 = struct.unpack('<fff', f.read(12))
            f.read(2)
            tris.append((v0, v1, v2))
    return tris


def get_master_height(path):
    """Return the Z-extent of the master STL — used by validation."""
    tris = read_stl(path)
    return max(v[2] for t in tris for v in t)


# ── Manifold construction ────────────────────────────────────────────────────

def build_manifold(tris):
    """
    Convert a list of (v0, v1, v2) triangles into a manifold3d.Manifold.
    Deduplicates vertices using SNAP tolerance. Raises ValueError if the
    resulting mesh is not manifold.
    """
    vmap = {}
    verts = []
    indices = []
    for tri in tris:
        for v in tri:
            key = (round(v[0] / SNAP), round(v[1] / SNAP), round(v[2] / SNAP))
            if key not in vmap:
                vmap[key] = len(verts)
                verts.append(v)
            indices.append(vmap[key])

    vert_arr = np.array(verts,   dtype=np.float32)
    tri_arr  = np.array(indices, dtype=np.uint32).reshape(-1, 3)

    mesh     = m3d.Mesh(vert_properties=vert_arr, tri_verts=tri_arr)
    manifold = m3d.Manifold(mesh)
    if manifold.status() != m3d.Error.NoError:
        raise ValueError(
            f"Master STL is not manifold (status: {manifold.status()}). "
            "The boolean cut requires a watertight master body."
        )
    return manifold


def build_cutter(center_height, angle_deg, master_bbox):
    """
    Build a half-space cutter that occupies the region above the cutting plane.

    Constructed as a large box whose bottom face passes through (0, 0, center_height)
    and is rotated around the Y axis by angle_deg.

    Order: cube(center) → translate up by H/2 (bottom face at z=0)
         → rotate around Y (rotation pivots about the bottom-center, at the origin)
         → translate up by center_height (rotation pivot becomes the cut reference).
    """
    xmin, ymin, _, xmax, ymax, _ = master_bbox
    xspan = (xmax - xmin) + 2 * CUTTER_PAD
    yspan = (ymax - ymin) + 2 * CUTTER_PAD

    box = m3d.Manifold.cube([xspan, yspan, CUTTER_HEIGHT], center=True)
    box = box.translate([0, 0, CUTTER_HEIGHT / 2])    # bottom face at z=0
    if angle_deg != 0:
        box = box.rotate([0, angle_deg, 0])           # tilt around Y through origin
    box = box.translate([0, 0, center_height])        # lift to cut height
    return box


# ── Slicing ──────────────────────────────────────────────────────────────────

def slice_master(input_path, center_height, angle_deg):
    """
    Read the master STL, clip at the cutting plane, return a manifold3d.Manifold.
    Caller is responsible for converting to STL bytes via to_stl_bytes().
    """
    tris   = read_stl(input_path)
    body   = build_manifold(tris)
    cutter = build_cutter(center_height, angle_deg, body.bounding_box())
    result = body - cutter
    if result.status() != m3d.Error.NoError:
        raise RuntimeError(
            f"Boolean subtract failed (status: {result.status()})."
        )
    return result


def to_stl_bytes(manifold, header_text=b"Riser Pad - Longboard Technology"):
    """Serialize a manifold3d.Manifold to binary STL bytes."""
    mesh  = manifold.to_mesh()
    verts = mesh.vert_properties
    tris  = mesh.tri_verts

    header = header_text + b" " * (80 - len(header_text))
    buf = bytearray(header)
    buf += struct.pack('<I', len(tris))

    for tri in tris:
        v0, v1, v2 = verts[tri[0]], verts[tri[1]], verts[tri[2]]
        ax, ay, az = float(v1[0]-v0[0]), float(v1[1]-v0[1]), float(v1[2]-v0[2])
        bx, by, bz = float(v2[0]-v0[0]), float(v2[1]-v0[1]), float(v2[2]-v0[2])
        nx = ay*bz - az*by
        ny = az*bx - ax*bz
        nz = ax*by - ay*bx
        mag = math.sqrt(nx*nx + ny*ny + nz*nz)
        if mag > 1e-12:
            nx, ny, nz = nx/mag, ny/mag, nz/mag
        else:
            nx, ny, nz = 0.0, 0.0, 1.0
        buf += struct.pack('<fff', nx, ny, nz)
        for v in (v0, v1, v2):
            buf += struct.pack('<fff', float(v[0]), float(v[1]), float(v[2]))
        buf += struct.pack('<H', 0)

    return bytes(buf)


# ── Validation ───────────────────────────────────────────────────────────────

def min_center_height(angle_deg):
    """Minimum legal center height for the given wedge angle."""
    return MIN_WALL_MM + PAD_HALF_LEN * math.tan(math.radians(angle_deg))


def thin_end_height(center_h, angle_deg):
    """Height of the pad at the thin (−X) end."""
    return center_h - PAD_HALF_LEN * math.tan(math.radians(angle_deg))


def validate(center_h, angle_deg, master_height):
    """Raises ValueError on first failing constraint."""
    if center_h <= 0:
        raise ValueError("Center height must be greater than zero.")
    if angle_deg < 0 or angle_deg > MAX_ANGLE_DEG:
        raise ValueError(f"Wedge angle must be between 0 and {MAX_ANGLE_DEG}°.")
    thin = thin_end_height(center_h, angle_deg)
    # 1e-3 mm (one micron) slack absorbs FP noise from the JS round-trip
    # (.toFixed(3)) at exact constraint boundaries — the UI can present a value
    # as "right at the limit" while the literal float lands ~1e-15 below.
    if thin < MIN_WALL_MM - 1e-3:
        raise ValueError(
            f"Thin end would be {thin:.2f} mm — below {MIN_WALL_MM} mm minimum. "
            f"Minimum center height for {angle_deg:.1f}° is "
            f"{min_center_height(angle_deg):.2f} mm."
        )
    thick = center_h + PAD_HALF_LEN * math.tan(math.radians(angle_deg))
    if thick > master_height:
        raise ValueError(
            f"Thick end ({thick:.2f} mm) exceeds master STL height "
            f"({master_height:.2f} mm). Use a taller master body or reduce height/angle."
        )


# ── Filename helper ───────────────────────────────────────────────────────────

def filename_for(style, center_h, angle_deg):
    """Standard STL filename for a generated riser pad."""
    angle_str  = f'{angle_deg:.1f}deg'.replace('.', 'p')
    height_str = f'{center_h:.1f}mm'.replace('.', 'p')
    return f'riser_{style}_{angle_str}_{height_str}.stl'
