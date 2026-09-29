"""Stage 1: Lava Horse meshes (one object per material slot), geometric studs, neon crack strips,
per-face atlas UVs and painted textures.   python3 build.py -> out/LavaHorse_stage1.blend"""
import os, sys, json, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from PIL import Image
from cube import chunk_faces, _inside
import design as D

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'build') + '/'
TEX = OUT + 'textures/'
W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'build') + '/'
PAD = 2

# stud grid per style: (pitch, half size, height) in ref px. Studs are PAINTED (colour + normal map) on one fixed
# grid per style, centred on every flat face: identical size and spacing everywhere, zero triangles.
STUD = {'body': (26.0, 5.5, 3.2), 'snout': (26.0, 5.5, 3.2), 'muzzle': (22.0, 5.0, 3.0), 'hoof': (20.0, 5.0, 3.0),
        'armour': (16.0, 4.4, 2.8), 'mane': (20.0, 4.4, 2.4), 'tail': (20.0, 4.4, 2.4)}
PALETTE = {  # albedo (sRGB 0-255), sampled from the reference sheet
    'body': (198, 44, 20), 'snout': (186, 42, 20), 'muzzle': (118, 36, 22), 'ear': (112, 44, 34),
    'ear_in': (64, 26, 22), 'hoof': (52, 45, 45), 'armour': (82, 42, 34), 'crack': (255, 206, 62),
    'eye': (246, 242, 238), 'pupil': (16, 14, 14), 'glow': (255, 92, 14), 'glow_hot': (255, 176, 44),
}
FIRE = [(0.0, (228, 58, 10)), (0.5, (255, 116, 20)), (0.82, (255, 176, 36)), (1.0, (255, 226, 76))]
ATLAS = {D.BODY: 1024, D.MANE: 1024, D.TAIL: 1024, D.HOOVES: 512, D.ARMOUR: 1024, D.CRACKS: 64, D.EYES: 64}
SS = 2                    # supersampling for painted tiles (anti-aliased stud / crack edges)
SHARED = ('crack', 'hidden')
VEINS = []


def srgb(c):
    return np.array(c, np.float32) / 255.0


# ------------------------------------------------------------------ face frames for crack placement
def face_frame(c, direction):
    direction = np.array(direction, float)
    best = None
    for k in range(3):
        for s in (-1, 1):
            d = (c['R'][:, k] * s) @ direction
            if best is None or d > best[0]:
                best = (d, k, s)
    _, k, s = best
    others = [i for i in range(3) if i != k]
    wn = c['R'][:, k] * s
    if abs(wn[0]) > 0.7:
        ua, va = np.array((0, 1.0, 0)), np.array((0, 0, 1.0))
    elif abs(wn[1]) > 0.7:
        ua, va = np.array((1.0, 0, 0)), np.array((0, 0, 1.0))
    else:
        ua, va = np.array((1.0, 0, 0)), np.array((0, 1.0, 0))
    iu = max(others, key=lambda i: abs(c['R'][:, i] @ ua))
    iv = [i for i in others if i != iu][0]
    su = 1 if c['R'][:, iu] @ ua > 0 else -1
    sv = 1 if c['R'][:, iv] @ va > 0 else -1
    return k, s, iu, su, iv, sv


def surf(c, direction, u, v):
    """world point + outward normal on the chunk's flat face nearest `direction`, (u, v) in -1..1"""
    k, s, iu, su, iv, sv = face_frame(c, direction)
    h = c['h']
    ch = min(c['ch'], 0.45 * min(h))
    tx, ty = c['taper']

    def local(uu, vv):
        q = np.zeros(3)
        q[k] = s * h[k]
        q[iu] = su * uu * (h[iu] - ch)
        q[iv] = sv * vv * (h[iv] - ch)
        f = (q[2] + h[2]) / (2 * h[2])
        q[0] *= 1 + (tx - 1) * f
        q[1] *= 1 + (ty - 1) * f
        return q

    q = local(u, v)
    e = 1e-3
    du = (local(u + e, v) - local(u - e, v))
    dv = (local(u, v + e) - local(u, v - e))
    n = np.cross(du, dv)
    n /= np.linalg.norm(n)
    wn = c['R'] @ n
    if wn @ (c['R'][:, k] * s) < 0:
        wn = -wn
    return c['c'] + c['R'] @ q, wn


# ------------------------------------------------------------------ simple boxes as faces (crack strips, studs)
def box_faces(centre, axes, half, part, bone, style, obj, skip_bottom=False, top_scale=1.0):
    """axes = (a, b, n) orthonormal; half = (ha, hb, hn); faces use the chunk_faces dict layout"""
    a, b, n = [np.array(x, float) for x in axes]
    ha, hb, hn = half
    out = []

    def P(sa, sb, sn):
        k = top_scale if sn > 0 else 1.0
        return centre + a * sa * ha * k + b * sb * hb * k + n * sn * hn

    quads = {
        'top': [P(-1, -1, 1), P(1, -1, 1), P(1, 1, 1), P(-1, 1, 1)],
        'bot': [P(-1, 1, -1), P(1, 1, -1), P(1, -1, -1), P(-1, -1, -1)],
        '+a': [P(1, -1, -1), P(1, 1, -1), P(1, 1, 1), P(1, -1, 1)],
        '-a': [P(-1, 1, -1), P(-1, -1, -1), P(-1, -1, 1), P(-1, 1, 1)],
        '+b': [P(1, 1, -1), P(-1, 1, -1), P(-1, 1, 1), P(1, 1, 1)],
        '-b': [P(-1, -1, -1), P(1, -1, -1), P(1, -1, 1), P(-1, -1, 1)],
    }
    for key, pts in quads.items():
        if skip_bottom and key == 'bot':
            continue
        Pm = np.array(pts)
        nn = np.cross(Pm[2] - Pm[0], Pm[3] - Pm[1])
        nn /= np.linalg.norm(nn)
        cen = Pm.mean(0)
        up = np.array((0, 0, 1.0)) if abs(nn[2]) < 0.9 else np.array((0, 1.0, 0))
        bb = up - (up @ nn) * nn
        bb /= np.linalg.norm(bb)
        aa = np.cross(bb, nn)
        la, lb = (Pm - cen) @ aa, (Pm - cen) @ bb
        out.append(dict(pts=[p for p in Pm], n=nn, a=aa, b=bb, c=cen, ha=max(1e-3, (la.max() - la.min()) / 2),
                        hb=max(1e-3, (lb.max() - lb.min()) / 2), part=part, bone=bone, style=style, obj=obj,
                        kind='stud_' + ('top' if key == 'top' else 'side') if style != 'crack' else 'crack',
                        bc=centre, bax=a, bh=ha))
    return out


def crack_segments(chunks, paths=None):
    byname = {c['name']: c for c in chunks}
    segs = []
    for name, direction, pts in (paths if paths is not None else D.crack_paths()):
        c = byname[name]
        P = [surf(c, direction, u, v) for (u, v) in pts]
        for (p0, n0), (p1, n1) in zip(P, P[1:]):
            segs.append((p0, p1, (n0 + n1) / 2, c['bone']))
    return segs


def crack_faces(segs):
    F = []
    for i, (p0, p1, n, bone) in enumerate(segs):
        n = n / np.linalg.norm(n)
        t = p1 - p0
        L = np.linalg.norm(t)
        t /= L
        w = np.cross(n, t)
        w /= np.linalg.norm(w)
        t = np.cross(w, n)
        c = (p0 + p1) / 2 + n * 0.35
        hl, hw = L / 2 + 1.6, 1.9
        pts = [c - t * hl - w * hw, c + t * hl - w * hw, c + t * hl + w * hw, c - t * hl + w * hw]
        Pm = np.array(pts)
        if np.cross(Pm[2] - Pm[0], Pm[3] - Pm[1]) @ n < 0:
            pts = pts[::-1]
        F.append(dict(pts=pts, n=n, a=t, b=w, c=c, ha=hl, hb=hw, part=f'crack{i}', bone=bone, style='crack',
                      obj=D.CRACKS, kind='crack', bc=c, bax=t, bh=hl))
    return F


def seg_dist(P, segs):
    d = np.full(P.shape[:-1], 1e9, np.float32)
    for (p0, p1, n, b) in segs:
        v = p1 - p0
        t = np.clip(((P - p0) @ v) / (v @ v), 0, 1)
        q = p0 + t[..., None] * v
        d = np.minimum(d, np.linalg.norm(P - q, axis=-1))
    return d


def point_in_face(p, f):
    Pm = np.array(f['pts'])
    a, b = f['a'], f['b']
    pts = [((q - f['c']) @ a, (q - f['c']) @ b) for q in Pm]
    x, y = (p - f['c']) @ a, (p - f['c']) @ b
    sgn = None
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        cr = (x1 - x0) * (y - y0) - (y1 - y0) * (x - x0)
        if abs(cr) < 1e-9:
            continue
        if sgn is None:
            sgn = cr > 0
        elif (cr > 0) != sgn:
            return False
    return True


def occluders(chunks):
    return [c for c in chunks if c['obj'] != D.CRACKS]


def buried(f, solid):
    """face lies entirely inside another chunk (e.g. leg top cap inside the body): never visible"""
    probes = [f['c']] + [np.asarray(p) * 0.8 + f['c'] * 0.2 for p in f['pts']]
    for q in probes:
        q = q + f['n'] * 0.8
        if not any(c['name'] != f['part'] and _inside(c, q) for c in solid):
            return False
    return True


def layout_studs(faces, chunks, segs):
    """fixed-pitch grid centred on each flat face; a stud is dropped only where something covers it
    (another chunk, the eye) or where a lava crack runs through it"""
    solid = occluders(chunks)
    count = 0
    for f in faces:
        f['studs'] = []
        if f['kind'] != 'main' or f['style'] not in STUD or f['n'][2] < -0.6:
            continue
        pitch, s, h = STUD[f['style']]
        na = int((2 * f['ha'] - 2 * s - 6) // pitch) + 1
        nb = int((2 * f['hb'] - 2 * s - 6) // pitch) + 1
        if na < 1 or nb < 1:
            continue
        for i in range(na):
            for j in range(nb):
                ua = (i - (na - 1) / 2) * pitch
                vb = (j - (nb - 1) / 2) * pitch
                p = f['c'] + f['a'] * ua + f['b'] * vb
                m = s + 2.0
                if not all(point_in_face(p + f['a'] * da * m + f['b'] * db * m, f) for da in (-1, 1) for db in (-1, 1)):
                    continue
                probes = [p + f['n'] * 1.0, p + f['n'] * (h + 1.0)] + \
                         [p + f['n'] * 1.0 + (f['a'] * da + f['b'] * db) * s for da in (-1, 1) for db in (-1, 1)]
                if any(c['name'] != f['part'] and _inside(c, q) for q in probes for c in solid):
                    continue
                if segs and min(seg_dist(p[None], segs)[0], seg_dist(p[None], VEINS)[0] if VEINS else 1e9) < s * 1.42 + 3.5:
                    continue
                f['studs'].append((ua, vb))
                count += 1
    return count


# ------------------------------------------------------------------ atlas layout + painting (per object)
def tile_size(f, pxr):
    if f['kind'] in SHARED:
        return 4, 4
    return max(2, int(np.ceil(2 * f['ha'] * pxr))), max(2, int(np.ceil(2 * f['hb'] * pxr)))


def pack(faces, size, pxr):
    """shelf packing; studs / crack strips share one tiny tile per (style, kind)"""
    shared = {}
    order = sorted(range(len(faces)), key=lambda i: -tile_size(faces[i], pxr)[1])
    pos = [None] * len(faces)
    x = y = rowh = 0
    for i in order:
        f = faces[i]
        key = (f['style'], f['kind']) if f['kind'] in SHARED else None
        if key and key in shared:
            pos[i] = shared[key]
            continue
        w, h = tile_size(f, pxr)
        if x + w + 2 * PAD > size:
            x, y, rowh = 0, y + rowh, 0
        if y + h + 2 * PAD > size:
            return None
        pos[i] = (x + PAD, y + PAD)
        if key:
            shared[key] = pos[i]
        x += w + 2 * PAD
        rowh = max(rowh, h + 2 * PAD)
    return pos


def fire(t):
    t = np.clip(t, 0, 1)
    out = np.zeros(t.shape + (3,), np.float32)
    for (t0, c0), (t1, c1) in zip(FIRE, FIRE[1:]):
        m = (t >= t0) & (t <= t1)
        k = ((t - t0) / (t1 - t0))[m][:, None]
        out[m] = srgb(c0) * (1 - k) + srgb(c1) * k
    return out


def stud_masks(f, qa, qb):
    """per-texel stud shading factors + tangent-space normal for the painted studs of face f"""
    shp = qa.shape
    light = np.ones(shp, np.float32)
    nrm = np.zeros(shp + (3,), np.float32)
    nrm[..., 2] = 1.0
    if not f.get('studs'):
        return light, nrm
    pitch, s, h = STUD[f['style']]
    top = s * 0.7
    for ua, vb in f['studs']:
        dx, dy = qa - ua, qb - vb
        ax, ay = np.abs(dx), np.abs(dy)
        m = np.maximum(ax, ay)
        if not (m < s + 1.6).any():
            continue
        cap = m < top
        bev = (m >= top) & (m < s)
        rim = (m >= s) & (m < s + 1.6)
        light[cap] *= 1.07
        vert = ay >= ax
        up, down = bev & vert & (dy > 0), bev & vert & (dy <= 0)
        right, left = bev & ~vert & (dx > 0), bev & ~vert & (dx <= 0)
        light[up] *= 1.2
        light[down] *= 0.8
        light[left] *= 1.06
        light[right] *= 0.92
        k = 1.0 - (m[rim] - s) / 1.6
        light[rim] *= 1.0 - 0.16 * k                      # soft contact shadow around the stud
        tilt = 0.62
        for msk, v in ((up, (0, tilt, 1)), (down, (0, -tilt, 1)), (right, (tilt, 0, 1)), (left, (-tilt, 0, 1))):
            vv = np.array(v, np.float32)
            nrm[msk] = vv / np.linalg.norm(vv)
    return light, nrm


def plate_jitter(c):
    return 0.96 + 0.08 * math.modf(abs(math.sin(float(np.sum(c['c'] * (1.3, 2.1, 0.7))) * 3.1)) * 91.7)[0]


def shade(f, P, qa, qb, segs, chunk_by_name):
    st = f['style']
    shp = P.shape[:-1]
    col = np.zeros(shp + (3,), np.float32)
    chunk = chunk_by_name.get(f['part'])
    if st in ('body', 'snout', 'muzzle', 'ear'):
        base = srgb(PALETTE['ear_in'] if f['kind'] == 'ear_in' else PALETTE[st])
        col[:] = base * (plate_jitter(chunk) if chunk is not None else 1.0)
        if st == 'snout':                                  # snout darkens toward the nose like the reference
            t = np.clip((-P[..., 1] - 236.0) / 48.0, 0, 1)
            col = col * (1 - 0.35 * t[..., None]) + srgb(PALETTE['muzzle']) * (0.35 * t[..., None])
            if f['n'][1] < -0.7:
                col[:] = srgb(PALETTE['muzzle']) * 1.02
        if st in ('body', 'snout') and f['kind'] not in SHARED and segs:
            d = seg_dist(P, segs)
            hot = np.exp(-(d / 4.0) ** 2)
            halo = np.clip(np.exp(-d / 9.0) * 0.92 + np.exp(-(d / 30.0) ** 2) * 0.42, 0, 1)
            col = col * (1 - halo[..., None]) + srgb(PALETTE['glow']) * halo[..., None]
            col = col * (1 - hot[..., None]) + srgb(PALETTE['glow_hot']) * hot[..., None]
            if VEINS:
                vd = seg_dist(P, VEINS)
                vh = np.clip(np.exp(-vd / 5.0) * 0.7 + np.exp(-(vd / 16.0) ** 2) * 0.2, 0, 1)
                vc = np.exp(-(vd / 1.5) ** 2)
                col = col * (1 - vh[..., None]) + srgb(PALETTE['glow']) * vh[..., None]
                col = col * (1 - vc[..., None]) + srgb(PALETTE['crack']) * vc[..., None]
        if f['n'][2] < -0.6:
            col *= 0.8
    elif st in ('hoof', 'armour'):
        col[:] = srgb(PALETTE[st]) * (plate_jitter(chunk) * 1.1 - 0.1 if chunk is not None else 1.0)
        if f['kind'] == 'edge' or f['kind'] == 'corner':
            col *= 1.08 if st == 'armour' else 1.12     # worn, lighter bevels on rock and hoof
        if st == 'hoof' and f['n'][2] < -0.6:
            col *= 0.7
    elif st in ('mane', 'tail'):
        c = chunk
        ax = c['R'][:, 2]
        base = c['c'] - ax * c['h'][2]
        t = ((P - base) @ ax) / (2 * c['h'][2])
        if 'core' in f['part']:
            t = 0.2 + 0.25 * t
        col = fire(t)
        blk = np.floor(P / 14.0)
        hsh = np.mod(np.sin(blk[..., 0] * 12.99 + blk[..., 1] * 78.23 + blk[..., 2] * 37.72) * 43758.5, 1.0)
        col *= (0.95 + 0.07 * hsh)[..., None]
    elif st == 'crack':
        col[:] = srgb(PALETTE['crack'])
    elif st in ('eye', 'pupil'):
        col[:] = srgb(PALETTE[st])
    light, nrm = stud_masks(f, qa, qb)
    col = col * light[..., None]
    return np.clip(col, 0, 1), nrm


def paint(obj, faces, pos, size, pxr, segs, chunk_by_name):
    img = np.zeros((size, size, 3), np.float32)
    nimg = np.zeros((size, size, 3), np.float32)
    nimg[..., 2] = 1.0
    done = set()
    for f, (tx, ty) in zip(faces, pos):
        if (tx, ty) in done:
            continue
        done.add((tx, ty))
        wa, hb = tile_size(f, pxr)
        na, nb = (wa + 2 * PAD) * SS, (hb + 2 * PAD) * SS
        if f['kind'] in SHARED:
            qa1 = np.zeros(na); qb1 = np.zeros(nb)
        else:
            qa1 = ((np.arange(na) + 0.5) / SS - PAD) / wa * (2 * f['ha']) - f['ha']
            qb1 = ((np.arange(nb) + 0.5) / SS - PAD) / hb * (2 * f['hb']) - f['hb']
        qa, qb = np.meshgrid(qa1, qb1, indexing='xy')
        P = f['c'] + f['a'] * qa[..., None] + f['b'] * qb[..., None]
        col, nrm = shade(f, P, qa, qb, segs, chunk_by_name)
        col = col.reshape(nb // SS, SS, na // SS, SS, 3).mean((1, 3))
        nrm = nrm.reshape(nb // SS, SS, na // SS, SS, 3).mean((1, 3))
        nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
        rows = size - 1 - (ty - PAD + np.arange(col.shape[0]))
        cols = (tx - PAD + np.arange(col.shape[1]))[None, :]
        img[rows[:, None], cols] = col
        nimg[rows[:, None], cols] = nrm
    Image.fromarray((img * 255 + 0.5).astype(np.uint8)).save(TEX + f'LavaHorse_{obj}_Color.png')
    if obj not in (D.CRACKS, D.EYES):
        Image.fromarray(((nimg * 0.5 + 0.5) * 255 + 0.5).astype(np.uint8)).save(TEX + f'LavaHorse_{obj}_Normal.png')


# ------------------------------------------------------------------ Blender objects
def make_material(obj):
    m = bpy.data.materials.new(obj)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    t = nt.nodes.new('ShaderNodeTexImage')
    t.image = bpy.data.images.load(TEX + f'LavaHorse_{obj}_Color.png', check_existing=True)
    t.interpolation = 'Linear'
    nt.links.new(t.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.55
    if obj not in (D.CRACKS, D.EYES):
        nm = nt.nodes.new('ShaderNodeTexImage')
        nm.image = bpy.data.images.load(TEX + f'LavaHorse_{obj}_Normal.png', check_existing=True)
        nm.image.colorspace_settings.name = 'Non-Color'
        nmap = nt.nodes.new('ShaderNodeNormalMap')
        nmap.inputs['Strength'].default_value = 1.4
        nt.links.new(nm.outputs['Color'], nmap.inputs['Color'])
        nt.links.new(nmap.outputs['Normal'], b.inputs['Normal'])
    if obj in (D.CRACKS, D.MANE, D.TAIL):
        nt.links.new(t.outputs['Color'], b.inputs['Emission Color'])
        b.inputs['Emission Strength'].default_value = 3.0 if obj == D.CRACKS else 1.6
    return m


def build_object(obj, faces, pos, size, pxr):
    bm = bmesh.new()
    vmap = {}
    uvl = bm.loops.layers.uv.new('UVMap')
    bone_of = []
    for f, (tx, ty) in zip(faces, pos):
        vs = []
        for p in f['pts']:
            key = (f['part'],) + tuple(np.round(np.asarray(p) * 8).astype(int))
            v = vmap.get(key)
            if v is None:
                v = bm.verts.new(tuple(np.asarray(p) * D.S))
                vmap[key] = v
            vs.append(v)
        P = np.array(f['pts'], float)
        groups = [list(range(len(vs)))]
        if len(vs) == 4:
            nn = np.cross(P[2] - P[0], P[3] - P[1])
            nn /= np.linalg.norm(nn)
            if np.abs((P - P.mean(0)) @ nn).max() > 0.05:      # twisted quad (tapered chamfer) -> 2 planar tris
                d02, d13 = np.linalg.norm(P[2] - P[0]), np.linalg.norm(P[3] - P[1])
                groups = [[0, 1, 2], [0, 2, 3]] if d02 <= d13 else [[0, 1, 3], [1, 2, 3]]
        wa, hb = tile_size(f, pxr)
        for g in groups:
            try:
                bf = bm.faces.new([vs[i] for i in g])
            except ValueError:
                continue
            for loop, i in zip(bf.loops, g):
                p = f['pts'][i]
                if f['kind'] in SHARED:
                    u, v = wa / 2, hb / 2
                else:
                    u = ((p - f['c']) @ f['a'] + f['ha']) / (2 * f['ha']) * wa
                    v = ((p - f['c']) @ f['b'] + f['hb']) / (2 * f['hb']) * hb
                loop[uvl].uv = ((tx + u) / size, (ty + v) / size)
            bone_of.append(f['bone'])
    me = bpy.data.meshes.new(obj)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(obj, me)
    bpy.context.scene.collection.objects.link(o)
    o.data.materials.append(make_material(obj))
    return o, bone_of


def main():
    os.makedirs(TEX, exist_ok=True)
    chunks = D.all_chunks()
    chunk_by_name = {c['name']: c for c in chunks}
    faces = []
    for c in chunks:
        for f in chunk_faces(c):
            f['obj'] = c['obj']
            faces.append(f)
    segs = crack_segments(chunks)
    global VEINS
    VEINS = crack_segments(chunks, D.vein_paths())
    solid = occluders(chunks)
    nburied = 0
    for f in faces:
        if f['obj'] != D.EYES and buried(f, solid):
            f['kind'] = 'hidden'
            nburied += 1
    nstud = layout_studs(faces, chunks, segs)
    faces += crack_faces(segs)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    report = {}
    bones = {}
    for obj in D.OBJECTS:
        F = [f for f in faces if f['obj'] == obj]
        size = ATLAS[obj]
        pxr = 4.0
        pos = None
        while pos is None:
            pos = pack(F, size, pxr)
            if pos is None:
                pxr *= 0.93
        paint(obj, F, pos, size, pxr, segs, chunk_by_name)
        o, bone_of = build_object(obj, F, pos, size, pxr)
        bones[obj] = bone_of
        tris = sum(len(p.vertices) - 2 for p in o.data.polygons)
        report[obj] = dict(tris=tris, texels_per_px=round(pxr, 3), atlas=size)
    json.dump(bones, open(W + 'face_bones.json', 'w'))
    total = sum(r['tris'] for r in report.values())
    print(json.dumps(report), 'buried faces', nburied, 'painted studs', nstud, 'crack segments', len(segs), 'TOTAL tris', total)
    bpy.ops.wm.save_as_mainfile(filepath=OUT + 'LavaHorse_stage1.blend')


if __name__ == '__main__':
    main()
