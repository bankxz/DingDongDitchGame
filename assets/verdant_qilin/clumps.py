"""Foliage as grouped solid clumps: each is the reference silhouette (left view, tools/foliage_polys.py) extruded into a
domed, mirrored shell; the reference crop itself is projected on it (atlas slot 'ref'), so every leaf edge/colour is 1:1."""
import json, math, os, numpy as np, cv2
from mathutils import Vector as V, geometry
PXU = 24.2; REFS = 320 / 365.0
def to_y(px): return -9.7 + (px - 10) / PXU
def to_z(py): return (277 - py) / PXU

def build(g):
    K, ACC, interp_w, W, wpos = g['K'], g['BODY'], g['interp_w'], g['W'], g['wpos']
    here = os.path.dirname(os.path.abspath(__file__))
    polys = json.load(open(os.path.join(here, 'foliage_polys.json')))
    uv = lambda px, py: (0, 0)
    neck = lambda z: interp_w([(4.9, 'Chest'), (5.8, 'Neck1'), (6.6, 'Neck2'), (7.4, 'Head')], z)
    for P in polys:
        pts = np.array(P['pts'], np.float32); grp = P['group']
        n = len(pts)
        mask = np.zeros((290 * 4, 365 * 4), np.uint8); cv2.fillPoly(mask, [(pts * 4).astype(np.int32)], 255)
        dt = cv2.GaussianBlur(cv2.distanceTransform(mask, cv2.DIST_L2, 5), (0, 0), 6)
        gy, gx = np.gradient(dt)
        depth = 0.18 * 4 * (1 if grp != 'tail' else .8)
        inner = []
        for px, py in pts:
            ix, iy = int(min(max(px * 4, 0), 365 * 4 - 1)), int(min(max(py * 4, 0), 290 * 4 - 1))
            d = np.array([gx[iy, ix], gy[iy, ix]]); nn = np.linalg.norm(d)
            d = d / nn if nn > 1e-6 else d * 0
            inner.append((px + d[0] * 5.5, py + d[1] * 5.5))
        def xs(px, py, top):
            if grp == 'tail': return (0.25, 1.15)[top]
            if grp == 'leg': return (1.55, 2.5)[top]
            if py < 70 and px > 100: return (2.8, 3.2)[top]                    # antler-tip glow leaf
            if py >= 150: w = 2.9                                              # shoulder / chest foliage
            elif px > 110: w = 1.6                                             # spine row
            else: w = 2.3                                                      # mane
            return (w - 1.0, w - 0.15)[top]
        def wt(p, px, py):
            if grp == 'tail': return interp_w([(0.4, 'Tail1'), (1.0, 'Tail2'), (2.4, 'Tail3'), (3.4, 'Tail4')], p.y)
            if grp == 'leg': return W('FrontLower.L')
            if py < 150 and px < 150 and p.y < -6.0 and p.z > 4.9: return neck(p.z)
            return wpos(p)
        for sx in (1, -1):
            O = [V((sx * xs(px, py, 0), to_y(px), to_z(py))) for px, py in pts]
            I = [V((sx * xs(ix, iy, 1), to_y(ix), to_z(iy))) for ix, iy in inner]
            ow = [wt(o, px, py) for o, (px, py) in zip(O, pts)]
            ids_o = [ACC.add_v(o, w) for o, w in zip(O, ow)]
            ids_i = [ACC.add_v(i, w) for i, w in zip(I, ow)]
            def orient(idx, uvs):
                a, b, c = (ACC.v[j] for j in idx[:3]); nx = (b - a).cross(c - a).x * sx
                return (idx, uvs) if nx > 0 else (idx[::-1], uvs[::-1])
            for k in range(n):
                k2 = (k + 1) % n
                q = [ids_o[k], ids_o[k2], ids_i[k2], ids_i[k]]
                u = [uv(*pts[k]), uv(*pts[k2]), uv(*inner[k2]), uv(*inner[k])]
                i, uu = orient(q, u); ACC.face(i, 'mid', [K._uv_rect('mid', 6, 6)] * len(i))
            tris = geometry.tessellate_polygon([[V((I[k].y, I[k].z, 0)) for k in range(n)]])
            for a, b, c in tris:
                i, uu = orient([ids_i[a], ids_i[b], ids_i[c]], [uv(*inner[a]), uv(*inner[b]), uv(*inner[c])]); ACC.face(i, 'mid', [K._uv_rect('mid', 6, 6)] * len(i))


def pieces(g, min_area=float(os.environ.get('MINA', 30))):
    """Faceted leaf pieces (one per reference leaf region) laid edge-to-edge over each clump's dome."""
    K, ACC, interp_w, W, wpos = g['K'], g['BODY'], g['interp_w'], g['W'], g['wpos']
    here = os.path.dirname(os.path.abspath(__file__))
    P = [p for p in json.load(open(os.path.join(here, 'foliage_pieces.json'))) if p['area'] >= min_area]
    mask = cv2.imread(os.path.join(here, 'ref', 'foliage_mask.png'), 0); Kk = 3
    dt = cv2.distanceTransform((mask > 0).astype(np.uint8), cv2.DIST_L2, 5) / Kk          # px (1x) to the silhouette edge
    rnd = __import__('random').Random(5)
    neck = lambda z: interp_w([(4.9, 'Chest'), (5.8, 'Neck1'), (6.6, 'Neck2'), (7.4, 'Head')], z)
    def grp_of(px, py): return 'tail' if px > 228 else ('leg' if py > 200 else ('mane' if px < 150 and py < 150 else 'body'))
    def xr(px, py, top):                                     # same x rules as the shell
        gp = grp_of(px, py)
        if gp == 'tail': return (0.25, 1.15)[top]
        if gp == 'leg': return (1.55, 2.5)[top]
        if py < 70 and px > 100: return (2.8, 3.2)[top]
        w = 2.9 if py >= 150 else (1.6 if px > 110 else 2.3)
        return (w - 1.0, w - 0.15)[top]
    def surf(px, py):
        d = dt[min(max(int(py * Kk), 0), mask.shape[0] - 1), min(max(int(px * Kk), 0), mask.shape[1] - 1)]
        t = min(1.0, d / 5.5); return xr(px, py, 0) + (xr(px, py, 1) - xr(px, py, 0)) * t
    def wt(p, px, py):
        gp = grp_of(px, py)
        if gp == 'tail': return interp_w([(0.4, 'Tail1'), (1.0, 'Tail2'), (2.4, 'Tail3'), (3.4, 'Tail4')], p.y)
        if gp == 'leg': return W('FrontLower.L')
        if py < 150 and px < 150 and p.y < -6.0 and p.z > 4.9: return neck(p.z)
        return wpos(p)
    LS = lambda l: 'limeBright' if l > 170 else 'lime' if l > 125 else 'mid' if l > 90 else 'dark'
    for pc in P:
        pts = np.array(pc['pts'], np.float32); n = len(pts); slot = LS(pc['lum'])
        c = pts.mean(0)
        # local frame: major axis -> v (base at the end nearer the body anchor), minor -> u
        ev, evec = np.linalg.eigh(np.cov((pts - c).T)); a = evec[:, 1]; b = evec[:, 0]
        pa, pb = (pts - c) @ a, (pts - c) @ b; la, lb = max(pa.max() - pa.min(), 1e-3), max(pb.max() - pb.min(), 1e-3)
        suv = lambda p: K._uv_rect(slot, 6 + ((p - c) @ b - pb.min()) / lb * 244, 6 + (1 - ((p - c) @ a - pa.min()) / la) * 244)
        lift = 0.16 + 0.22 * min(1.0, pc['area'] / 400) + rnd.uniform(0, 0.12)
        ridge_x = surf(*c) + lift
        for sx in (1, -1):
            V3 = lambda px, py, dx: V((sx * (surf(px, py) + dx), to_y(px), to_z(py)))
            ring = []
            for p in pts:
                v = V3(p[0], p[1], 0.03); ring.append((v, wt(v, p[0], p[1])))
            cv = V((sx * ridge_x, to_y(c[0]), to_z(c[1]))); cw = wt(cv, c[0], c[1])
            ids = [ACC.add_v(v, w) for v, w in ring]; ci = ACC.add_v(cv, cw)
            for k in range(n):
                k2 = (k + 1) % n
                idx = [ids[k], ids[k2], ci]; A, B, C = (ACC.v[j] for j in idx)
                if (B - A).cross(C - A).x * sx < 0: idx = idx[::-1]
                uvs = {ids[k]: suv(pts[k]), ids[k2]: suv(pts[k2]), ci: suv(c)}
                ACC.face(idx, slot, [uvs[j] for j in idx])
