"""Hand-painted stylised texture for the sword (blender-hand-painted-stylised workflow), built from scratch.

Pipeline
 1. join body parts, smart-UV islands (proper islands, not per-triangle), pack
 2. rasterise UV space -> per-texel world position / normal / part id (paint directly in 2D on the UV layout)
 3. paint (numpy):  value structure (top-down gradient + facet light) -> flat per-part base colours sampled from the
    reference -> warm lit / cool shared shadow (#4C506C) -> coloured AO -> panel hue drift -> crease shadows (concave)
    -> broken edge highlights (convex, mostly up-facing) -> logical wear -> grip strap lines -> painted red seams
 4. glow = separate plain mesh (thin ribbons traced from the reference's crack skeleton + the gems) so it can be Neon in Studio
 5. look calibration against the reference (mean colour / brightness / glow peak), QA renders
Run from models/sword:  python3 texture_sword.py
"""
import bpy, bmesh, cv2, numpy as np, math, os, json
from PIL import Image
from scipy import ndimage as ndi
from skimage.morphology import skeletonize
from mathutils import Vector
from mathutils.bvhtree import BVHTree

REF = 'reference_sheet.png'; SRC = 'sword_model.blend'; OUT = 'sword_model_textured'
TEXDIR = 'textures'; os.makedirs(TEXDIR, exist_ok=True)
AT = 1024
SCALE = 1.2 / 850; CX, ZERO = 139.5, 500
FX0, FX1, BX0, BX1 = 40, 239, 317, 516
R0, R1 = 8, 864
TRI_LIMIT = 3000

rgb = np.array(Image.open(REF).convert('RGB')); rgbi = rgb.astype(int)

# ------------------------------------------------------------------ palette (sampled from the reference)
def region_palette(r0, r1):
    sub = rgbi[r0:r1, FX0:FX1]; lum = sub.sum(2) / 3
    m = (lum < 42) & (lum > 10) & (sub[..., 0] < 1.45 * sub[..., 1] + 6)
    return np.median(sub[m], axis=0) if m.sum() > 20 else np.array([26., 22., 30.])
def hl_palette(r0, r1):
    sub = rgbi[r0:r1, FX0:FX1]; lum = sub.sum(2) / 3
    m = (lum > 55) & (lum < 135) & (sub[..., 0] < 1.5 * sub[..., 1] + 14) & (sub[..., 2] > 0.55 * sub[..., 0])
    return np.median(sub[m], axis=0) if m.sum() > 20 else np.array([88., 72., 100.])
HLPAL = {'blade': hl_palette(11, 452), 'guard': hl_palette(452, 560), 'grip': hl_palette(557, 625), 'cap': hl_palette(622, 657)}
print('HL PALETTE', {k: v.round(0).tolist() for k, v in HLPAL.items()})
PAL = {'blade': region_palette(11, 452), 'guard': region_palette(452, 560), 'grip': region_palette(557, 625), 'cap': region_palette(622, 657)}
print('PALETTE', {k: v.round(1).tolist() for k, v in PAL.items()})
SHADOW = np.array([76., 80., 108.])           # shared cool shadow tint #4C506C
RED_DEEP = np.array([112., 14., 30.])         # painted red seams (non-glowing)
RED_MID = np.array([168., 24., 36.])

# ------------------------------------------------------------------ load, join, UV unwrap
bpy.ops.wm.open_mainfile(filepath=SRC)
PARTS = {'blade': 'blade', 'guard': 'guard', 'grip': 'grip', 'cap': 'cap', 'horns': 'guard', 'spike': 'cap'}
pid_names = ['blade', 'guard', 'grip', 'cap']
body = []; gems = None
for ob in list(bpy.data.objects):
    if ob.type != 'MESH': continue
    if 'gems' in ob.name: gems = ob; continue
    key = next(k for k in PARTS if k in ob.name)
    bm = bmesh.new(); bm.from_mesh(ob.data)
    lay = bm.faces.layers.int.new('part')
    for f in bm.faces: f[lay] = pid_names.index(PARTS[key])
    bm.to_mesh(ob.data); bm.free(); body.append(ob)
bpy.ops.object.select_all(action='DESELECT')
for o in body: o.select_set(True)
bpy.context.view_layer.objects.active = body[0]
bpy.ops.object.join()
bob = bpy.context.active_object; bob.name = 'GEO-sword_body'
bm = bmesh.new(); bm.from_mesh(bob.data)
bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
bm.to_mesh(bob.data); bm.free()

for p in bob.data.polygons: p.use_smooth = False
bpy.ops.object.select_all(action='DESELECT'); bob.select_set(True); bpy.context.view_layer.objects.active = bob
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.004, area_weight=0.6, correct_aspect=True, scale_to_bounds=False)
bpy.ops.uv.pack_islands(margin=0.004)
bpy.ops.object.mode_set(mode='OBJECT')
me = bob.data; uvl = me.uv_layers.active
print('UV islands done; loops', len(me.loops), 'tris', len(me.polygons))

# ------------------------------------------------------------------ geometry info (per-tri, per-vertex)
bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table(); bm.verts.ensure_lookup_table()
play = bm.faces.layers.int['part']
bvh = BVHTree.FromBMesh(bm)
NT = len(bm.faces)
tri_part = np.array([f[play] for f in bm.faces]); tri_n = np.array([tuple(f.normal) for f in bm.faces])
tri_cen = np.array([tuple(f.calc_center_median()) for f in bm.faces])
# convex / concave edge flags -> per tri list of (v_a, v_b, kind) kind: +1 convex hard, -1 concave hard
edge_info = []   # (p, q, kind, tri index)
for e in bm.edges:
    fs = e.link_faces
    if len(fs) != 2: kind = 1
    else:
        a, b = fs
        if a.normal.dot(b.normal) > 0.85: continue
        kind = 1 if (b.calc_center_median() - a.calc_center_median()).dot(a.normal) < 0 else -1
    p, q = e.verts[0].co.copy(), e.verts[1].co.copy()
    for f in fs: edge_info.append((p, q, kind, f.index))

# per-vertex AO (cosine rays, creases only)
vnorm = [Vector((0, 0, 0)) for _ in bm.verts]
for f in bm.faces:
    for v in f.verts: vnorm[v.index] += f.normal
rng = np.random.default_rng(11); AO = np.zeros(len(bm.verts))
for v in bm.verts:
    n = vnorm[v.index].normalized() if vnorm[v.index].length > 1e-9 else Vector((0, 0, 1))
    tng = n.cross(Vector((0.3, 0.8, 0.5))).normalized(); bit = n.cross(tng); occ = 0
    for _ in range(24):
        u1, u2 = rng.random(), rng.random(); r = math.sqrt(u1); ph = 2 * math.pi * u2
        d = tng * (r * math.cos(ph)) + bit * (r * math.sin(ph)) + n * math.sqrt(max(0, 1 - u1))
        if bvh.ray_cast(v.co + n * 0.0006, d, 0.045)[0] is not None: occ += 1
    AO[v.index] = 1 - occ / 24.0
print('AO mean', round(AO.mean(), 3))

# ------------------------------------------------------------------ rasterise UV space -> texel attributes
loops_uv = {}
tri_uv = np.zeros((NT, 3, 2)); tri_v = np.zeros((NT, 3, 3)); tri_vi = np.zeros((NT, 3), int)
for p in me.polygons:
    for k, li in enumerate(p.loop_indices):
        tri_uv[p.index, k] = uvl.data[li].uv
        vi = me.loops[li].vertex_index; tri_vi[p.index, k] = vi; tri_v[p.index, k] = me.vertices[vi].co
tid = -np.ones((AT, AT), np.int32); B1 = np.zeros((AT, AT), np.float32); B2 = np.zeros((AT, AT), np.float32)
for i in range(NT):
    uv = tri_uv[i] * AT; uv[:, 1] = AT - uv[:, 1]       # image coords, y down
    x0, x1 = int(max(0, math.floor(uv[:, 0].min()))), int(min(AT - 1, math.ceil(uv[:, 0].max())))
    y0, y1 = int(max(0, math.floor(uv[:, 1].min()))), int(min(AT - 1, math.ceil(uv[:, 1].max())))
    if x1 < x0 or y1 < y0: continue
    xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
    (ax, ay), (bx, by), (cx, cy) = uv
    den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    if abs(den) < 1e-9: continue
    l1 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / den
    l2 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / den
    l3 = 1 - l1 - l2
    ins = (l1 >= -0.02) & (l2 >= -0.02) & (l3 >= -0.02)
    sub = tid[y0:y1 + 1, x0:x1 + 1]; w = ins & (sub < 0)
    sub[w] = i; B1[y0:y1 + 1, x0:x1 + 1][w] = l1[w]; B2[y0:y1 + 1, x0:x1 + 1][w] = l2[w]
cover = tid >= 0
print('UV coverage', round(float(cover.mean()), 3))
T = np.where(cover, tid, 0)
l1, l2 = B1, B2; l3 = 1 - l1 - l2
V = tri_v[T]                                           # (AT,AT,3,3)
P = l1[..., None] * V[:, :, 0] + l2[..., None] * V[:, :, 1] + l3[..., None] * V[:, :, 2]
N = tri_n[T]; PART = tri_part[T]
ao = l1 * AO[tri_vi[T][..., 0]] + l2 * AO[tri_vi[T][..., 1]] + l3 * AO[tri_vi[T][..., 2]]

# ------------------------------------------------------------------ painting
def noise3(Pp, f):
    return (np.sin(Pp[..., 0] * f * 1.3 + np.sin(Pp[..., 1] * f * 0.7)) + np.sin(Pp[..., 2] * f * 1.1 + Pp[..., 0] * f * 0.4)
            + np.sin((Pp[..., 1] + Pp[..., 2]) * f * 0.9 + Pp[..., 0] * f * 0.3)) / 3.0
def smooth(t): t = np.clip(t, 0, 1); return t * t * (3 - 2 * t)

light = np.array([0.35, -0.55, 0.75]); light /= np.linalg.norm(light)
zt = np.clip((P[..., 2] + 0.55) / 1.25, 0, 1)
lam0 = np.clip((N * light).sum(-1), 0, 1)
# 1) value structure: top-down gradient + facet light, soft 3-step banding (painted, not CG-smooth)
lam = 0.22 + 0.80 * lam0
lam = lam * (0.78 + 0.34 * zt)
# 2) flat base per part, value-first
pal_img = np.zeros(P.shape, np.float32)
for k, name in enumerate(pid_names): pal_img[PART == k] = PAL[name]
# 3) panel hue drift (low frequency only; no grain)
drift = noise3(P, 38.0)
base = pal_img * (1.0 + 0.10 * drift[..., None]) * (1 + 0.06 * np.array([0.6, -0.2, 0.8]) * noise3(P, 21.0)[..., None])
# 4) warm lit / cool shared shadow, coloured AO (multiply ~50%, tinted not black)
hl_img = np.zeros(P.shape, np.float32)
for k, name in enumerate(pid_names): hl_img[PART == k] = HLPAL[name]
sweep = smooth(lam0 * 1.25 - 0.30) * (0.45 + 0.55 * np.clip(0.5 + 0.5 * noise3(P, 17.0), 0, 1))   # painted gloss sweep on lit facets
warm = base * np.array([1.10, 1.0, 0.96]) * (0.45 + 1.15 * lam)[..., None]
warm = warm * (1 - 0.22 * sweep[..., None]) + hl_img * (0.22 * sweep[..., None]) * (0.40 + 0.5 * lam)[..., None]
shade = np.clip((1 - lam) * 0.9 + (1 - ao) * 0.9, 0, 1)[..., None]
col = warm * (1 - 0.55 * shade) + SHADOW * 0.30 * shade
aoc = 0.50 + 0.50 * ao[..., None]                      # AO multiply at ~50%
col = col * (0.5 + 0.5 * aoc) + SHADOW * 0.10 * (1 - aoc)

# 5) crease shadows (concave) + broken edge highlights (convex) from real edge geometry, per texel
hl = np.zeros((AT, AT), np.float32); cr = np.zeros((AT, AT), np.float32)
tri_edges = {}
for (p, q, kind, fi) in edge_info: tri_edges.setdefault(fi, []).append((np.array(p), np.array(q), kind))
Pf = P.reshape(-1, 3); Tf = T.reshape(-1); cov = cover.reshape(-1)
hl_f = np.zeros(AT * AT, np.float32); cr_f = np.zeros(AT * AT, np.float32)
order = np.argsort(Tf, kind='stable'); Ts = Tf[order]
bounds = np.searchsorted(Ts, np.arange(NT + 1))
for fi, edges in tri_edges.items():
    idx = order[bounds[fi]:bounds[fi + 1]]; idx = idx[cov[idx]]
    if len(idx) == 0: continue
    pts = Pf[idx]
    for (p, q, kind) in edges:
        d = q - p; L = max(np.linalg.norm(d), 1e-9); dn = d / L
        t = np.clip(((pts - p) @ dn), 0, L); proj = p + t[:, None] * dn
        dist = np.linalg.norm(pts - proj, axis=1)
        if kind > 0: hl_f[idx] = np.maximum(hl_f[idx], np.clip(1 - dist / 0.0030, 0, 1))
        else: cr_f[idx] = np.maximum(cr_f[idx], np.clip(1 - dist / 0.0055, 0, 1))
hl = hl_f.reshape(AT, AT); cr = cr_f.reshape(AT, AT)
brk = np.clip(0.60 + 0.8 * noise3(P, 80.0), 0, 1)                      # broken up, hand-placed feel
up = np.clip(N[..., 2], 0, 1)
rim = (lam0 < 0.35).astype(np.float32) * np.clip(1 - np.abs(N[..., 1]) * 1.1, 0, 1)
hl = hl * brk * (0.55 + 0.9 * up + 0.45 * lam0)
col = col * (1 - 0.45 * cr[..., None]) + SHADOW * 0.22 * cr[..., None]  # concave crease: cool shadow
col = col + hl[..., None] * np.array([44., 34., 62.]) + (hl * rim)[..., None] * np.array([16., 30., 78.])                  # convex edge: lighter, slightly warm-violet

# 6) logical wear: tiny chips only on convex edges, sparse
chip = np.clip(noise3(P, 260.0) - 0.55, 0, 1) * 4.0 * (hl > 0.35)
col = col + chip[..., None] * np.array([46., 38., 52.])

# 7) grip strap lines (helical seams) on the wrapped grip, hand-painted
gm = PART == pid_names.index('grip')
ang = np.arctan2(P[..., 1], P[..., 0] - (CX - CX) * SCALE)
row = ZERO - P[..., 2] / SCALE
ph = ang / (2 * math.pi) + (row - 557) / 14.0
seam = np.clip(1 - np.abs(((ph + 0.5) % 1.0) - 0.5) / 0.045, 0, 1) * gm
col = col * (1 - 0.5 * seam[..., None]) + SHADOW * 0.12 * seam[..., None]
gm2 = np.clip(0.5 + 0.5 * np.cos(2 * math.pi * ph), 0, 1) * gm
col = col + (gm2 * 0.10)[..., None] * np.array([70., 56., 80.])     # strap highlight rolls with the twist

# 8) painted red (non-glowing seams/bands/halo) traced from the reference; the crack glow itself is a separate mesh
def red_stencils(crop):
    c = crop.astype(int)
    core = ((c[..., 0] > 150) & (c[..., 1] < 95) & (c[..., 2] < 110)).astype(np.float32)
    mid = ((c[..., 0] > 85) & (c[..., 0] > 1.6 * c[..., 1]) & (c[..., 1] < 70)).astype(np.float32)
    hot = ((c[..., 0] > 205) & (c[..., 1] > 55) & (c[..., 0] > 1.35 * c[..., 1])).astype(np.float32)
    return cv2.GaussianBlur(core, (0, 0), 0.6), cv2.GaussianBlur(mid, (0, 0), 1.0), cv2.GaussianBlur(core, (0, 0), 3.4), cv2.GaussianBlur(hot, (0, 0), 0.7)
def fix_bg(crop):
    fg = (crop.astype(int).sum(2) < 3 * 232); fg = cv2.erode(fg.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    idx = ndi.distance_transform_edt(~fg, return_distances=False, return_indices=True); return crop[idx[0], idx[1]]
RF = red_stencils(rgb[R0:R1, FX0:FX1]); RB = red_stencils(rgb[R0:R1, BX0:BX1][:, ::-1].copy())
cols = P[..., 0] / SCALE + CX - FX0; rows = ZERO - P[..., 2] / SCALE - R0
back = N[..., 1] > 0; facing = np.abs(N[..., 1]) >= 0.30
def samp(img): return cv2.remap(img, cols.astype(np.float32), rows.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
corm = np.where(back, samp(RB[0]), samp(RF[0])) * facing
midm = np.where(back, samp(RB[1]), samp(RF[1])) * facing
halo = np.where(back, samp(RB[2]), samp(RF[2])) * facing
hotm = np.where(back, samp(RB[3]), samp(RF[3])) * facing
blade_m = (PART == 0)
# seams / bands on guard, grip, cap are painted red; on the blade the glow ribbon owns the crack, we only paint a soft red bloom on the metal
paint_red = np.clip(midm + corm, 0, 1)
col = col * (1 - 0.55 * paint_red[..., None]) + RED_MID * 0.55 * paint_red[..., None]
col = col * (1 - 0.9 * corm[..., None]) + np.array([226., 38., 38.]) * 0.9 * corm[..., None]
col = col * (1 - hotm[..., None]) + np.array([255., 150., 112.]) * hotm[..., None]
bloom = np.clip(halo * 1.15, 0, 1)
col = col * (1 - 0.70 * bloom[..., None]) + RED_DEEP * 0.70 * bloom[..., None]
EMIS = np.clip(corm[..., None] * np.array([226., 38., 38.]) + hotm[..., None] * np.array([255., 150., 112.]) * 0.9 + midm[..., None] * np.array([150., 18., 28.]) * 0.6 + bloom[..., None] * np.array([120., 14., 30.]) * 0.3, 0, 255)

# ------------------------------------------------------------------ dilate gutters (no seam bleed) and save
col = np.clip(col, 0, 255)
idx = ndi.distance_transform_edt(~cover, return_distances=False, return_indices=True)
col = col[idx[0], idx[1]]
atlas = col.astype(np.uint8)
atlas = np.where(cover[..., None], atlas, atlas)         # all texels valid after dilation
Image.fromarray(atlas).save(f'{TEXDIR}/sword_basecolor.png')
EMIS = EMIS[idx[0], idx[1]] * cover[..., None]
Image.fromarray(EMIS.astype(np.uint8)).save(f'{TEXDIR}/sword_emissive.png')
if os.path.exists(f'{TEXDIR}/sword_roughness.png'): os.remove(f'{TEXDIR}/sword_roughness.png')

# ------------------------------------------------------------------ glow mesh: ribbons traced from the reference crack skeleton + gems
def trace_polylines(mask):
    sk = skeletonize(mask > 0)
    ys, xs = np.nonzero(sk); pts = set(zip(ys.tolist(), xs.tolist()))
    nb = lambda p: [(p[0] + dy, p[1] + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dy or dx) and (p[0] + dy, p[1] + dx) in pts]
    deg = {p: len(nb(p)) for p in pts}
    nodes = {p for p, d in deg.items() if d != 2}
    seen_e = set(); lines = []
    for s in nodes:
        for n0 in nb(s):
            if (s, n0) in seen_e: continue
            path = [s, n0]; seen_e.add((s, n0)); seen_e.add((n0, s)); cur, prev = n0, s
            while cur not in nodes:
                nxt = [q for q in nb(cur) if q != prev]
                if not nxt: break
                prev, cur = cur, nxt[0]; path.append(cur); seen_e.add((prev, cur)); seen_e.add((cur, prev))
            lines.append(path)
    return [np.array([(c, r) for r, c in l], float) for l in lines if len(l) >= 6]

def ribbons_for(core_crop, back_view, budget_tris):
    m = core_crop.copy(); m[(452 - R0):] = 0                       # blade rows only (guard seams stay painted)
    m = cv2.morphologyEx((m > 0).astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    lines = trace_polylines(m)
    lines = [cv2.approxPolyDP(l.astype(np.float32).reshape(-1, 1, 2), 3.0, False)[:, 0, :] for l in lines]
    lines = [l for l in lines if len(l) >= 2]
    lines.sort(key=lambda l: -np.linalg.norm(np.diff(l, axis=0), axis=1).sum())
    chosen = []; used = 0
    for l in lines:
        cost = 2 * (len(l) - 1)
        if used + cost > budget_tris:
            keep = (budget_tris - used) // 2 + 1          # truncate to what is left
            if keep >= 2: chosen.append(l[:keep]); used += 2 * (keep - 1)
            continue
        chosen.append(l); used += cost
    return chosen, used

c_f = ((rgbi[R0:R1, FX0:FX1, 0] > 115) & (rgbi[R0:R1, FX0:FX1, 0] > 2.0 * rgbi[R0:R1, FX0:FX1, 1]) & (rgbi[R0:R1, FX0:FX1, 2] < 120)).astype(np.uint8)
c_b = ((rgbi[R0:R1, BX0:BX1, 0] > 115) & (rgbi[R0:R1, BX0:BX1, 0] > 2.0 * rgbi[R0:R1, BX0:BX1, 1]) & (rgbi[R0:R1, BX0:BX1, 2] < 120)).astype(np.uint8)[:, ::-1].copy()
gem_tris = sum(len(p.vertices) - 2 for p in gems.data.polygons) if gems else 0
body_tris = sum(len(p.vertices) - 2 for p in me.polygons)
budget = 0 if os.environ.get('RIBBONS', '0') != '1' else TRI_LIMIT - 20 - body_tris - gem_tris
print('glow ribbon budget tris', budget)
gm_bm = bmesh.new(); W_PX = 1.5
bvh2 = BVHTree.FromBMesh(bm)
def surf_y(x, z, back_view):
    # nearest-to-viewer surface within ~2.5px so the ribbon rides on the groove opening and is never buried
    best = None
    for dx, dz in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
        origin = Vector((x + dx * 2.5 * SCALE, 2.0 if back_view else -2.0, z + dz * 2.5 * SCALE)); d = Vector((0, -1 if back_view else 1, 0))
        h = bvh2.ray_cast(origin, d)
        if h[0] is None: continue
        y = h[0].y
        best = y if best is None else (max(best, y) if back_view else min(best, y))
    return best
used_total = 0
for back_view, core in ((False, c_f), (True, c_b)):
    chosen, used = (ribbons_for(core, back_view, budget // 2) if budget > 0 else ([], 0)); used_total += used
    for li, l in enumerate(chosen):
        pts = [((c + FX0 - CX) * SCALE, -((r + R0) - ZERO) * SCALE) for c, r in l]       # (x, z) in metres
        n = len(pts); left = []; right = []
        for i, (x, z) in enumerate(pts):
            a = np.array(pts[max(i - 1, 0)]); b = np.array(pts[min(i + 1, n - 1)]); t = b - a
            t = t / (np.linalg.norm(t) + 1e-12); nrm = np.array([-t[1], t[0]])
            taper = 0.55 + 0.45 * math.sin(math.pi * (i + 0.5) / n)
            hw = 0.5 * W_PX * SCALE * taper
            for sgn, store in ((1, left), (-1, right)):
                px, pz = x + nrm[0] * hw * sgn, z + nrm[1] * hw * sgn
                y = surf_y(px, pz, back_view)
                if y is None: y = 0.0
                y += (0.00045 if back_view else -0.00045) * 0.0 + (SCALE * (1.3 + 0.03 * li)) * (1 if back_view else -1)
                store.append(gm_bm.verts.new((px, y, pz)))
        for i in range(n - 1):
            quad = (left[i], left[i + 1], right[i + 1], right[i]) if not back_view else (left[i], right[i], right[i + 1], left[i + 1])
            try: gm_bm.faces.new(quad)
            except ValueError: pass
bmesh.ops.triangulate(gm_bm, faces=gm_bm.faces[:])
bmesh.ops.recalc_face_normals(gm_bm, faces=gm_bm.faces[:])
gme = bpy.data.meshes.new('GEO-sword_glowM'); gm_bm.to_mesh(gme); gm_bm.free()
glow = bpy.data.objects.new('GEO-sword_glow', gme); bpy.context.collection.objects.link(glow)
if gems:
    bpy.ops.object.select_all(action='DESELECT'); glow.select_set(True); gems.select_set(True)
    bpy.context.view_layer.objects.active = glow; bpy.ops.object.join(); glow = bpy.context.active_object; glow.name = 'GEO-sword_glow'
bm.free()
print('glow tris', sum(len(p.vertices) - 2 for p in glow.data.polygons))

# ------------------------------------------------------------------ materials + look calibration
def img(path, cs):
    im = bpy.data.images.load(os.path.abspath(path), check_existing=False); im.colorspace_settings.name = cs; im.pack(); return im
BASE_ATLAS = np.array(Image.open(f'{TEXDIR}/sword_basecolor.png').convert('RGB')).astype(np.float32) / 255.0
def bake_gain(gain):
    lin = np.power(BASE_ATLAS, 2.2) * gain
    Image.fromarray((np.power(np.clip(lin, 0, 1), 1 / 2.2) * 255 + 0.5).astype(np.uint8)).save(f'{TEXDIR}/sword_basecolor_cal.png')

def build_mats(gain, glow_strength):
    bake_gain(gain)
    for m in list(bpy.data.materials): bpy.data.materials.remove(m)
    mat = bpy.data.materials.new('MAT-sword_body'); mat.use_nodes = True
    nt = mat.node_tree; bs = nt.nodes['Principled BSDF']
    tb = nt.nodes.new('ShaderNodeTexImage'); tb.image = img(f'{TEXDIR}/sword_basecolor_cal.png', 'sRGB'); tb.interpolation = 'Linear'
    nt.links.new(tb.outputs['Color'], bs.inputs['Base Color'])
    te = nt.nodes.new('ShaderNodeTexImage'); te.image = img(f'{TEXDIR}/sword_emissive.png', 'sRGB'); nt.links.new(te.outputs['Color'], bs.inputs['Emission Color']); bs.inputs['Emission Strength'].default_value = 1.6
    bs.inputs['Metallic'].default_value = 0.0; bs.inputs['Roughness'].default_value = 0.7
    bs.inputs['Specular IOR Level'].default_value = 0.1
    gmat = bpy.data.materials.new('MAT-sword_glow'); gmat.use_nodes = True
    g = gmat.node_tree.nodes['Principled BSDF']
    g.inputs['Base Color'].default_value = (0.6, 0.0, 0.02, 1)
    g.inputs['Emission Color'].default_value = (1.0, 0.05, 0.04, 1); g.inputs['Emission Strength'].default_value = glow_strength
    g.inputs['Roughness'].default_value = 0.3
    for ob_, m_ in ((bob, mat), (glow, gmat)): ob_.data.materials.clear(); ob_.data.materials.append(m_)

def stats_of(a_rgb, m):
    px = a_rgb[m].astype(np.float32); hsv = cv2.cvtColor(a_rgb, cv2.COLOR_RGB2HSV)[m].astype(np.float32); lum = px.mean(1)
    red = ((px[:, 0] > 140) & (px[:, 1] < 90) & (px[:, 2] < 100))
    return dict(mean_rgb=px.mean(0).round(1).tolist(), lum_mean=float(lum.mean()), lum_p95=float(np.percentile(lum, 95)),
                sat_mean=float(hsv[:, 1].mean()), red_frac=float(red.mean()))
ref_front = rgb[R0:R1, FX0:FX1]; ref_mask = (ref_front.astype(int).sum(2) < 3 * 232); cut = 650 - R0; ref_mask[cut:] = False
REFSTAT = stats_of(ref_front, ref_mask); print('REF LOOK', REFSTAT)

sc = bpy.context.scene
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = 16; sc.cycles.use_denoising = False
sc.render.film_transparent = True; sc.view_settings.view_transform = 'Standard'
sc.world = bpy.data.worlds.new('cal'); sc.world.use_nodes = True
sc.world.node_tree.nodes['Background'].inputs['Color'].default_value = (1, 1, 1, 1)
sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.0
cam = bpy.data.objects.new('cal_cam', bpy.data.cameras.new('cal_cam')); bpy.context.collection.objects.link(cam)
cam.data.type = 'ORTHO'; cam.data.ortho_scale = 850 * SCALE; sc.camera = cam
H = 850; sc.render.resolution_x = sc.render.resolution_y = H
cam.location = (0, -3, -((11 + 861) / 2 - 500) * SCALE); cam.rotation_euler = (math.pi / 2, 0, 0)

def render_stats(tag):
    sc.render.filepath = os.path.abspath(f'calib_{tag}.png'); sc.render.image_settings.color_mode = 'RGBA'
    bpy.ops.render.render(write_still=True)
    im = np.array(Image.open(f'calib_{tag}.png').convert('RGBA')); alpha = im[..., 3] > 128
    x0 = int(round(425 - (139.5 - FX0)))
    crop = im[:, x0:x0 + (FX1 - FX0), :3]; am = alpha[:, x0:x0 + (FX1 - FX0)]
    rc = np.zeros((R1 - R0, FX1 - FX0, 3), np.uint8); rm = np.zeros((R1 - R0, FX1 - FX0), bool)
    r_lo = max(0, 11 - R0); src_lo = max(0, R0 - 11); n_rows = min(R1 - R0 - r_lo, H - src_lo)
    rc[r_lo:r_lo + n_rows] = crop[src_lo:src_lo + n_rows]; rm[r_lo:r_lo + n_rows] = am[src_lo:src_lo + n_rows]; rm[cut:] = False
    return stats_of(rc, rm)

gain, gl = 1.0, 3.0; history = []
for it in range(6):
    build_mats(gain, gl); st = render_stats(f'it{it}'); history.append(dict(it=it, gain=gain, glow=gl, **st))
    print('CAL', it, 'gain', round(gain, 3), 'glow', round(gl, 2), '->', st)
    gain = float(np.clip(gain * REFSTAT['lum_mean'] / max(st['lum_mean'], 1), 0.2, 2.5))
    gl = float(np.clip(gl * (REFSTAT['lum_p95'] / max(st['lum_p95'], 1)) ** 1.5, 0.5, 12.0))
build_mats(gain, gl)
os.replace(f'{TEXDIR}/sword_basecolor_cal.png', f'{TEXDIR}/sword_basecolor.png') if False else None
json.dump(dict(ref=REFSTAT, history=history, final=dict(gain=gain, glow=gl)), open('look_fit_report.json', 'w'), indent=1)
bpy.data.objects.remove(cam); sc.render.film_transparent = False
bpy.ops.object.select_all(action='DESELECT'); bob.select_set(True); glow.select_set(True)
bpy.ops.wm.save_as_mainfile(filepath=OUT + '.blend')
bpy.ops.export_scene.gltf(filepath=OUT + '.glb', export_format='GLB', use_selection=True, export_apply=True)
tb_ = sum(len(p.vertices) - 2 for p in bob.data.polygons); tg_ = sum(len(p.vertices) - 2 for p in glow.data.polygons)
print('FINAL tris', tb_ + tg_, 'body', tb_, 'glow', tg_)
print('SAVED', OUT)
