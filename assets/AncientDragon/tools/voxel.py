"""Voxelize the lofted sculpt into reference-style stud cubes, then greedy-merge faces.

Each cube is VOX_CELL_U design units: one stud of the texture.  Cube colours come from the
sculpt's per-face swatch key, or for rune / wing faces from the painted sculpt atlas so glyphs
become individual glowing cubes.  Coplanar same-colour, same-skin faces are merged into
rectangles (<= 16 cells) and textured with whole stud cells, keeping the mesh under budget.
"""
import math, os, random
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from PIL import Image
from spec import *

HERE = os.path.dirname(os.path.abspath(__file__))
TILE_KEYS = {'charcoal', 'gold', 'cream', 'horn', 'glow', 'teal', 'dark', 'belly'}
_rng = random.Random(11)


def _quantize_table():
    keys = [k for k, *_ in VOX if k != 'slate']
    cols = np.array([dict((k, c) for k, c, *_ in VOX)[k] for k in keys], float)
    return keys, cols


def voxelize(co, faces, fkey, fpart, open_parts, weights, v=VOX_CELL_U, slate_ratio=0.0):
    flat = np.asarray(Image.open(os.path.join(HERE, '_cache', 'source_flat.png')).convert('RGB'), float)
    qkeys, qcols = _quantize_table()
    polys = [f[0] for f in faces]
    bvh = BVHTree.FromPolygons([tuple(c) for c in co], polys, all_triangles=False)

    used = sorted({q for f in polys for q in f})
    lo = Vector((min(co[q].x for q in used), min(co[q].y for q in used), 0.0))
    hi = Vector((max(co[q].x for q in used), max(co[q].y for q in used), max(co[q].z for q in used)))
    nx = int(math.ceil(max(abs(lo.x), abs(hi.x)) / v)) + 2
    ox = -nx * v; NX = 2 * nx                       # symmetric about x = 0
    oy = lo.y - 2 * v; NY = int(math.ceil((hi.y - oy) / v)) + 3
    oz = 0.0; NZ = int(math.ceil(hi.z / v)) + 3
    org = Vector((ox, oy, oz))

    def centre(i, j, k):
        return org + Vector(((i + 0.5) * v, (j + 0.5) * v, (k + 0.5) * v))

    # ---- solid interior: per-part ray parity along +Z for every column ----
    closed = [p not in open_parts for p in fpart]
    occ = np.zeros((NX, NY, NZ), bool)
    owner = np.full((NX, NY, NZ), -1, np.int32)
    # part size (bbox volume): the smallest containing part owns a cube (armour/horns/claws win)
    pv = {}
    for f, p in zip(polys, fpart):
        for q in f:
            c = co[q]
            lo_, hi_ = pv.get(p, (Vector(c), Vector(c)))
            pv[p] = (Vector((min(lo_.x, c.x), min(lo_.y, c.y), min(lo_.z, c.z))),
                     Vector((max(hi_.x, c.x), max(hi_.y, c.y), max(hi_.z, c.z))))
    pvol = {p: max(1e-6, (h - l).x * (h - l).y * (h - l).z + 1e-3) for p, (l, h) in pv.items()}
    up = Vector((0, 0, 1))
    for i in range(NX):
        for j in range(NY):
            o = centre(i, j, -2) + Vector((1.3e-4, 0.7e-4, 0))
            hits = {}
            while True:
                loc, nrm, idx, dist = bvh.ray_cast(o, up, 100.0)
                if loc is None:
                    break
                if closed[idx]:
                    hits.setdefault(fpart[idx], []).append(loc.z)
                o = loc + up * 1e-4
            if not hits:
                continue
            for k in range(NZ):
                z = oz + (k + 0.5) * v
                best = None
                for p, zs in hits.items():
                    if sum(1 for h in zs if h < z) % 2 == 1:
                        if best is None or pvol[p] < pvol[best]:
                            best = p
                if best is not None:
                    occ[i, j, k] = True
                    owner[i, j, k] = best
    # ---- thin parts (spikes, claws, teeth) that own too few interior cubes get a surface shell ----
    part_faces = {}
    for fi, p in enumerate(fpart):
        part_faces.setdefault(p, []).append(fi)
    counts = {}
    for p in owner[owner >= 0].ravel():
        counts[int(p)] = counts.get(int(p), 0) + 1
    rad = v * 0.5
    for p, fl in part_faces.items():
        if counts.get(p, 0) >= 3:
            continue
        tree = BVHTree.FromPolygons([tuple(c) for c in co], [polys[f] for f in fl], all_triangles=False)
        l, h = pv[p]
        i0_ = max(0, int((l.x - ox) / v) - 1); i1_ = min(NX, int((h.x - ox) / v) + 2)
        j0_ = max(0, int((l.y - oy) / v) - 1); j1_ = min(NY, int((h.y - oy) / v) + 2)
        k0_ = max(0, int((l.z - oz) / v) - 1); k1_ = min(NZ, int((h.z - oz) / v) + 2)
        for i in range(i0_, i1_):
            for j in range(j0_, j1_):
                for k in range(k0_, k1_):
                    if owner[i, j, k] >= 0 and pvol[int(owner[i, j, k])] <= pvol[p]:
                        continue
                    loc, nrm, idx, dist = tree.find_nearest(centre(i, j, k), rad)
                    if loc is not None:
                        occ[i, j, k] = True; owner[i, j, k] = p
    # ground: nothing below z = 0 (grid already starts at 0)

    part_bvh = {}

    def pbvh(p):
        if p not in part_bvh:
            fl = part_faces[p]
            part_bvh[p] = (BVHTree.FromPolygons([tuple(c) for c in co], [polys[f] for f in fl], all_triangles=False), fl)
        return part_bvh[p]

    def sample(p, own=-1):
        """colour key + bone weights of the sculpt surface nearest to p (restricted to the owning part)."""
        if own >= 0:
            tree, fl = pbvh(own)
            loc, nrm, li, dist = tree.find_nearest(p, 50.0)
            idx = fl[li] if loc is not None else None
        else:
            loc, nrm, idx, dist = bvh.find_nearest(p, 4 * v)
        if loc is None:
            return 'charcoal', {'Hips': 1.0}
        vids, uvs, _ = faces[idx]
        # nearest vertex weights
        vi = min(range(len(vids)), key=lambda q: (co[vids[q]] - loc).length)
        wt = weights[vids[vi]]
        key = fkey[idx]
        if key in TILE_KEYS:
            return key, wt
        # rune / wing: sample the painted sculpt atlas at the interpolated UV
        pts = [co[q] for q in vids]
        ws = [1.0 / max((pp - loc).length, 1e-4) ** 2 for pp in pts]
        tw = sum(ws)
        u = sum(uv[0] * w for uv, w in zip(uvs, ws)) / tw
        vv = sum(uv[1] * w for uv, w in zip(uvs, ws)) / tw
        px = min(ATLAS - 1, max(0, int(u * ATLAS))); py = min(ATLAS - 1, max(0, int((1 - vv) * ATLAS)))
        c = flat[py, px]
        q = int(np.argmin(((qcols - c) ** 2).sum(1)))
        return qkeys[q], wt

    def wkey(wt):
        return (max(wt, key=wt.get),)

    DIRS = [(0, 1), (0, -1), (1, 1), (1, -1), (2, 1), (2, -1)]
    AX = [Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))]
    # per-direction exposed-face labels
    labels = {}
    cellw = {}
    idx3 = np.argwhere(occ)
    for (i, j, k) in idx3:
        for a, s in DIRS:
            n = [i, j, k]; n[a] += s
            if 0 <= n[0] < NX and 0 <= n[1] < NY and 0 <= n[2] < NZ and occ[n[0], n[1], n[2]]:
                continue
            if a == 2 and s == -1 and k == 0:
                continue                                  # bottom faces on the ground are never seen
            fc = centre(i, j, k) + AX[a] * (s * 0.35 * v)
            key, wt = sample(fc, int(owner[i, j, k]))
            if key == 'charcoal':
                h = (i * 73856093 ^ j * 19349663 ^ k * 83492791) % 1000
                if h < slate_ratio * 1000:
                    key = 'slate'
            labels[(a, s, int(i), int(j), int(k))] = (key, key)
            cellw[(a, s, int(i), int(j), int(k))] = wt

    # ---- greedy merge per slice ----
    out_co, out_w, out_faces = [], [], []
    cellsw = {0: (1, 2), 1: (0, 2), 2: (0, 1)}        # in-plane axes (u, v) per normal axis
    buckets = {}
    wbuck = {}
    for key3, lab in labels.items():
        a_, s_ = key3[0], key3[1]
        ua_, va_ = cellsw[a_]
        buckets.setdefault((a_, s_, key3[2 + a_]), {})[(key3[2 + ua_], key3[2 + va_])] = lab
        wbuck.setdefault((a_, s_, key3[2 + a_]), {})[(key3[2 + ua_], key3[2 + va_])] = cellw[key3]
    # ---- de-speckle: 3x3 majority filter per surface slice (rune/glow colours are kept) ----
    KEEP = {'glow', 'glow_edge', 'teal_light', 'teal_mid', 'teal'}
    for bk, grid in buckets.items():
        for _ in range(2):
            new = {}
            for (cu, cv), (key, _k) in grid.items():
                if key in KEEP:
                    continue
                cnt = {}
                for du in (-1, 0, 1):
                    for dv in (-1, 0, 1):
                        nb = grid.get((cu + du, cv + dv))
                        if nb is not None and nb[0] not in KEEP:
                            cnt[nb[0]] = cnt.get(nb[0], 0) + (2 if du == dv == 0 else 1)
                best = max(cnt, key=cnt.get)
                if best != key and cnt[best] >= 4:
                    new[(cu, cv)] = (best, best)
            grid.update(new)
    for a, s in DIRS:
        ua, va = cellsw[a]
        dims = [NX, NY, NZ]
        for layer in range(dims[a]):
            grid = buckets.get((a, s, layer), {})
            wgrid = wbuck.get((a, s, layer), {})
            used = set()
            for c in sorted(grid, key=lambda t: (t[1], t[0])):
                if c in used:
                    continue
                lab = grid[c]
                w = 1
                while w < CELLS and (c[0] + w, c[1]) in grid and grid[(c[0] + w, c[1])] == lab and (c[0] + w, c[1]) not in used:
                    w += 1
                h = 1
                while h < CELLS and all((c[0] + d, c[1] + h) in grid and grid[(c[0] + d, c[1] + h)] == lab
                                        and (c[0] + d, c[1] + h) not in used for d in range(w)):
                    h += 1
                for d in range(w):
                    for e in range(h):
                        used.add((c[0] + d, c[1] + e))
                # quad corners in grid units
                plane = layer + (1 if s > 0 else 0)
                corners = []
                for du, dv in ((0, 0), (w, 0), (w, h), (0, h)):
                    g = [0, 0, 0]; g[a] = plane; g[ua] = c[0] + du; g[va] = c[1] + dv
                    corners.append(org + Vector((g[0] * v, g[1] * v, g[2] * v)))
                # UVs: whole stud cells inside the colour's swatch
                key, wk = lab
                sx, sy = VOX_SWATCH[key]
                offu = _rng.randint(0, CELLS - w); offv = _rng.randint(0, CELLS - h)
                uvs = []
                for du, dv in ((0, 0), (w, 0), (w, h), (0, h)):
                    px = sx * SW + MARGIN + (offu + du) * CELL_PX
                    py = sy * SW + MARGIN + (offv + h - dv) * CELL_PX
                    uvs.append((px / ATLAS, 1 - py / ATLAS))
                # winding: outward normal = s * axis a
                e1 = corners[1] - corners[0]; e2 = corners[3] - corners[0]
                ids = []
                ccell = [(c[0], c[1]), (c[0] + w - 1, c[1]), (c[0] + w - 1, c[1] + h - 1), (c[0], c[1] + h - 1)]
                for p, cc in zip(corners, ccell):
                    out_co.append(p); out_w.append(wgrid[cc]); ids.append(len(out_co) - 1)
                if e1.cross(e2).dot(AX[a] * s) < 0:
                    ids = ids[::-1]; uvs = uvs[::-1]
                out_faces.append((ids, uvs, False))
    return out_co, out_w, out_faces, (NX, NY, NZ, int(occ.sum()))
