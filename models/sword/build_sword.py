"""Untextured detailed 1:1 sword. Front silhouette locked to the reference sheet,
thickness from side view, plus carved cracks, blade ridge/bevels, gems,
spiral-wrapped grip, real chain links, spiked cap and pommel.
Run: python3 build_sword_v2.py
"""
import bpy, bmesh, cv2, numpy as np, math
from mathutils import Vector
from PIL import Image

REF = 'reference_sheet.png'
OUT = '/home/user/DingDongDitchGame/models/sword/sword_model'
rgb = np.array(Image.open(REF).convert('RGB')).astype(int)
mask = (rgb.sum(2) < 3 * 235).astype(np.uint8)
R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
red = (((R > 90) & (G < 80) & (B < 80) & (R > 1.8 * G))).astype(np.uint8)

FX0, FX1 = 40, 239      # front view columns
BX0, BX1 = 317, 516     # back view columns
SX0, SX1 = 951, 1033     # side view columns
Y0, Y1 = 11, 861
SCALE = 1.2 / 850
CX = 139.5
ZERO = 500

side_t = np.ones(mask.shape[0]); side_c = np.zeros(mask.shape[0])
cs = []
for y in range(Y0, Y1 + 1):
    xs = np.where(mask[y, SX0:SX1])[0]
    if len(xs): side_t[y] = xs.max() - xs.min() + 1; cs.append((xs.max() + xs.min()) / 2 + SX0)
    else: cs.append(np.nan)
cs = np.array(cs); ref_c = np.nanmedian(cs)
side_c[Y0:Y1 + 1] = np.where(np.isnan(cs), ref_c, cs) - ref_c
k = np.ones(7) / 7
side_t = np.convolve(side_t, k, mode='same'); side_c = np.convolve(side_c, k, mode='same')


def W(x, y, yoff=0.0):
    return (((x - CX) * SCALE), yoff * SCALE, -(y - ZERO) * SCALE)


def smooth(t): t = np.clip(t, 0, 1); return t * t * (3 - 2 * t)


def make_obj(name, verts, faces, smooth_shade=True):
    me = bpy.data.meshes.new(name + 'M')
    me.from_pydata(verts, [], faces); me.update()
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob)
    if smooth_shade:
        for p in me.polygons: p.use_smooth = True
    return ob


GRAY = cv2.cvtColor(np.array(Image.open(REF).convert('RGB')).astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)


def relief_field(g, redm, shape, up, sigma):
    g = g.copy()
    rd = cv2.dilate(redm.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    bl = cv2.GaussianBlur(g, (0, 0), sigma)
    g[rd] = bl[rd]
    hp = g - cv2.GaussianBlur(g, (0, 0), sigma)
    hp = cv2.GaussianBlur(hp, (0, 0), 0.8)
    hp = np.clip(hp / (hp.std() + 1e-6), -2, 2) / 2
    return cv2.resize(hp, (shape[1], shape[0]), interpolation=cv2.INTER_LINEAR)


def heightfield(name, ya, yb, prof, up=1, groove=1.8, xa=FX0, xb=FX1, wanted=None, relief=0.0):
    """Dense surface over the part's silhouette. prof(ctx)->half-thickness px."""
    sub = np.zeros(mask.shape, np.uint8)
    sub[ya:yb, xa:xb] = mask[ya:yb, xa:xb]
    roi = sub[ya:yb, xa:xb].astype(np.float32)
    big = cv2.resize(roi, None, fx=up, fy=up, interpolation=cv2.INTER_CUBIC)
    m = (big > 0.5).astype(np.uint8)
    if up > 1:
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    # drop specks
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, connectivity=4)
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] < 8 * up * up: m[lab == i] = 0
    if wanted is not None:
        pass
    dt = cv2.distanceTransform(m, cv2.DIST_L2, 5) / up
    # groove fields (front from front view, back from flipped back view)
    rf = red[ya:yb, xa:xb].astype(np.float32)
    rb = red[ya:yb, BX0:BX1][:, ::-1].astype(np.float32)
    def gfield(rr):
        rr = cv2.dilate(rr, np.ones((2, 2), np.uint8))
        rr = cv2.resize(rr, (m.shape[1], m.shape[0]), interpolation=cv2.INTER_LINEAR)
        return cv2.GaussianBlur(rr, (0, 0), 0.6 * up)
    gf, gb = gfield(rf), gfield(rb)
    hh, ww = m.shape
    jj, ii = np.mgrid[0:hh, 0:ww]
    px = xa + (ii + 0.5) / up
    py = ya + (jj + 0.5) / up
    # per-row extents for normalised cross-section coordinate
    rows = np.where(m.any(1), 1, 0)
    xmin = np.full(hh, 0.0); xmax = np.full(hh, 1.0)
    for j in range(hh):
        xs = np.where(m[j])[0]
        if len(xs): xmin[j], xmax[j] = xs.min(), xs.max()
    rc = (xmin + xmax) / 2; rh = np.maximum((xmax - xmin) / 2, 1)
    u = (ii - rc[:, None]) / rh[:, None]
    yi = np.clip(np.round(py).astype(int), Y0, Y1)
    ctx = dict(dt=dt, u=u, px=px, py=py, Tz=side_t[yi], c=side_c[yi], rh=rh[:, None] / up,
               rowhalf=rh[:, None] / up, up=up)
    H = prof(ctx)
    Rf = Rb = 0
    if relief:
        Rf = relief * relief_field(GRAY[ya:yb, xa:xb], red[ya:yb, xa:xb], m.shape, up, 5.0) * smooth(dt / 3.0)
        Rb = relief * relief_field(GRAY[ya:yb, BX0:BX1][:, ::-1], red[ya:yb, BX0:BX1][:, ::-1], m.shape, up, 5.0) * smooth(dt / 3.0)
    H_f, H_b = H + Rf, H + Rb
    Hf = np.maximum(H_f - groove * smooth(gf * 1.2), 0.35)
    Hb = np.maximum(H_b - groove * smooth(gb * 1.2), 0.35)
    idx = -np.ones(m.shape, np.int64); inside = m > 0
    cnt = int(inside.sum()); idx[inside] = np.arange(cnt)
    X = px[inside]; Yp = py[inside]; C = ctx['c'][inside]
    vf = np.stack([(X - CX) * SCALE, (C - Hf[inside]) * SCALE, -(Yp - ZERO) * SCALE], 1)
    vb = np.stack([(X - CX) * SCALE, (C + Hb[inside]) * SCALE, -(Yp - ZERO) * SCALE], 1)
    verts = np.concatenate([vf, vb]); faces = []
    a, b, c, d = idx[:-1, :-1], idx[:-1, 1:], idx[1:, 1:], idx[1:, :-1]
    q = (a >= 0) & (b >= 0) & (c >= 0) & (d >= 0)
    qa, qb, qc, qd = a[q], b[q], c[q], d[q]
    faces += [tuple(r) for r in np.stack([qa, qb, qc, qd], 1)]
    faces += [tuple(r) for r in np.stack([qd + cnt, qc + cnt, qb + cnt, qa + cnt], 1)]
    # boundary walls
    Q = np.zeros((hh + 1, ww + 1), bool); Q[1:-1, 1:-1] = False
    Qv = np.zeros((hh - 1, ww - 1), bool); Qv[:] = q
    P = np.pad(Qv, 1)
    # horizontal edges (i,j)-(i+1,j) between row j-1 quad and row j quad
    for j in range(hh):
        for i in range(ww - 1):
            if idx[j, i] < 0 or idx[j, i + 1] < 0: continue
            up_q = P[j, i + 1]   # quad above (row j-1) -> padded index j
            dn_q = P[j + 1, i + 1]
            if up_q != dn_q:
                p0, p1 = idx[j, i], idx[j, i + 1]
                faces.append((p0, p1, p1 + cnt, p0 + cnt) if dn_q else (p1, p0, p0 + cnt, p1 + cnt))
    for j in range(hh - 1):
        for i in range(ww):
            if idx[j, i] < 0 or idx[j + 1, i] < 0: continue
            l_q = P[j + 1, i]; r_q = P[j + 1, i + 1]
            if l_q != r_q:
                p0, p1 = idx[j, i], idx[j + 1, i]
                faces.append((p1, p0, p0 + cnt, p1 + cnt) if r_q else (p0, p1, p1 + cnt, p0 + cnt))
    return make_obj('GEO-' + name, verts.tolist(), faces), ctx


# ---------- profiles ----------
def prof_blade(c):
    bev = 6.0
    edge = smooth(c['dt'] / bev) * 0.8 + 0.2
    ridge = 1 - 0.22 * np.minimum(np.abs(c['u'] + 0.25), 1.0)
    return np.maximum(c['Tz'] * 0.5 * edge * ridge * 1.0, 0.4)

def prof_guard(c):
    edge = smooth(c['dt'] / 4.0) * 0.85 + 0.15
    tx = 1 - 0.72 * np.minimum(np.abs(c['px'] - CX) / 92.0, 1) ** 1.2
    plate = 1 + 0.10 * np.exp(-((c['px'] - CX) / 16) ** 2)
    return np.maximum(c['Tz'] * 0.5 * edge * np.maximum(tx, 0.2) * plate * 0.95, 0.4)

def prof_round(c):
    t = np.clip(1 - c['u'] ** 2, 0, 1)
    return np.maximum(np.sqrt(t) * c['rh'] * 1.0, 0.4)

def prof_pommel(c):
    edge = smooth(c['dt'] / 3.5) * 0.8 + 0.2
    tx = 1 - 0.6 * np.minimum(np.abs(c['px'] - CX) / 22.0, 1)
    return np.maximum(c['Tz'] * 0.5 * edge * np.maximum(tx, 0.25), 0.4)


def surface_h(ctx_prof, ob_ctx, x, y):
    return None


# ---------- gems ----------
def gem(name, cx, cy, hw, hh, depth, ybase):
    """Octahedron-like faceted diamond protruding on both faces. ybase=half thickness px."""
    verts = []; faces = []
    for sgn in (-1, 1):  # -1 front (towards -Y), +1 back
        base = len(verts)
        verts += [W(cx, cy - hh, sgn * (ybase - 0.5)), W(cx + hw, cy, sgn * (ybase - 0.5)),
                  W(cx, cy + hh, sgn * (ybase - 0.5)), W(cx - hw, cy, sgn * (ybase - 0.5)),
                  W(cx, cy, sgn * (ybase + depth))]
        for i in range(4):
            faces.append((base + i, base + (i + 1) % 4, base + 4))
        faces.append((base + 3, base + 2, base + 1, base + 0))
    return make_obj('GEO-' + name, verts, faces, smooth_shade=False)


# ---------- grip: lathe with spiral wrap ----------
def grip():
    ya, yb = 557, 625
    segs = 28
    verts = []; faces = []
    ys = np.arange(ya, yb + 0.01, 1.0)
    for j, y in enumerate(ys):
        xs = np.where(mask[int(y), FX0:FX1])[0]
        r0 = (xs.max() - xs.min() + 1) / 2 * 0.86
        t = (y - ya) / (yb - ya)
        collar = 2.2 * smooth((7 - (y - ya)) / 7) + 1.6 * smooth((y - (yb - 9)) / 9)
        for s in range(segs):
            a = 2 * math.pi * s / segs
            phase = a / (2 * math.pi) * 1.0 + (y - ya) / 11.0
            band = (abs(math.sin(math.pi * phase))) ** 0.55
            groove = 1.0 - 0.0
            r = r0 * (0.90 + 0.14 * band) + collar
            verts.append(W(CX + r * math.cos(a), y, r * math.sin(a) + side_c[int(y)] * 0.0))
    for j in range(len(ys) - 1):
        for s in range(segs):
            a = j * segs + s; b = j * segs + (s + 1) % segs
            faces.append((a, b, b + segs, a + segs))
    # end caps
    for j in (0, len(ys) - 1):
        c = len(verts); verts.append(W(CX, ys[j], 0))
        for s in range(segs):
            a = j * segs + s; b = j * segs + (s + 1) % segs
            faces.append((c, b, a) if j == 0 else (c, a, b))
    return make_obj('GEO-sword_grip', verts, faces)


# ---------- chain ----------
def link(name, cz, phi, w=18.0, h=26.0, r=4.0, nseg=40, nring=10):
    a = (w - 2 * r) / 2; b = (h - 2 * r) / 2; st = b - a
    path = []
    n = nseg // 2
    for i in range(n + 1):           # top arc
        t = math.pi * i / n
        path.append((a * math.cos(t), st + a * math.sin(t)))
    for i in range(n + 1):           # bottom arc
        t = math.pi + math.pi * i / n
        path.append((a * math.cos(t), -st + a * math.sin(t)))
    # remove duplicate joins
    pts = []
    for p in path:
        if not pts or (abs(p[0] - pts[-1][0]) + abs(p[1] - pts[-1][1])) > 1e-6: pts.append(p)
    if (abs(pts[0][0] - pts[-1][0]) + abs(pts[0][1] - pts[-1][1])) < 1e-6: pts.pop()
    N = len(pts); verts = []; faces = []
    for i in range(N):
        p = np.array(pts[i]); q = np.array(pts[(i + 1) % N]); pr = np.array(pts[i - 1])
        tan = q - pr; tan /= np.linalg.norm(tan)
        nrm = np.array([tan[1], -tan[0]])   # outward in-plane normal
        for k in range(nring):
            t = 2 * math.pi * k / nring
            off_in = math.cos(t) * r; off_perp = math.sin(t) * r
            lp = p + nrm * off_in
            c_, s_ = math.cos(phi), math.sin(phi)
            hx = lp[0] * c_ - off_perp * s_
            hy = lp[0] * s_ + off_perp * c_
            verts.append(W(CX + hx, cz - lp[1], hy))
    for i in range(N):
        for k in range(nring):
            a = i * nring + k; b = i * nring + (k + 1) % nring
            c = ((i + 1) % N) * nring + (k + 1) % nring; d = ((i + 1) % N) * nring + k
            faces.append((a, b, c, d))
    return make_obj(name, verts, faces)


def drop_islands(ob, min_verts=150):
    bm = bmesh.new(); bm.from_mesh(ob.data)
    seen = set(); kill = []
    for v in bm.verts:
        if v.index in seen: continue
        stack = [v]; comp = []; seen.add(v.index)
        while stack:
            x = stack.pop(); comp.append(x)
            for e in x.link_edges:
                o = e.other_vert(x)
                if o.index not in seen: seen.add(o.index); stack.append(o)
        if len(comp) < min_verts: kill += comp
    if kill:
        bmesh.ops.delete(bm, geom=kill, context='VERTS'); print('DROPPED', ob.name, len(kill))
    bm.to_mesh(ob.data); bm.free()


def join(objs, name, bevel=None):
    objs = [o for o in objs if o]
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1: bpy.ops.object.join()
    o = bpy.context.active_object; o.name = name
    return o


bpy.ops.wm.read_factory_settings(use_empty=True)
blade, _ = heightfield('blade', Y0, 452, prof_blade, up=2, groove=2.4, relief=1.6)
guard, _ = heightfield('guard', 452, 560, prof_guard, up=2, groove=2.0, relief=3.0)
cap, _ = heightfield('cap', 624, 656, prof_round, up=2, groove=1.0)
pommel, _ = heightfield('pommel', 792, Y1 + 1, prof_pommel, up=2, groove=1.6, relief=1.5)
gr = grip()
links = []
for i, cz in enumerate([689.5, 730.5, 772.5]):
    links.append(link(f'GEO-chain_big_{i}', cz, math.radians(45), w=22.0, h=26.0, r=3.6))
for i, cz in enumerate([667, 710.5, 751.5, 791.5]):
    links.append(link(f'GEO-chain_small_{i}', cz, math.radians(135), w=9.0, h=20.0, r=2.4))
chain = join(links, 'GEO-sword_chain')
g1 = gem('gem_guard', 139.7, 478.8, 8, 12, 5.5, 20)
g2 = gem('gem_cap', 139.4, 641.4, 3.5, 5, 2.5, 8)
g3 = gem('gem_pommel', 139.8, 823.4, 6, 8, 4, 9)
gems = join([g1, g2, g3], 'GEO-sword_gems')
for _o in (blade, guard, cap, pommel): drop_islands(_o)
blade.name = 'GEO-sword_blade'; guard.name = 'GEO-sword_guard'; gr.name = 'GEO-sword_grip'
cap.name = 'GEO-sword_cap'; pommel.name = 'GEO-sword_pommel'

mat = bpy.data.materials.new('MAT-clay_untextured'); mat.use_nodes = True
bs = mat.node_tree.nodes['Principled BSDF']
bs.inputs['Base Color'].default_value = (0.55, 0.55, 0.58, 1); bs.inputs['Roughness'].default_value = 0.6
for o in bpy.data.objects:
    if o.type == 'MESH':
        o.data.materials.clear(); o.data.materials.append(mat)
        print('PART', o.name, len(o.data.vertices), len(o.data.polygons))
bpy.ops.wm.save_as_mainfile(filepath=OUT + '.blend')
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=OUT + '.glb', export_format='GLB', use_selection=True, export_apply=True)
print('SAVED', OUT)
