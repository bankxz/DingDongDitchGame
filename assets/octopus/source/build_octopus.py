"""Build the voxel octopus for Roblox: mesh, baked stud atlas, rig, idle + walk.

Run headless:  python3 build_octopus.py      (uses the `bpy` module, Blender 4.2)

Conventions
- 1 Blender unit = 1 stud (scene unit scale 0.01, per Roblox's Blender guidance).
- Character faces -Y, Z up, ground at Z=0.
- Built as a right half (x >= 0), baked, then mirrored so both halves share UVs
  (doubles texel density on the single 1024 atlas).
"""
import math
import os
import sys

import bpy  # noqa: I001  (must precede bmesh/mathutils when run as a module)
import bmesh
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
TILES = os.path.join(ROOT, "textures", "tiles")
TEX = os.path.join(ROOT, "textures")
EXPORT = os.path.join(ROOT, "export")
os.makedirs(EXPORT, exist_ok=True)
ATLAS = int(os.environ.get("OCTO_ATLAS", "1024"))
FPS = 30

# ----------------------------------------------------------------------------
# scene
# ----------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = "METRIC"
scene.unit_settings.scale_length = 0.01
scene.render.fps = FPS

# material slot indices (bake-source)
M_BODY, M_ARM, M_SUCK, M_EYE, M_BEAK, M_SPIKE = range(6)


def lerp(a, b, t):
    return a + (b - a) * t


def catmull(pts, n):
    """Resample a Catmull-Rom spline through pts to n points evenly by arc length."""
    P = [Vector(p) for p in pts]
    P = [P[0] * 2 - P[1]] + P + [P[-1] * 2 - P[-2]]
    dense = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(40):
            t = k / 40
            t2, t3 = t * t, t * t * t
            dense.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    dense.append(P[-2])
    acc = [0.0]
    for a, b in zip(dense, dense[1:]):
        acc.append(acc[-1] + (b - a).length)
    L = acc[-1]
    out, j = [], 0
    for i in range(n):
        s = L * i / (n - 1)
        while j < len(acc) - 2 and acc[j + 1] < s:
            j += 1
        f = (s - acc[j]) / max(acc[j + 1] - acc[j], 1e-9)
        out.append(dense[j].lerp(dense[j + 1], min(max(f, 0), 1)))
    return out, L


class Builder:
    """Collects geometry into one bmesh with material, tile-UV and weight data."""

    def __init__(self):
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("tile")
        self.deform = self.bm.verts.layers.deform.verify()
        self.groups = []

    def group(self, name):
        if name not in self.groups:
            self.groups.append(name)
        return self.groups.index(name)

    def face(self, verts, mat, uvs=None, smooth=False):
        f = self.bm.faces.new(verts)
        f.material_index = mat
        f.smooth = smooth
        if uvs:
            for loop, uv in zip(f.loops, uvs):
                loop[self.uv].uv = uv
        return f

    def vert(self, co, weights):
        v = self.bm.verts.new(co)
        for g, w in weights.items():
            if w > 1e-4:
                v[self.deform][self.group(g)] = w
        return v


B = Builder()
BODY_W = {"Body": 1.0}

# ----------------------------------------------------------------------------
# mantle (faceted, boxy superellipse rings, leaning back)
# ----------------------------------------------------------------------------
# (z, half-width, front y, back y)  -- measured from the FRONT / SIDE views
RINGS = [
    (0.95, 0.80, -0.60, 0.65),
    (1.40, 1.30, -1.10, 1.05),
    (2.10, 1.62, -1.45, 1.40),
    (2.95, 1.85, -1.55, 1.80),
    (3.80, 1.75, -1.40, 2.35),
    (4.70, 1.52, -1.10, 2.55),
    (5.45, 1.18, -0.75, 2.30),
    (6.00, 0.78, -0.38, 1.65),
    (6.30, 0.46, -0.08, 1.10),
]
TOP = (0.0, 0.45, 6.42)
NSEG = 10  # around (full circle); only the x>=0 half is kept
SE = 5.5   # superellipse exponent -> blocky head


def se_point(a, yf, yb, ang):
    c, s = math.cos(ang), math.sin(ang)
    x = a * math.copysign(abs(c) ** (2 / SE), c)
    b = -yf if s < 0 else yb
    y = b * math.copysign(abs(s) ** (2 / SE), s)
    return x, y


def mantle_front_y(x, z):
    """y of the mantle front surface at (x, z) (interpolated between rings)."""
    for (z0, a0, f0, b0), (z1, a1, f1, b1) in zip(RINGS, RINGS[1:]):
        if z0 <= z <= z1:
            t = (z - z0) / (z1 - z0)
            a, f = lerp(a0, a1, t), lerp(f0, f1, t)
            u = min(abs(x) / a, 0.999)
            return f * (1 - u ** SE) ** (1 / SE)
    return RINGS[-1][2]


ring_verts = []
for z, a, yf, yb in RINGS:
    row = []
    for i in range(NSEG // 2 + 1):  # angles from -90deg (front) to +90deg (back) through +x
        ang = -math.pi / 2 + math.pi * i / (NSEG // 2)
        x, y = se_point(a, yf, yb, ang)
        x = max(x, 0.0)
        if i in (0, NSEG // 2):
            x = 0.0
        row.append(B.vert((x, y, z), BODY_W))
    ring_verts.append(row)
for r0, r1 in zip(ring_verts, ring_verts[1:]):
    for i in range(len(r0) - 1):
        B.face([r0[i], r0[i + 1], r1[i + 1], r1[i]], M_BODY)
top = B.vert(TOP, BODY_W)
last = ring_verts[-1]
for i in range(len(last) - 1):
    B.face([last[i], last[i + 1], top], M_BODY)
bot = B.vert((0, 0.05, 0.75), BODY_W)
first = ring_verts[0]
for i in range(len(first) - 1):
    B.face([first[i + 1], first[i], bot], M_BODY)


# ----------------------------------------------------------------------------
# helpers for blocky parts
# ----------------------------------------------------------------------------
def prism(profile, depth_dir, depth, mat, front_scale=1.0, weights=BODY_W, cap_uv=None):
    """Extrude a planar polygon (list of Vectors) along depth_dir; front cap may shrink."""
    n = len(profile)
    c = sum(profile, Vector()) / n
    back = [B.vert(p, weights) for p in profile]
    front = [B.vert(c + (p - c) * front_scale + depth_dir * depth, weights) for p in profile]
    B.face(list(reversed(back)), mat)
    uvs = cap_uv(profile) if cap_uv else None
    B.face(front, mat, uvs)
    for i in range(n):
        j = (i + 1) % n
        B.face([back[i], back[j], front[j], front[i]], mat)
    return front


def spike(base_c, tip, width, mat=M_SPIKE, up=Vector((0, 0, 1)), sides=4, weights=BODY_W):
    base_c, tip = Vector(base_c), Vector(tip)
    axis = (tip - base_c).normalized()
    u = axis.cross(up)
    if u.length < 1e-3:
        u = axis.cross(Vector((1, 0, 0)))
    u.normalize()
    v = axis.cross(u).normalized()
    ring = []
    for k in range(sides):
        a = 2 * math.pi * k / sides + math.pi / 4
        ring.append(B.vert(base_c + (u * math.cos(a) + v * math.sin(a)) * width, weights))
    t = B.vert(tip, weights)
    for k in range(sides):
        B.face([ring[k], ring[(k + 1) % sides], t], mat)
    B.face(list(reversed(ring)), mat)


def box(center, size, mat=M_BODY, rot=Matrix.Identity(3), weights=BODY_W):
    cx, cy, cz = center
    sx, sy, sz = (s / 2 for s in size)
    corners = [Vector((x, y, z)) for x in (-sx, sx) for y in (-sy, sy) for z in (-sz, sz)]
    vs = [B.vert(Vector(center) + rot @ c, weights) for c in corners]
    quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    for q in quads:
        B.face([vs[i] for i in q], mat)


# ----------------------------------------------------------------------------
# face: eye, brow, beak  (FRONT view measurements, right half)
# ----------------------------------------------------------------------------
FWD = Vector((0, -1, 0))
# eye: slanted trapezoid, top edge dips toward the nose (angry)
eye2d = [(0.36, 2.72), (1.12, 2.86), (1.20, 3.52), (0.36, 3.10)]
eye_pts = [Vector((x, mantle_front_y(x, z) + 0.18, z)) for x, z in eye2d]
xs = [p.x for p in eye_pts]
zs = [p.z for p in eye_pts]


def eye_uv(profile):
    # u = 1 at the inner (nose) side so the iris sits inner-lower
    return [(1 - (p.x - min(xs)) / (max(xs) - min(xs)), (p.z - min(zs)) / (max(zs) - min(zs))) for p in profile]


prism(eye_pts, FWD, 0.24, M_EYE, 1.0, cap_uv=eye_uv)

# brow ridge: angled block sweeping from above the nose up to the temple
brow_in = Vector((0.18, 0, 3.12))
brow_out = Vector((1.62, 0, 4.18))
d = (brow_out - brow_in).normalized()
n_up = Vector((-d.z, 0, d.x))
bw = 0.34
brow = []
for p, dy in ((brow_in, -0.28), (brow_out, 0.05)):
    y = mantle_front_y(p.x, p.z) + 0.25
    brow += [Vector((p.x, y, p.z)) - n_up * bw * 0.6, Vector((p.x, y, p.z)) + n_up * bw * 0.4]
brow = [brow[0], brow[2], brow[3], brow[1]]
prism(brow, Vector((0, -0.93, -0.35)).normalized(), 0.62, M_BODY, 0.82)

# beak: dark downward pentagon between the eyes (half, closed at x=0)
beak2d = [(0.0, 3.18), (0.50, 3.08), (0.50, 2.30), (0.08, 1.52), (0.0, 1.50)]
beak_pts = [Vector((x, mantle_front_y(x, z) + 0.25, z)) for x, z in beak2d]
prism(beak_pts, Vector((0, -1, -0.15)).normalized(), 0.62, M_BEAK, 0.72)

# ----------------------------------------------------------------------------
# spikes: crown, temple, side/back fins, spine blocks (FRONT/SIDE/BACK/TOP)
# ----------------------------------------------------------------------------
spike((0.0, 0.25, 6.05), (0.0, 0.10, 7.05), 0.34)              # crown spike
spike((0.0, 1.25, 5.85), (0.0, 1.85, 6.85), 0.30)              # crest 2
spike((0.0, 2.05, 5.10), (0.0, 3.60, 5.90), 0.40)              # crest 3
spike((1.30, -0.55, 4.55), (2.15, -0.35, 5.85), 0.30)          # temple spike
spike((1.45, 0.25, 4.30), (2.55, 0.95, 5.05), 0.28)            # side 1
spike((1.62, 0.55, 3.35), (2.70, 1.35, 3.50), 0.26)            # side 2
spike((1.50, 0.85, 2.35), (2.40, 1.65, 2.05), 0.22)            # side 3
spike((0.70, 1.70, 5.35), (1.05, 4.30, 6.25), 0.52)            # back fin 1 (long, sweeps up-back)
spike((1.05, 2.00, 4.35), (1.70, 4.60, 4.55), 0.55)            # back fin 2
spike((1.10, 2.05, 3.25), (1.70, 4.20, 2.85), 0.48)            # back fin 3
spike((0.35, 1.00, 5.95), (0.55, 3.10, 7.05), 0.42)            # top back fin
spike((0.55, 0.20, 5.80), (0.95, 0.55, 6.55), 0.22)            # crown side
for z, s_ in ((4.35, 0.55), (4.95, 0.52), (5.55, 0.48)):
    box((0.0, mantle_front_y(0.0, z) + 0.12, z), (s_, s_, s_ * 0.95), M_BODY)  # front crest ridge
for i, (y, z) in enumerate([(0.95, 6.05), (1.75, 5.55), (2.15, 4.75), (2.25, 3.85), (2.05, 2.95), (1.65, 2.05)]):
    s = 0.46 - i * 0.03
    box((0.0, y, z), (s, s * 0.9, s), M_BODY)                   # spine blocks (bisected later)

# ----------------------------------------------------------------------------
# tentacles
# ----------------------------------------------------------------------------
# profile points (r = outward from centre, z = up, s = lateral toward the arm's +B)
# measured from the FRONT view, azimuth from the TOP view; ventral side shown pink.
ARMS = [
    # name, azimuth (deg from front, toward +x), base width, pts (r, z, s), ventral sign
    ("Arm1", 28, 0.80, [(0.45, 2.0, 0), (1.49, 0.95, 0), (2.87, 0.5, 0.2), (4.25, 0.5, 0.6), (5.29, 0.9, 1.2), (5.63, 1.6, 1.8), (5.17, 2.0, 2.1)], -1),
    ("Arm2", 58, 0.80, [(0.5, 2.0, 0), (1.56, 2.8, 0), (2.66, 3.45, 0), (3.66, 3.7, -0.1), (4.41, 3.2, -0.3), (4.36, 2.35, -0.4), (3.76, 1.7, -0.6), (3.11, 1.45, -0.75), (2.81, 1.8, -0.8)], -1),
    ("Arm3", 128, 0.68, [(0.55, 2.6, 0), (1.94, 3.1, 0), (3.07, 3.8, 0), (3.44, 4.85, 0), (3.98, 5.6, -0.2), (4.74, 5.7, -0.4), (5.33, 5.3, -0.6), (5.43, 4.7, -0.6), (5.17, 4.45, -0.5)], 1),
    ("Arm4", 150, 0.74, [(0.5, 1.85, 0), (1.4, 0.85, 0), (2.6, 0.48, -0.25), (3.7, 0.5, -0.7), (4.4, 0.95, -1.3), (4.6, 1.7, -1.8), (4.2, 2.05, -2.1)], -1),
]
TSEG = 18
FRONT, BACK = Vector((0, -1, 0)), Vector((0, 1, 0))
ROLL = {"Arm1": (30, FRONT), "Arm2": (45, FRONT), "Arm3": (35, FRONT), "Arm4": (30, BACK)}


def sucker(base, T, Bv, U, w, wts):
    """Square cream sucker block: 5 faces (inner face hidden inside the arm)."""
    a, b = w * 0.62, w * 0.80
    lo, hi = w * 0.25, -w * 0.30   # U offsets: 'lo' inside the arm, 'hi' sticks out
    c = [base + T * ta + Bv * tb + U * tu for tu in (lo, hi) for ta in (-a, a) for tb in (-b, b)]
    v = [B.vert(x, wts) for x in c]
    # outer face (textured sucker with sunken centre)
    B.face([v[4], v[5], v[7], v[6]], M_SUCK, [(0.14, 0.14), (0.86, 0.14), (0.86, 0.86), (0.14, 0.86)])
    side_uv = [(0.17, 0.17), (0.3, 0.17), (0.3, 0.3), (0.17, 0.3)]
    for q in ((0, 1, 5, 4), (1, 3, 7, 5), (3, 2, 6, 7), (2, 0, 4, 6)):
        B.face([v[k] for k in q], M_SUCK, side_uv)
CS = 10                    # cross-section verts (chamfered square, split sides)
BONES_PER_ARM = 5
VENTRAL = {8: (0.04, 0.06), 9: (0.06, 0.08), 0: (0.08, 0.10)}  # plain lilac strip of the sucker tile
arm_curves = {}

for name, az, w0, prof, vsign in ARMS:
    th = math.radians(az)
    R = Vector((math.sin(th), -math.cos(th), 0))   # outward
    Lat = Vector((math.cos(th), math.sin(th), 0))  # lateral (perp to arm plane)
    world = [R * r + Vector((0, 0, z)) + Lat * s for r, z, s in prof]
    pts, L = catmull(world, TSEG + 1)
    arm_curves[name] = pts
    # parallel-transport frame starting with B = lateral
    tangents = []
    for i in range(len(pts)):
        a = pts[max(i - 1, 0)]
        b = pts[min(i + 1, len(pts) - 1)]
        tangents.append((b - a).normalized())
    Bv = Lat.copy()
    frames = []
    for i, T in enumerate(tangents):
        if i > 0:
            Bv = Bv - T * Bv.dot(T)
            Bv.normalize()
        U = T.cross(Bv).normalized() * vsign * -1  # U points dorsal; -U ventral
        frames.append((T, Bv.copy(), U))
    # roll the section so the sucker side turns toward the viewer, as in the sheet
    roll_deg, face_dir = ROLL[name]
    mid = frames[len(frames) // 2]
    best = None
    for sgn in (1, -1):
        a_ = math.radians(roll_deg) * sgn
        Um = mid[2] * math.cos(a_) + mid[1] * math.sin(a_)
        score = (-Um).dot(face_dir)
        if best is None or score > best[0]:
            best = (score, a_)
    a_ = best[1]
    frames = [(T, Bv * math.cos(a_) - U * math.sin(a_), U * math.cos(a_) + Bv * math.sin(a_)) for T, Bv, U in frames]
    # arm sits in the plane -> U is "up" for ground arms; ventral = -U
    rings = []
    ring_wts = []
    acc = 0.0
    vs_acc = [0.0]
    for i in range(1, len(pts)):
        acc += (pts[i] - pts[i - 1]).length
        vs_acc.append(acc)
    widths = []
    for i in range(len(pts)):
        t = i / (len(pts) - 1)
        widths.append(lerp(w0, 0.20, t ** 1.8))
    # accumulated length normalised by local width -> studs shrink toward the tip
    vnorm = [0.0]
    for i in range(1, len(pts)):
        seg = vs_acc[i] - vs_acc[i - 1]
        vnorm.append(vnorm[-1] + seg / (0.5 * (widths[i] + widths[i - 1])))
    for i, (p, (T, Bv, U)) in enumerate(zip(pts, frames)):
        w = widths[i]
        hgt = w * 0.95
        c = 0.55
        sect = [(c * w, -hgt), (w, -c * hgt), (w, -0.05 * hgt), (w, c * hgt), (c * w, hgt), (-c * w, hgt), (-w, c * hgt), (-w, -0.05 * hgt), (-w, -c * hgt), (-c * w, -hgt)]
        t = i / (len(pts) - 1)
        # weights: body near base, blend along chain
        f = t * BONES_PER_ARM - 0.5
        k0 = int(math.floor(f))
        fr = f - k0
        wts = {}
        for k, ww in ((k0, 1 - fr), (k0 + 1, fr)):
            kk = min(max(k, 0), BONES_PER_ARM - 1)
            wts[f"{name}_{kk + 1}_R"] = wts.get(f"{name}_{kk + 1}_R", 0) + ww
        if t < 0.12:
            bw_ = 1 - t / 0.12
            wts = {g: v * (1 - bw_) for g, v in wts.items()}
            wts["Body"] = bw_
        ring = [B.vert(p + Bv * sx + U * sy, wts) for sx, sy in sect]
        rings.append(ring)
        ring_wts.append(wts)
    # modelled sucker blocks along the ventral midline (anatomy, not surface studs)
    pos = vs_acc[-1] * 0.16
    while pos < vs_acc[-1] * 0.95:
        i = max(j for j in range(len(vs_acc)) if vs_acc[j] <= pos)
        i = min(i, len(pts) - 2)
        f = (pos - vs_acc[i]) / max(vs_acc[i + 1] - vs_acc[i], 1e-9)
        p = pts[i].lerp(pts[i + 1], f)
        T, Bv, U = frames[i]
        w = lerp(widths[i], widths[i + 1], f)
        sucker(p - U * w * 0.95, T, Bv, U, w, ring_wts[i if f < 0.5 else i + 1])
        pos += w * 1.62
    for i in range(len(rings) - 1):
        v0 = vnorm[i] * 0.55
        v1 = vnorm[i + 1] * 0.55
        for k in range(CS):
            kk = (k + 1) % CS
            quad = [rings[i][k], rings[i][kk], rings[i + 1][kk], rings[i + 1][k]]
            if k in VENTRAL:   # ventral band: bottom, chamfers, lower sides -> suckers
                u0, u1 = VENTRAL[k]
                sv0, sv1 = 0.1 + (vnorm[i] * 0.05) % 0.8, 0.1 + (vnorm[i] * 0.05) % 0.8 + 0.01
                B.face(quad, M_SUCK, [(u0, sv0), (u1, sv0), (u1, sv1), (u0, sv1)])
            else:
                u0, u1 = k / CS * 2.4, (k + 1) / CS * 2.4
                B.face(quad, M_ARM, [(u0, v0), (u1, v0), (u1, v1), (u0, v1)])
    # pointed tip
    tip = B.vert(pts[-1] + frames[-1][0] * widths[-1] * 1.6, {f"{name}_{BONES_PER_ARM}_R": 1.0})
    for k in range(CS):
        B.face([rings[-1][k], rings[-1][(k + 1) % CS], tip], M_SUCK if k in VENTRAL else M_ARM)
    # close the (buried) base
    B.face(list(reversed(rings[0])), M_ARM)

# ----------------------------------------------------------------------------
# to object, bisect at x=0 (right half)
# ----------------------------------------------------------------------------
mesh = bpy.data.meshes.new("Octopus")
bm = B.bm
bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, 0), plane_no=(1, 0, 0), clear_inner=True)
bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-4)
for v in bm.verts:
    if abs(v.co.x) < 1e-4:
        v.co.x = 0.0
bm.to_mesh(mesh)
bm.free()
obj = bpy.data.objects.new("Octopus", mesh)
scene.collection.objects.link(obj)
for g in B.groups:
    obj.vertex_groups.new(name=g)
for g in list(B.groups):
    if g.endswith("_R"):
        obj.vertex_groups.new(name=g[:-2] + "_L")
bpy.context.view_layer.objects.active = obj
obj.select_set(True)
for p in mesh.polygons:
    p.use_smooth = False
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.object.mode_set(mode="OBJECT")

# ----------------------------------------------------------------------------
# bake-source materials
# ----------------------------------------------------------------------------
def img(name, cs="sRGB"):
    im = bpy.data.images.load(os.path.join(TILES, name), check_existing=True)
    im.colorspace_settings.name = cs
    return im


def src_mat(name, color_img=None, height_img=None, flat=None, uv="tile", box_scale=None, bump=0.6):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.name = "EMIT"
    bsdf.name = "BSDF"
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    if flat is not None:
        bsdf.inputs["Base Color"].default_value = (*flat, 1)
        emit.inputs["Color"].default_value = (*flat, 1)
        return m
    if box_scale:
        tc = nt.nodes.new("ShaderNodeTexCoord")
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (box_scale,) * 3
        # abs(x) keeps the mirrored halves identical
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        ab = nt.nodes.new("ShaderNodeMath")
        ab.operation = "ABSOLUTE"
        comb = nt.nodes.new("ShaderNodeCombineXYZ")
        nt.links.new(tc.outputs["Object"], sep.inputs[0])
        nt.links.new(sep.outputs[0], ab.inputs[0])
        nt.links.new(ab.outputs[0], comb.inputs[0])
        nt.links.new(sep.outputs[1], comb.inputs[1])
        nt.links.new(sep.outputs[2], comb.inputs[2])
        nt.links.new(comb.outputs[0], mp.inputs[0])
        vec = mp.outputs[0]
    else:
        uvn = nt.nodes.new("ShaderNodeUVMap")
        uvn.uv_map = uv
        vec = uvn.outputs[0]
    ct = nt.nodes.new("ShaderNodeTexImage")
    ct.image = img(color_img)
    ht = nt.nodes.new("ShaderNodeTexImage")
    ht.image = img(height_img, "Non-Color")
    if box_scale:
        for t in (ct, ht):
            t.projection = "BOX"
            t.projection_blend = 0.15
    nt.links.new(vec, ct.inputs[0])
    nt.links.new(vec, ht.inputs[0])
    nt.links.new(ct.outputs[0], bsdf.inputs["Base Color"])
    nt.links.new(ct.outputs[0], emit.inputs["Color"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = bump
    bp.inputs["Distance"].default_value = 0.05
    nt.links.new(ht.outputs[0], bp.inputs["Height"])
    nt.links.new(bp.outputs[0], bsdf.inputs["Normal"])
    return m


mats = [
    src_mat("SRC_body", "stud_body_color.png", "stud_body_height.png", box_scale=0.5, bump=1.0),
    src_mat("SRC_arm", "stud_arm_color.png", "stud_arm_height.png", bump=1.0),
    src_mat("SRC_sucker", "sucker_color.png", "sucker_height.png", bump=0.8),
    None,
    src_mat("SRC_beak", flat=(0.095, 0.068, 0.255)),
    src_mat("SRC_spike", "stud_body_color.png", "stud_body_height.png", box_scale=0.35, bump=0.25),
]
# eye: image on the tile UV (0..1 over the eye cap), others flat dark
em = bpy.data.materials.new("SRC_eye")
em.use_nodes = True
nt = em.node_tree
nt.nodes.clear()
o = nt.nodes.new("ShaderNodeOutputMaterial")
b = nt.nodes.new("ShaderNodeBsdfPrincipled")
b.name = "BSDF"
e = nt.nodes.new("ShaderNodeEmission")
e.name = "EMIT"
uvn = nt.nodes.new("ShaderNodeUVMap")
uvn.uv_map = "tile"
t = nt.nodes.new("ShaderNodeTexImage")
t.image = img("eye_color.png")
nt.links.new(uvn.outputs[0], t.inputs[0])
nt.links.new(t.outputs[0], b.inputs["Base Color"])
nt.links.new(t.outputs[0], e.inputs["Color"])
nt.links.new(b.outputs[0], o.inputs[0])
mats[M_EYE] = em
for m in mats:
    obj.data.materials.append(m)

# eye side walls get no tile UVs (0,0 -> dark rim of eye texture) which reads as a socket. good.

# ----------------------------------------------------------------------------
# atlas UV (half model) + bake colour & normal
# ----------------------------------------------------------------------------
atlas_uv = mesh.uv_layers.new(name="UVMap")
mesh.uv_layers.active = atlas_uv
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.smart_project(angle_limit=math.radians(58), island_margin=0.006, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
bpy.ops.uv.pack_islands(margin=0.004, rotate=True)
bpy.ops.object.mode_set(mode="OBJECT")
atlas_uv.active_render = False
mesh.uv_layers["tile"].active_render = True  # tile UV drives the source textures' default
mesh.uv_layers.active = atlas_uv

scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 16
scene.render.bake.margin = 6
scene.render.bake.use_clear = True

color_img = bpy.data.images.new("Octopus_Color", ATLAS, ATLAS, alpha=False)
normal_img = bpy.data.images.new("Octopus_Normal", ATLAS, ATLAS, alpha=False)
normal_img.colorspace_settings.name = "Non-Color"


def set_targets(image, emit):
    for m in obj.data.materials:
        nt = m.node_tree
        n = nt.nodes.get("BAKE") or nt.nodes.new("ShaderNodeTexImage")
        n.name = "BAKE"
        n.image = image
        un = nt.nodes.get("BAKEUV") or nt.nodes.new("ShaderNodeUVMap")
        un.name = "BAKEUV"
        un.uv_map = "UVMap"
        nt.links.new(un.outputs[0], n.inputs[0])
        nt.nodes.active = n
        out = [x for x in nt.nodes if x.type == "OUTPUT_MATERIAL"][0]
        src = nt.nodes["EMIT"] if emit else nt.nodes["BSDF"]
        nt.links.new(src.outputs[0], out.inputs[0])


set_targets(color_img, True)
bpy.ops.object.bake(type="EMIT", uv_layer="UVMap")
set_targets(normal_img, False)
scene.cycles.samples = 4
bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT", uv_layer="UVMap")
color_path = os.path.join(TEX, "Octopus_Color.png")
normal_path = os.path.join(TEX, "Octopus_Normal.png")
# fill unused atlas space (bake leaves it black) so mip levels don't bleed dark seams
import numpy as np  # noqa: E402

for im, fill in ((color_img, (0.033, 0.015, 0.34)), (normal_img, (0.5, 0.5, 1.0))):
    px = np.empty(ATLAS * ATLAS * 4, np.float32)
    im.pixels.foreach_get(px)
    px = px.reshape(-1, 4)
    empty = px[:, :3].sum(1) < 1e-6
    px[empty, :3] = fill
    im.pixels.foreach_set(px.ravel())
for im, p in ((color_img, color_path), (normal_img, normal_path)):
    im.filepath_raw = p
    im.file_format = "PNG"
    im.save()
print("BAKED", color_path, normal_path)

# ----------------------------------------------------------------------------
# final single material (what Roblox gets), drop tile UV, mirror
# ----------------------------------------------------------------------------
final = bpy.data.materials.new("Octopus")
final.use_nodes = True
nt = final.node_tree
bsdf = nt.nodes["Principled BSDF"]
ct = nt.nodes.new("ShaderNodeTexImage")
ct.image = bpy.data.images.load(color_path, check_existing=False)
ct.image.name = "Octopus_Color.png"
nm = nt.nodes.new("ShaderNodeTexImage")
nm.image = bpy.data.images.load(normal_path, check_existing=False)
nm.image.name = "Octopus_Normal.png"
nm.image.colorspace_settings.name = "Non-Color"
nmap = nt.nodes.new("ShaderNodeNormalMap")
nt.links.new(ct.outputs[0], bsdf.inputs["Base Color"])
nt.links.new(nm.outputs[0], nmap.inputs["Color"])
nt.links.new(nmap.outputs[0], bsdf.inputs["Normal"])
bsdf.inputs["Roughness"].default_value = 0.62
obj.data.materials.clear()
obj.data.materials.append(final)
for p in mesh.polygons:
    p.material_index = 0
mesh.uv_layers.remove(mesh.uv_layers["tile"])
mesh.uv_layers["UVMap"].active_render = True

mir = obj.modifiers.new("Mirror", "MIRROR")
mir.use_axis = (True, False, False)
mir.use_mirror_merge = True
mir.merge_threshold = 1e-3
mir.use_mirror_vertex_groups = True
bpy.ops.object.modifier_apply(modifier="Mirror")
# pack atlas-normal islands are shared -> fine for Roblox; recalc normals
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.object.mode_set(mode="OBJECT")
mesh.calc_loop_triangles()
TRIS = len(mesh.loop_triangles)
print("TRIS", TRIS)
if TRIS >= 5000:
    raise SystemExit(f"triangle budget exceeded: {TRIS}")

# ----------------------------------------------------------------------------
# armature
# ----------------------------------------------------------------------------
arm_data = bpy.data.armatures.new("OctopusRig")
rig = bpy.data.objects.new("OctopusRig", arm_data)
scene.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode="EDIT")
eb = arm_data.edit_bones
root = eb.new("Root")
root.head, root.tail = (0, 0, 0), (0, 0.0, 0.8)
body = eb.new("Body")
body.head, body.tail = (0, 0.2, 1.6), (0, 0.4, 4.6)
body.parent = root
for name, az, *_ in ARMS:
    pts = arm_curves[name]
    th = math.radians(az)
    lat = Vector((math.cos(th), math.sin(th), 0))
    n = len(pts) - 1
    idx = [round(n * k / BONES_PER_ARM) for k in range(BONES_PER_ARM + 1)]
    for side, sx in (("R", 1), ("L", -1)):
        prev = body
        for k in range(BONES_PER_ARM):
            a, b = pts[idx[k]].copy(), pts[idx[k + 1]].copy()
            a.x *= sx
            b.x *= sx
            bone = eb.new(f"{name}_{k + 1}_{side}")
            bone.head, bone.tail = a, b
            l = lat.copy()
            l.x *= sx
            bone.align_roll(l)
            bone.parent = prev
            bone.use_connect = k > 0
            prev = bone
bpy.ops.object.mode_set(mode="OBJECT")
obj.parent = rig
mod = obj.modifiers.new("Armature", "ARMATURE")
mod.object = rig

# ----------------------------------------------------------------------------
# animations
# ----------------------------------------------------------------------------
GROUP_A = {"Arm1_R", "Arm2_L", "Arm3_R", "Arm4_L"}
ARM_PHASE = {"Arm1": 0.0, "Arm2": 1.3, "Arm3": 2.5, "Arm4": 3.7}


def key_action(action_name, frames, pose_fn):
    act = bpy.data.actions.new(action_name)
    rig.animation_data_create()
    rig.animation_data.action = act
    for pb in rig.pose.bones:
        pb.rotation_mode = "XYZ"
    for f in range(0, frames + 1, 2):
        ph = 2 * math.pi * f / frames
        for pb in rig.pose.bones:
            pb.location = (0, 0, 0)
            pb.rotation_euler = (0, 0, 0)
        pose_fn(ph)
        for pb in rig.pose.bones:
            pb.keyframe_insert("rotation_euler", frame=f + 1)
            if pb.name in ("Body", "Root"):
                pb.keyframe_insert("location", frame=f + 1)
    for fc in act.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"
        mods = fc.modifiers.new("CYCLES")
    act.frame_range = (1, frames + 1)
    act.use_frame_range = True
    act.use_cyclic = True
    return act


def arm_bones():
    for name, *_ in ARMS:
        for side in ("R", "L"):
            yield name, side, [rig.pose.bones[f"{name}_{k + 1}_{side}"] for k in range(BONES_PER_ARM)]


def idle(ph):
    bd = rig.pose.bones["Body"]
    # bone Y is roughly world up for Body: local translation along Y = bob
    bd.location = (0, 0.10 * math.sin(ph), 0)
    bd.rotation_euler = (math.radians(2.0) * math.sin(ph + 0.6), math.radians(2.5) * math.sin(ph * 1 + 1.9), 0)
    for name, side, chain in arm_bones():
        off = ARM_PHASE[name] + (0.7 if side == "L" else 0)
        for k, pb in enumerate(chain):
            amp = math.radians(4 + 3.2 * k)
            pb.rotation_euler = (math.radians(2 + k) * math.sin(ph + off - 0.8 * k + 1.1), 0, amp * math.sin(ph + off - 0.8 * k))


def walk(ph):
    bd = rig.pose.bones["Body"]
    bd.location = (0, 0.14 * math.cos(2 * ph), 0)
    bd.rotation_euler = (math.radians(-4 + 2 * math.cos(2 * ph)), math.radians(5) * math.sin(ph), math.radians(3) * math.sin(ph))
    for name, side, chain in arm_bones():
        g = 0.0 if f"{name}_{side}" in GROUP_A else math.pi
        p = ph + g
        sgn = 1 if side == "R" else -1
        for k, pb in enumerate(chain):
            lag = p - 0.55 * k
            swing = math.radians(16 if k == 0 else 7) * math.sin(lag) * sgn
            lift = math.radians(10 + 4 * k) * max(0.0, math.cos(lag)) - math.radians(3)
            pb.rotation_euler = (swing, 0, lift)


IDLE_FRAMES, WALK_FRAMES = 90, 36
idle_act = key_action("Idle", IDLE_FRAMES, idle)
walk_act = key_action("Walk", WALK_FRAMES, walk)
for act in (idle_act, walk_act):
    act.use_fake_user = True
    tr = rig.animation_data.nla_tracks.new()
    tr.name = act.name
    tr.strips.new(act.name, 1, act)
    tr.mute = True
rig.animation_data.action = idle_act
scene.frame_start, scene.frame_end = 1, IDLE_FRAMES + 1
for pb in rig.pose.bones:
    pb.rotation_euler = (0, 0, 0)
    pb.location = (0, 0, 0)

# limit influences to 4 & normalise (Roblox requirement)
bpy.context.view_layer.objects.active = obj
obj.select_set(True)
bpy.ops.object.vertex_group_limit_total(limit=4)
bpy.ops.object.vertex_group_normalize_all(lock_active=False)

# ----------------------------------------------------------------------------
# save + export
# ----------------------------------------------------------------------------
blend_path = os.path.join(ROOT, "Octopus.blend")
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=blend_path, compress=True)


def export_fbx(path, action):
    rig.animation_data.action = action
    for tr in rig.animation_data.nla_tracks:
        tr.mute = True
    if action:
        scene.frame_start, scene.frame_end = int(action.frame_range[0]), int(action.frame_range[1])
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    obj.select_set(True)
    bpy.ops.export_scene.fbx(
        filepath=path,
        use_selection=True,
        object_types={"MESH", "ARMATURE"},
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="-Z",
        axis_up="Y",
        use_mesh_modifiers=False,
        mesh_smooth_type="FACE",
        add_leaf_bones=False,
        primary_bone_axis="Y",
        secondary_bone_axis="X",
        armature_nodetype="NULL",
        use_armature_deform_only=False,
        bake_anim=action is not None,
        bake_anim_use_all_actions=False,
        bake_anim_use_nla_strips=False,
        bake_anim_force_startend_keying=True,
        bake_anim_simplify_factor=0.0,
        path_mode="COPY",
        embed_textures=True,
    )


export_fbx(os.path.join(EXPORT, "Octopus_Rig.fbx"), None)
export_fbx(os.path.join(EXPORT, "Octopus_Idle.fbx"), idle_act)
export_fbx(os.path.join(EXPORT, "Octopus_Walk.fbx"), walk_act)

# glTF with both clips (Roblox's importer also takes .glb)
for tr in rig.animation_data.nla_tracks:
    tr.mute = False
rig.animation_data.action = None
bpy.ops.export_scene.gltf(
    filepath=os.path.join(EXPORT, "Octopus.glb"),
    export_format="GLB",
    use_selection=True,
    export_yup=True,
    export_animations=True,
    export_animation_mode="ACTIONS",
    export_skins=True,
    export_apply=False,
)
for tr in rig.animation_data.nla_tracks:
    tr.mute = True
rig.animation_data.action = idle_act
print("EXPORTED", os.listdir(EXPORT))
print("BONES", len(arm_data.bones), "TRIS", TRIS, "VERTS", len(mesh.vertices))
