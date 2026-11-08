"""Clean, angular, untextured sword built from smoothed vector outlines.
Blade/guard = stepped layered solids (boolean union) + clean boolean crack/seam grooves + crisp bevel.
Front silhouette from reference sheet, thickness from the edge-on view.
Run: python3 build_sword.py
"""
import bpy, bmesh, cv2, numpy as np, math
from PIL import Image

REF = 'reference_sheet.png'
OUT = 'sword_model'
rgb = np.array(Image.open(REF).convert('RGB')).astype(int)
mask = (rgb.sum(2) < 3 * 235).astype(np.uint8)
R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
red = (((R > 90) & (G < 80) & (B < 80) & (R > 1.8 * G))).astype(np.uint8)

FX0, FX1 = 40, 239
BX0, BX1 = 317, 516
SX0, SX1 = 951, 1033
Y0, Y1 = 11, 861
SCALE = 1.2 / 850
CX = 139.5
ZERO = 500
UP = 4
GEPS, GMIN = 5.5, 300

# ---- clean side profile (edge-on view) ----
ys = np.arange(Y0, Y1 + 1)
tw, tc = [], []
for y in ys:
    xs = np.where(mask[y, SX0:SX1])[0]
    tw.append(xs.max() - xs.min() + 1 if len(xs) else 1)
    tc.append((xs.max() + xs.min()) / 2 + SX0 if len(xs) else np.nan)
tw = np.array(tw, float); tc = np.array(tc)
tc = np.where(np.isnan(tc), np.nanmedian(tc), tc) - np.nanmedian(tc)
def sm(a, n): return np.convolve(np.pad(a, n, mode='edge'), np.ones(2 * n + 1) / (2 * n + 1), mode='valid')
tw = sm(tw, 9); tc = sm(tc, 15)
def Tz(row): return float(np.interp(row, ys, tw))
from scipy.signal import medfilt
tw_body = medfilt(np.pad(tw, 15, mode='edge'), 31)[15:-15]
def Tb(row): return float(np.interp(row, ys, tw)) if row >= 524 else float(np.interp(row, ys, tw_body))
def ext_half(x0, x1, row):
    xs = np.where(mask[int(row), x0:x1])[0]
    return (xs.max() - xs.min() + 1) / 2 if len(xs) else 0.0
def fhalf(row): return ext_half(FX0, FX1, row)
def shalf(row): return ext_half(SX0, SX1, row)
def Cz(row): return float(np.interp(row, ys, tc)) - 0.6


def W(x, row, d=0.0):
    return ((x - CX) * SCALE, d * SCALE, -(row - ZERO) * SCALE)


def smooth(t): t = np.clip(t, 0, 1); return t * t * (3 - 2 * t)


def make_obj(name, verts, faces, flat=False):
    me = bpy.data.meshes.new(name + 'M')
    me.from_pydata(verts, [], faces); me.update()
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob)
    for p in me.polygons: p.use_smooth = not flat
    return ob


# ---- smoothed vector outlines ----
def outlines(binary_roi, xa, ya, sigma=2.6, eps=1.5, min_area=40):
    """binary ROI (orig px) -> list of (outer_polygon, [hole_polygons]); smoothed + simplified."""
    big = cv2.resize(binary_roi.astype(np.float32), None, fx=UP, fy=UP, interpolation=cv2.INTER_CUBIC)
    big = cv2.GaussianBlur(big, (0, 0), sigma)
    m = (big > 0.5).astype(np.uint8)
    cs, h = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    polys = {}
    for i, c in enumerate(cs):
        if cv2.contourArea(c) < min_area: continue
        a = cv2.approxPolyDP(c, eps, True)[:, 0, :].astype(float)
        if len(a) < 3: continue
        polys[i] = np.stack([xa + (a[:, 0] + 0.5) / UP, ya + (a[:, 1] + 0.5) / UP], 1)
    groups = []
    for i, p in polys.items():
        if h[0][i][3] == -1:
            groups.append((p, [polys[j] for j in polys if h[0][j][3] == i]))
    return groups


def layer_mask(sub_roi, erode_px):
    if erode_px <= 0: return sub_roi
    big = cv2.resize(sub_roi.astype(np.float32), None, fx=UP, fy=UP, interpolation=cv2.INTER_CUBIC)
    big = (cv2.GaussianBlur(big, (0, 0), 2.6) > 0.5).astype(np.uint8)
    dt = cv2.distanceTransform(big, cv2.DIST_L2, 5)
    m = (dt >= erode_px * UP).astype(np.uint8)
    return cv2.resize(m, (sub_roi.shape[1], sub_roi.shape[0]), interpolation=cv2.INTER_AREA) > 0.5


def prism(name, groups, tfun):
    """Solid from [(outer, [holes])] polygons. tfun(x,row)->(front_y, back_y) px."""
    from mathutils import Vector
    import mathutils.geometry as mg
    bm = bmesh.new()
    for outer, holes in groups:
        loops = [outer] + list(holes)
        allv_t = []; allv_b = []
        for poly in loops:
            tv = []; bv = []
            for x, r in poly:
                f, b = tfun(x, r)
                tv.append(bm.verts.new(W(x, r, f))); bv.append(bm.verts.new(W(x, r, b)))
            n = len(poly)
            for i in range(n):
                try: bm.faces.new((tv[i], tv[(i + 1) % n], bv[(i + 1) % n], bv[i]))
                except ValueError: pass
            allv_t += tv; allv_b += bv
        tess = mg.tessellate_polygon([[Vector((float(x), float(r), 0.0)) for x, r in poly] for poly in loops])
        for (i, j, k) in tess:
            try: bm.faces.new((allv_t[i], allv_t[j], allv_t[k]))
            except ValueError: pass
            try: bm.faces.new((allv_b[k], allv_b[j], allv_b[i]))
            except ValueError: pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name + 'M'); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob)
    return ob


def boolean(a, b, op, exact=True):
    md = a.modifiers.new('b', 'BOOLEAN'); md.object = b; md.operation = op
    md.solver = 'EXACT'
    try: md.use_self = True
    except Exception: pass
    bpy.context.view_layer.objects.active = a
    bpy.ops.object.modifier_apply(modifier=md.name)
    bpy.data.objects.remove(b)


def tris(ob): return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def reduce(ob, budget):
    """Shape-preserving: planar dissolve first, then (only if still over budget) edge-collapse."""
    bpy.context.view_layer.objects.active = ob
    d = ob.modifiers.new('dis', 'DECIMATE'); d.decimate_type = 'DISSOLVE'; d.angle_limit = math.radians(3.0)
    bpy.ops.object.modifier_apply(modifier=d.name)
    t = tris(ob); print('REDUCE', ob.name, 'after dissolve', t)
    if t > budget:
        tm = ob.modifiers.new('tri', 'TRIANGULATE'); bpy.ops.object.modifier_apply(modifier=tm.name)
        c = ob.modifiers.new('col', 'DECIMATE'); c.decimate_type = 'COLLAPSE'; c.ratio = budget / tris(ob)
        c.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=c.name)
        print('REDUCE', ob.name, 'after collapse', tris(ob))


def finish(ob, bevel=0.0005, name=None):
    bpy.context.view_layer.objects.active = ob
    try: bpy.ops.object.shade_auto_smooth(angle=math.radians(32))
    except Exception:
        for p in ob.data.polygons: p.use_smooth = False
    if name: ob.name = name
    return ob


def bevel_obj(ob, px, segs=2, angle=30):
    bpy.context.view_layer.objects.active = ob
    bv = ob.modifiers.new('bev', 'BEVEL'); bv.width = px * SCALE; bv.segments = segs
    bv.limit_method = 'ANGLE'; bv.angle_limit = math.radians(angle); bv.use_clamp_overlap = True
    bpy.ops.object.modifier_apply(modifier=bv.name)


def layered_part(name, ya, yb, layers, groove_depth, taper=None, osig=3.0, oeps=1.8, const_t=None, use_body=False, kgroove=9, clip=None):
    """layers: [(erode_px, thickness_scale, bevel_px, groove)] each a beveled slab; crisp grooves cut after bevel."""
    xa, xb = FX0, FX1
    sub = np.zeros(mask.shape, np.uint8); sub[ya:yb, xa:xb] = mask[ya:yb, xa:xb]
    roi = sub[ya:yb, xa:xb].copy()
    if clip:   # (row0, xl, xr): below row0 keep only the blade-width column band (shaft entering the guard)
        r0, xl, xr = clip
        roi[r0 - ya:, :xl - xa] = 0; roi[r0 - ya:, xr - xa + 1:] = 0

    def tf_for(sc):
        def f(x, r):
            t = (const_t if const_t else (Tb(r) if use_body else Tz(r)) * 0.5) * sc
            if taper: t *= taper(x)
            t = max(t, 0.6); c = Cz(r)
            return (c - t, c + t)
        return f

    # groove polygons (front from front view, back from flipped back view)
    groove = {}
    for side, red_roi in (('f', red[ya:yb, xa:xb]), ('b', red[ya:yb, BX0:BX1][:, ::-1])):
        gm = (red_roi.astype(np.uint8) * (mask[ya:yb, xa:xb] > 0))
        gm = cv2.dilate(gm, np.ones((2, 2), np.uint8))
        gg = outlines(gm, xa, ya, sigma=4.0, eps=GEPS, min_area=GMIN)
        gg.sort(key=lambda g: -cv2.contourArea(g[0].astype(np.float32)))
        groove[side] = gg[:kgroove]

    parts = []
    for (er, sc, bev, do_groove) in layers:
        lm = layer_mask(roi, er)
        loops = outlines(lm, xa, ya, sigma=osig, eps=oeps)
        if not loops: continue
        tf = tf_for(sc)
        o = prism(f'{name}_L{er}', loops, tf)
        bevel_obj(o, bev, 1)
        if do_groove:
            for side in ('f', 'b'):
                cut = []
                for poly in groove[side]:
                    def tfun(x, r, side=side, tf=tf):
                        f, b = tf(x, r)
                        return (f - 6.0, f + groove_depth) if side == 'f' else (b - groove_depth, b + 6.0)
                    cut.append(prism(f'{name}_cut', [(poly[0], [])], tfun))
                if cut:
                    bpy.ops.object.select_all(action='DESELECT')
                    for c in cut: c.select_set(True)
                    bpy.context.view_layer.objects.active = cut[0]
                    if len(cut) > 1: bpy.ops.object.join()
                    boolean(o, bpy.context.active_object, 'DIFFERENCE')
        parts.append(o)
    return join(parts, name)


# ---- grip: smooth lathe, spiral wrap ----
def grip():
    ya, yb = 557, 625; segs = 8
    verts = []; faces = []
    rows = np.arange(ya, yb + 0.01, 68 / 15.0)
    for y in rows:
        rx = fhalf(int(y)) * 0.97; ry = max(shalf(int(y)), 6) * 0.99
        collar = 2.2 * smooth((7 - (y - ya)) / 7) + 1.8 * smooth((y - (yb - 9)) / 9)
        cz = Cz(int(y))
        for sg in range(segs):
            a = 2 * math.pi * sg / segs
            phase = a / (2 * math.pi) + (y - ya) / 14.0
            band = 0.5 + 0.5 * math.cos(2 * math.pi * phase)
            k = 0.88 + 0.14 * band
            verts.append(W(CX + (rx * k + collar) * math.cos(a), y, cz + (ry * k + collar) * math.sin(a)))
    for j in range(len(rows) - 1):
        for sg in range(segs):
            a = j * segs + sg; b = j * segs + (sg + 1) % segs
            faces.append((a, b, b + segs, a + segs))
    for j in (0, len(rows) - 1):
        c = len(verts); verts.append(W(CX, rows[j], Cz(int(rows[j]))))
        for sg in range(segs):
            a = j * segs + sg; b = j * segs + (sg + 1) % segs
            faces.append((c, b, a) if j == 0 else (c, a, b))
    return make_obj('GEO-sword_grip', verts, faces)


def cap_body():
    """Faceted pommel body: rx from the front view, ry from the edge-on view, centred on side centre line."""
    rows = [622, 630, 638, 646, 652, 657]
    segs = 8; verts = []; faces = []
    for r in rows:
        rx = max(fhalf(r), 6) * 0.98; ry = max(shalf(r), 6) * 0.98; cz = Cz(r)
        for sg in range(segs):
            a = 2 * math.pi * (sg + 0.5) / segs
            verts.append(W(CX + rx * math.cos(a), r, cz + ry * math.sin(a)))
    for j in range(len(rows) - 1):
        for sg in range(segs):
            a = j * segs + sg; b = j * segs + (sg + 1) % segs
            faces.append((a, b, b + segs, a + segs))
    for j in (0, len(rows) - 1):
        c = len(verts); verts.append(W(CX, rows[j], Cz(rows[j])))
        for sg in range(segs):
            a = j * segs + sg; b = j * segs + (sg + 1) % segs
            faces.append((c, b, a) if j == 0 else (c, a, b))
    return make_obj('GEO-sword_cap', verts, faces, flat=True)


def lathe_prof(name, prof, segs, flat=True, fin=None):
    """prof: list of (row, radius). Faceted lathe with `segs` sides (angular)."""
    verts = []; faces = []
    for (row, r) in prof:
        for s in range(segs):
            a = 2 * math.pi * (s + 0.5) / segs
            rr = r * (fin(a) if fin else 1.0)
            verts.append(W(CX + rr * math.cos(a), row, Cz(int(row)) + rr * math.sin(a)))
    for j in range(len(prof) - 1):
        for s in range(segs):
            a = j * segs + s; b = j * segs + (s + 1) % segs
            faces.append((a, b, b + segs, a + segs))
    for j in (0, len(prof) - 1):
        c = len(verts); verts.append(W(CX, prof[j][0], 0))
        for s in range(segs):
            a = j * segs + s; b = j * segs + (s + 1) % segs
            faces.append((c, b, a) if j == 0 else (c, a, b))
    return make_obj(name, verts, faces, flat=flat)


def tube(name, p0, p1, p2, r0, r1, n=5, ring=4):
    P = [np.array(p, float) for p in (p0, p1, p2)]
    pts = [(1 - t) ** 2 * P[0] + 2 * (1 - t) * t * P[1] + t * t * P[2] for t in np.linspace(0, 1, n)]
    verts = []; faces = []
    for i, p in enumerate(pts):
        tan = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]); tan /= np.linalg.norm(tan)
        a = np.cross(tan, [1, 0, 0])
        if np.linalg.norm(a) < 1e-3: a = np.cross(tan, [0, 1, 0])
        a /= np.linalg.norm(a); b = np.cross(tan, a)
        r = r0 + (r1 - r0) * (i / (n - 1)) ** 0.8
        for k in range(ring):
            t = 2 * math.pi * k / ring
            q = p + (a * math.cos(t) + b * math.sin(t)) * r
            verts.append(W(q[0], q[1], q[2]))
    for i in range(n - 1):
        for k in range(ring):
            a_ = i * ring + k; b_ = i * ring + (k + 1) % ring
            faces.append((a_, b_, b_ + ring, a_ + ring))
    tip = len(verts); verts.append(W(*pts[-1]))
    for k in range(ring): faces.append(((n - 1) * ring + k, (n - 1) * ring + (k + 1) % ring, tip))
    base = len(verts); verts.append(W(*pts[0]))
    for k in range(ring): faces.append((base, (k + 1) % ring, k))
    return make_obj(name, verts, faces, flat=True)


def gem(name, cx, cy, hw, hh, depth, ybase):
    verts = []; faces = []
    for sgn in (-1, 1):
        base = len(verts)
        verts += [W(cx, cy - hh, sgn * (ybase - 0.5)), W(cx + hw, cy, sgn * (ybase - 0.5)),
                  W(cx, cy + hh, sgn * (ybase - 0.5)), W(cx - hw, cy, sgn * (ybase - 0.5)),
                  W(cx, cy, sgn * (ybase + depth))]
        for i in range(4): faces.append((base + i, base + (i + 1) % 4, base + 4))
        faces.append((base + 3, base + 2, base + 1, base + 0))
    return make_obj('GEO-' + name, verts, faces, flat=True)


def join(objs, name):
    objs = [o for o in objs if o]
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1: bpy.ops.object.join()
    o = bpy.context.active_object; o.name = name
    return o


bpy.ops.wm.read_factory_settings(use_empty=True)

# BLADE: slab with wide crisp edge bevel + raised central spine plate
_xs = np.where(mask[451, FX0:FX1])[0] + FX0
blade = layered_part('blade', Y0, 484, [(0, 0.62, 4.0, True), (10, 1.0, 2.4, True)], 1.5, oeps=8.0, clip=(452, int(_xs.min()), int(_xs.max())))
reduce(blade, 1320)
finish(blade, 0.0, 'GEO-sword_blade')

# GUARD: base slab + stacked bevelled armour plates, tapering toward claw tips
def gtaper(x): return max(1 - 0.70 * min(abs(x - CX) / 92.0, 1) ** 1.2, 0.2)
guard = layered_part('guard', 452, 560, [(0, 0.45, 1.8, False), (6.0, 0.80, 2.2, False), (16.0, 1.0, 2.2, False)], 1.3, osig=5.0, oeps=7.5, use_body=True, kgroove=0)
reduce(guard, 880)
finish(guard, 0.0, 'GEO-sword_guard')

gr = grip()
# cap: octagonal flared pommel body
cap = cap_body()
spike_prof = [(650, 9), (668, 6.5), (688, 3), (704, 0.0)]
spk = lathe_prof('GEO-sword_pommel_spike', spike_prof, 8)
horns = []
cz = Cz(480)
for sx in (-1, 1):
    for sy in (-1, 1):
        horns.append(tube(f'GEO-horn_{sx}_{sy}', (CX + sx * 13, 488, cz + sy * 7), (CX + sx * 14, 486, cz + sy * 13),
                          (CX + sx * 12, 462, cz + sy * 12), 3.6, 0.5))
# long thin forward/back prongs seen in the edge-on view (row ~511)
for sy in (-1, 1):
    horns.append(tube(f'GEO-prong_{sy}', (CX, 511, Cz(511) + sy * 5), (CX, 511, Cz(511) + sy * 16),
                      (CX, 511, Cz(511) + sy * 29), 6.5, 0.3))
horn = join(horns, 'GEO-sword_guard_horns')
g1 = gem('gem_guard', 139.7, 478.8, 8, 12, 5.5, 20)
g2 = gem('gem_cap', 139.4, 641.4, 4.5, 6.5, 3.2, 21)
gems = join([g1, g2], 'GEO-sword_gems')

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
