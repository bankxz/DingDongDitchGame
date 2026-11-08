"""Hybrid texture (roblox-r6-character-from-reference recipe) for the 2880-tri sword.
 - every triangle gets its own UV rectangle (shelf packed, gutter+clamped-bary dilation => no seams/bleed)
 - candidate B (baked): per-texel projection of the reference front/back view, with occlusion + background-leak tests
 - candidate A (painted): reference-sampled dark-metal palette, fbm variation, fixed-light shading, hard-edge highlights
 - glowing crack floors (strongly red baked triangles) are split into a separate plain Glow mesh (Neon in Studio)
 - remaining red accents -> emissive map; gems -> Glow material
 - look calibration against the reference (mean colour / brightness / saturation / red extent)
Run from models/sword:  python3 texture_sword_v2.py
"""
import bpy, bmesh, cv2, numpy as np, math, os, json, sys
from PIL import Image
from scipy import ndimage as ndi
from mathutils import Vector
from mathutils.bvhtree import BVHTree

REF = 'reference_sheet.png'
SRC = 'sword_model.blend'
OUT = 'sword_model_textured'
TEXDIR = 'textures'; os.makedirs(TEXDIR, exist_ok=True)
AT = 1024
SCALE = 1.2 / 850; CX, ZERO = 139.5, 500
FX0, FX1, BX0, BX1 = 40, 239, 317, 516
R0, R1 = 8, 864

rgb = np.array(Image.open(REF).convert('RGB'))
rgbi = rgb.astype(int)


def fill_bg(crop):
    fg = (crop.astype(int).sum(2) < 3 * 232)
    fg = cv2.erode(fg.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    idx = ndi.distance_transform_edt(~fg, return_distances=False, return_indices=True)
    out = crop[idx[0], idx[1]]
    return out, fg


FRONT, FG_F = fill_bg(rgb[R0:R1, FX0:FX1])
BACK, FG_B = fill_bg(rgb[R0:R1, BX0:BX1][:, ::-1].copy())
# mild unsharp so the low-res source reads crisper when magnified
def sharpen(a):
    b = cv2.GaussianBlur(a, (0, 0), 1.0)
    return np.clip(a.astype(np.float32) * 1.5 - b.astype(np.float32) * 0.5, 0, 255).astype(np.uint8)
FRONT, BACK = sharpen(FRONT), sharpen(BACK)

# ---- palette sampled from the reference (dark metal per region) ----
def region_palette(r0, r1):
    sub = rgbi[r0:r1, FX0:FX1]
    lum = sub.sum(2) / 3
    m = (lum < 42) & (lum > 10) & (sub[..., 0] < 1.45 * sub[..., 1] + 6)
    return np.median(sub[m], axis=0) if m.sum() > 20 else np.array([26, 22, 30.])
PAL = {'blade': region_palette(11, 452), 'guard': region_palette(452, 560), 'grip': region_palette(557, 625),
       'cap': region_palette(622, 657)}
print('PALETTE', {k: v.round(1).tolist() for k, v in PAL.items()})

# ---- load model, join body parts, tag part ids ----
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
bm.faces.ensure_lookup_table(); bm.edges.ensure_lookup_table()
play = bm.faces.layers.int['part']
tris = []
for f in bm.faces:
    vs = [v.co.copy() for v in f.verts]
    tris.append(dict(v=vs, n=f.normal.copy(), part=f[play], face=f))
NT = len(tris)
print('TRIS', NT)
bvh = BVHTree.FromBMesh(bm)

# hard-edge flags: per tri, which of its 3 edges are hard (dihedral)
for t in tris:
    f = t['face']; hard = []
    for i in range(3):
        e = f.edges[i]
        others = [g for g in e.link_faces if g is not f]
        hard.append((not others) or (f.normal.dot(others[0].normal) < 0.85))
    # f.edges order is not vert order; recompute by vertex pair
    t['hard'] = {}
    for e in f.edges:
        others = [g for g in e.link_faces if g is not f]
        h = (not others) or (f.normal.dot(others[0].normal) < 0.85)
        t['hard'][frozenset((e.verts[0].index, e.verts[1].index))] = h
    t['vidx'] = [v.index for v in f.verts]

# ---- per-triangle 2D frames, rect sizes ----
for t in tris:
    a, b, c = t['v']; n = t['n']
    e1 = (b - a); L1 = e1.length
    if L1 < 1e-9: e1 = (c - a); L1 = e1.length
    e1n = e1.normalized(); e2 = n.cross(e1n).normalized()
    pts = [((p - a).dot(e1n), (p - a).dot(e2)) for p in (a, b, c)]
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    t['pts'] = pts; t['o'] = (min(xs), min(ys)); t['wh'] = (max(xs) - min(xs), max(ys) - min(ys))
    t['frame'] = (a, e1n, e2)

PAD, GUT = 3, 3
def pack(D):
    rects = []
    for i, t in enumerate(tris):
        w = int(math.ceil(t['wh'][0] * D)) + 2 * PAD; h = int(math.ceil(t['wh'][1] * D)) + 2 * PAD
        rects.append((i, max(w, 2 * PAD + 2), max(h, 2 * PAD + 2)))
    order = sorted(rects, key=lambda r: -r[2])
    x = y = rowh = 0; place = {}
    for i, w, h in order:
        if x + w > AT: x = 0; y += rowh + GUT; rowh = 0
        if y + h > AT: return None
        place[i] = (x, y, w, h); x += w + GUT; rowh = max(rowh, h)
    return place

lo, hi = 100.0, 4000.0; best = None
for _ in range(14):
    mid = (lo + hi) / 2; p = pack(mid)
    if p: lo = mid; best = (mid, p)
    else: hi = mid
D, PLACE = best
print('TEXEL DENSITY px/unit', round(D, 1), '(reference ~', round(850 / 1.2, 1), 'px/unit)')

# ---- fill ----
atlas = np.zeros((AT, AT, 3), np.uint8); atlas[:] = (30, 26, 32)
rng = np.random.default_rng(3)
light = Vector((0.35, -0.55, 0.75)).normalized()

def fbm(shape, seed):
    r = np.random.default_rng(seed); out = np.zeros(shape, np.float32); amp = 1.0; tot = 0
    for o in range(4):
        s = max(2, int(max(shape) / (2 ** (3 - o) * 3)))
        small = r.random((max(2, shape[0] // s + 2), max(2, shape[1] // s + 2))).astype(np.float32)
        out += amp * cv2.resize(small, (shape[1], shape[0]), interpolation=cv2.INTER_CUBIC); tot += amp; amp *= 0.5
    return out / tot

def sample_ref(img, cols, rows):
    return cv2.remap(img, cols.astype(np.float32), rows.astype(np.float32), cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

stats = dict(B=0, A=0, occluded=0, bgleak=0, mismatch=0, glow=0, side=0)
glow_ids = set(); isB = np.zeros(NT, bool)
UV = [None] * NT
for i, t in enumerate(tris):
    x0, y0, w, h = PLACE[i]
    a, e1, e2 = t['frame']; ox, oy = t['o']
    pxs, pys = np.meshgrid(np.arange(w) + 0.5, np.arange(h) + 0.5)
    lx = (pxs - PAD) / D + ox; ly = (pys - PAD) / D + oy
    (ax_, ay_), (bx_, by_), (cx_, cy_) = t['pts']
    den = (by_ - cy_) * (ax_ - cx_) + (cx_ - bx_) * (ay_ - cy_)
    if abs(den) < 1e-12: den = 1e-12
    l1 = ((by_ - cy_) * (lx - cx_) + (cx_ - bx_) * (ly - cy_)) / den
    l2 = ((cy_ - ay_) * (lx - cx_) + (ax_ - cx_) * (ly - cy_)) / den
    l3 = 1 - l1 - l2
    # clamp to triangle (dilation without seams)
    l1c, l2c, l3c = np.clip(l1, 0, None), np.clip(l2, 0, None), np.clip(l3, 0, None)
    s = np.maximum(l1c + l2c + l3c, 1e-9); l1c, l2c, l3c = l1c / s, l2c / s, l3c / s
    va, vb, vc = t['v']
    P = np.stack([l1c * va[k] + l2c * vb[k] + l3c * vc[k] for k in range(3)], -1)
    n = t['n']; part = pid_names[t['part']]
    # ---- A: painted ----
    pal = PAL[part]
    nz = fbm((h, w), i)
    base = pal[None, None, :] * (0.93 + 0.14 * nz[..., None])
    lam = 0.80 + 0.32 * max(n.dot(light), 0.0)
    A = base * lam
    # hard-edge highlight: distance to hard edges in 2D frame
    vids = t['vidx']; P2 = t['pts']
    hl = np.zeros((h, w), np.float32)
    for (ia, ib) in ((0, 1), (1, 2), (2, 0)):
        if t['hard'].get(frozenset((vids[ia], vids[ib])), False):
            p, q = np.array(P2[ia]), np.array(P2[ib]); d = q - p; L = max(np.hypot(*d), 1e-9)
            dist = np.abs((lx - p[0]) * d[1] - (ly - p[1]) * d[0]) / L
            hl = np.maximum(hl, np.clip(1 - dist / 0.0035, 0, 1))
    A = A * (1 + 0.55 * hl[..., None]) + 14 * hl[..., None]
    A = np.clip(A, 0, 255)
    colour = A; used = 'A'
    # ---- B: baked from the reference ----
    facing = abs(n.y) >= 0.35
    if facing:
        back = n.y > 0
        cam = Vector((0, 1, 0)) if back else Vector((0, -1, 0))
        # occlusion test (centroid + 3 shrunk vertex points)
        cen = (va + vb + vc) / 3
        free = 0
        for q in (cen, cen * 0.5 + va * 0.5, cen * 0.5 + vb * 0.5, cen * 0.5 + vc * 0.5):
            hit = bvh.ray_cast(q + n * 0.0004, cam)
            if hit[0] is None: free += 1
        if free < 3:
            stats['occluded'] += 1
        else:
            cols = (P[..., 0] / SCALE + CX - FX0); rows = (ZERO - P[..., 2] / SCALE - R0)
            src = BACK if back else FRONT
            Bc = sample_ref(src, cols, rows).astype(np.float32)
            mx = Bc.max(2); mn = Bc.min(2)
            leak = ((mx > 150) & (mx - mn < 32)).mean()
            fgm = (FG_B if back else FG_F)
            inside = sample_ref(fgm.astype(np.uint8) * 255, cols, rows) > 128
            if leak > 0.04 or inside.mean() < 0.85:
                stats['bgleak'] += 1
            else:
                dd = np.abs(Bc.mean((0, 1)) - A.mean((0, 1))).max()
                nonred = ~((Bc[..., 0] > 105) & (Bc[..., 0] > 1.7 * Bc[..., 1]))
                if nonred.any() and np.abs(Bc[nonred].mean(0) - A[nonred].mean(0)).max() > 70:
                    stats['mismatch'] += 1
                else:
                    colour = Bc; used = 'B'
                    redfrac = (~nonred).mean()
                    pass  # crack glow stays in the emissive map (thin lines); only gems are a separate Glow mesh
    if used == 'B': stats['B'] += 1; isB[i] = True
    else:
        stats['A'] += 1
        if not facing: stats['side'] += 1
    atlas[y0:y0 + h, x0:x0 + w] = np.clip(colour, 0, 255).astype(np.uint8)
    # uv of the 3 corners (v up)
    uvs = []
    for (px_, py_) in t['pts']:
        u = (x0 + PAD + (px_ - ox) * D) / AT; v = 1 - (y0 + PAD + (py_ - oy) * D) / AT
        uvs.append((u, v))
    UV[i] = uvs
print('STATS', stats, 'glow tris', len(glow_ids))

Image.fromarray(atlas).save(f'{TEXDIR}/sword_basecolor.png')
a_ = atlas.astype(int)
redm = ((a_[..., 0] > 105) & (a_[..., 1] < 90) & (a_[..., 2] < 90) & (a_[..., 0] > 1.7 * a_[..., 1])).astype(np.float32)
redm = cv2.GaussianBlur(redm, (0, 0), 0.8)
Image.fromarray((atlas * redm[..., None]).astype(np.uint8)).save(f'{TEXDIR}/sword_emissive.png')

# ---- write per-triangle UVs; split glow triangles ----
uvl = bm.loops.layers.uv.new('UVMap')
for i, t in enumerate(tris):
    f = t['face']
    for loop, uv in zip(f.loops, UV[i]):
        loop[uvl].uv = uv
# glow split
glow_faces = [tris[i]['face'] for i in glow_ids]
bpy.ops.object.mode_set(mode='OBJECT')
bm.to_mesh(bob.data)
body_mesh = bob.data
bm.free()

# split glow faces into a new object
bm2 = bmesh.new(); bm2.from_mesh(bob.data); bm2.faces.ensure_lookup_table()
gset = [bm2.faces[i] for i in sorted(glow_ids)]
gm = bpy.data.meshes.new('GEO-sword_glowM'); gb = bmesh.new()
vmap = {}
guv = gb.loops.layers.uv.new('UVMap'); uvsrc = bm2.loops.layers.uv['UVMap']
for f in gset:
    nv = []
    for v in f.verts:
        if v.index not in vmap: vmap[v.index] = gb.verts.new(v.co)
        nv.append(vmap[v.index])
    try: nf = gb.faces.new(nv)
    except ValueError: continue
gb.to_mesh(gm); gb.free()
bmesh.ops.delete(bm2, geom=gset, context='FACES')
bm2.to_mesh(bob.data); bm2.free()
glow = bpy.data.objects.new('GEO-sword_glow', gm); bpy.context.collection.objects.link(glow)
# gems join into the glow object
if gems:
    bpy.ops.object.select_all(action='DESELECT'); glow.select_set(True); gems.select_set(True)
    bpy.context.view_layer.objects.active = glow; bpy.ops.object.join()
    glow = bpy.context.active_object; glow.name = 'GEO-sword_glow'
for p in bob.data.polygons: p.use_smooth = False
bob.data.update()

# ---- materials ----
def img(path, cs):
    im = bpy.data.images.load(os.path.abspath(path), check_existing=False); im.colorspace_settings.name = cs; im.pack(); return im
def build_mats(base_gain, emis_strength, glow_strength, metallic=0.0, rough=0.7):
    for m in list(bpy.data.materials): bpy.data.materials.remove(m)
    mat = bpy.data.materials.new('MAT-sword_body'); mat.use_nodes = True
    nt = mat.node_tree; bs = nt.nodes['Principled BSDF']
    tb = nt.nodes.new('ShaderNodeTexImage'); tb.image = img(f'{TEXDIR}/sword_basecolor.png', 'sRGB')
    te = nt.nodes.new('ShaderNodeTexImage'); te.image = img(f'{TEXDIR}/sword_emissive.png', 'sRGB')
    for tx in (tb, te): tx.interpolation = 'Linear'
    hsv = nt.nodes.new('ShaderNodeHueSaturation'); hsv.inputs['Value'].default_value = base_gain
    nt.links.new(tb.outputs['Color'], hsv.inputs['Color']); nt.links.new(hsv.outputs['Color'], bs.inputs['Base Color'])
    nt.links.new(te.outputs['Color'], bs.inputs['Emission Color'])
    bs.inputs['Emission Strength'].default_value = emis_strength
    bs.inputs['Metallic'].default_value = metallic; bs.inputs['Roughness'].default_value = rough
    bs.inputs['Specular IOR Level'].default_value = 0.1
    gmat = bpy.data.materials.new('MAT-sword_glow'); gmat.use_nodes = True
    g = gmat.node_tree.nodes['Principled BSDF']
    g.inputs['Base Color'].default_value = (0.6, 0.0, 0.02, 1)
    g.inputs['Emission Color'].default_value = (1.0, 0.03, 0.03, 1); g.inputs['Emission Strength'].default_value = glow_strength
    g.inputs['Roughness'].default_value = 0.2
    for ob_, m_ in ((bob, mat), (glow, gmat)):
        ob_.data.materials.clear(); ob_.data.materials.append(m_)
    return mat, gmat

# ---- look calibration vs reference ----
def stats_of(a_rgb, mask):
    px = a_rgb[mask].astype(np.float32)
    hsv = cv2.cvtColor(a_rgb, cv2.COLOR_RGB2HSV)[mask].astype(np.float32)
    lum = px.mean(1)
    red = ((px[:, 0] > 140) & (px[:, 1] < 90) & (px[:, 2] < 100))
    return dict(mean_rgb=px.mean(0).round(1).tolist(), lum_mean=float(lum.mean()), lum_p95=float(np.percentile(lum, 95)),
                sat_mean=float(hsv[:, 1].mean()), red_frac=float(red.mean()))

ref_front = rgb[R0:R1, FX0:FX1]
ref_mask = (ref_front.astype(int).sum(2) < 3 * 232)
# restrict to the kept sword body (no chain/star): rows < 650 in sheet coords
cut = 650 - R0
ref_mask[cut:] = False
REFSTAT = stats_of(ref_front, ref_mask)
print('REF LOOK', REFSTAT)

sc = bpy.context.scene
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = 16; sc.cycles.use_denoising = False
sc.render.film_transparent = True; sc.view_settings.view_transform = 'Standard'
sc.world = bpy.data.worlds.new('cal'); sc.world.use_nodes = True
sc.world.node_tree.nodes['Background'].inputs['Color'].default_value = (1, 1, 1, 1)
sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.0
cam = bpy.data.objects.new('cal_cam', bpy.data.cameras.new('cal_cam')); bpy.context.collection.objects.link(cam)
cam.data.type = 'ORTHO'; cam.data.ortho_scale = 850 * SCALE
sc.camera = cam
sun = bpy.data.objects.new('cal_sun', bpy.data.lights.new('cal_sun', 'SUN')); sun.data.energy = 0.0
sun.rotation_euler = (math.radians(50), math.radians(8), math.radians(-25)); bpy.context.collection.objects.link(sun)
H = 850
sc.render.resolution_x = sc.render.resolution_y = H
cam.location = (0, -3, -((11 + 861) / 2 - 500) * SCALE); cam.rotation_euler = (math.pi / 2, 0, 0)

def render_stats(tag):
    sc.render.filepath = os.path.abspath(f'calib_{tag}.png'); sc.render.image_settings.color_mode = 'RGBA'
    bpy.ops.render.render(write_still=True)
    im = np.array(Image.open(f'calib_{tag}.png').convert('RGBA'))
    alpha = im[..., 3] > 128
    x0 = int(round(425 - (139.5 - FX0)))
    crop = im[:, x0:x0 + (FX1 - FX0), :3]; am = alpha[:, x0:x0 + (FX1 - FX0)]
    # align rows: sheet row r -> render row r - 11 + (850-850)/... render spans sheet rows 11..861
    top = R0 - 11
    rc = np.zeros((R1 - R0, FX1 - FX0, 3), np.uint8); rm = np.zeros((R1 - R0, FX1 - FX0), bool)
    r_lo = max(0, 11 - R0)
    src_lo = max(0, R0 - 11)
    n_rows = min(R1 - R0 - r_lo, H - src_lo)
    rc[r_lo:r_lo + n_rows] = crop[src_lo:src_lo + n_rows]; rm[r_lo:r_lo + n_rows] = am[src_lo:src_lo + n_rows]
    rm[cut:] = False
    return stats_of(rc, rm), rc, rm

gain, emis, gl = 1.0, 2.0, 2.2
history = []
for it in range(6):
    build_mats(gain, emis, gl)
    st, rc, rm = render_stats(f'it{it}')
    history.append(dict(it=it, gain=gain, emis=emis, glow=gl, **st))
    print('CAL', it, 'gain', round(gain, 3), 'emis', round(emis, 2), 'glow', round(gl, 2), '->', st)
    # brightness: match mean luminance of non-red body; red: match red fraction / peak
    kb = REFSTAT['lum_mean'] / max(st['lum_mean'], 1)
    gain = float(np.clip(gain * kb, 0.3, 2.5))
    kr = (REFSTAT['lum_p95'] / max(st['lum_p95'], 1)) ** 1.5
    emis = float(np.clip(emis * kr, 0.3, 8.0)); gl = float(np.clip(gl * kr, 0.5, 8.0))
mat, gmat = build_mats(gain, emis, gl)
json.dump(dict(ref=REFSTAT, history=history, final=dict(gain=gain, emission=emis, glow=gl)), open('look_fit_report.json', 'w'), indent=1)

# clean calibration helpers out, save + export
for o in (cam, sun): bpy.data.objects.remove(o)
sc.render.film_transparent = False
bpy.ops.object.select_all(action='DESELECT'); bob.select_set(True); glow.select_set(True)
bpy.ops.wm.save_as_mainfile(filepath=OUT + '.blend')
bpy.ops.export_scene.gltf(filepath=OUT + '.glb', export_format='GLB', use_selection=True, export_apply=True)
tri_total = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in (bob, glow))
print('FINAL tris', tri_total, 'body', sum(len(p.vertices) - 2 for p in bob.data.polygons), 'glow', sum(len(p.vertices) - 2 for p in glow.data.polygons))
print('SAVED', OUT)
