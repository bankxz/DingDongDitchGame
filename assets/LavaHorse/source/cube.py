"""Generic chamfered-chunk helpers (copied from the Lava Ape pipeline). Lava Ape: clean low-poly chamfered chunks (reference px; X right, Y back, Z up; faces -Y; +X = ape's left).

Every chunk is a chamfered, optionally tapered box (6 main quads + 12 chamfer quads + 8 corner tris
= 44 tris). All faces are planar, so UVs are exact planar projections at one texel density (studs
never stretch). Studs and lava cracks are texture only.
Measurements from the front / left reference panels: X = x_front - 226, Y = u_side - 280, Z = 442 - v.
"""
import math
import numpy as np

S = 2.2 / 410.0          # metres per reference px (ape ~2.2 m tall incl. crest)


def rot(tilt=0.0, yaw=0.0, roll=0.0):
    t, r = math.radians(tilt), math.radians(roll)
    rx = np.array([[1, 0, 0], [0, math.cos(t), -math.sin(t)], [0, math.sin(t), math.cos(t)]])
    ry = np.array([[math.cos(r), 0, math.sin(r)], [0, 1, 0], [-math.sin(r), 0, math.cos(r)]])
    a = -math.radians(yaw)
    rz = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
    return rz @ ry @ rx


def C(name, c, h, bone, style, tilt=0, yaw=0, roll=0, taper=(1.0, 1.0), ch=None, R=None, cax=None):
    """Chunk. taper = (x, y) scale of the +Z end relative to the -Z end. ch = chamfer (ref px)."""
    if R is None:
        R = rot(tilt, yaw, roll)
    if ch is None:
        ch = max(3.0, min(h) * 0.22)
    return dict(name=name, c=np.array(c, float), h=np.array(h, float), bone=bone, style=style,
                R=np.array(R, float), taper=taper, ch=ch, cax=cax)


def seg(name, p0, p1, hw, hd, bone, style, taper=(1.0, 1.0), ext=0.0, ch=None, up=(1, 0, 0), cax=None):
    """Chunk whose local Z runs from p0 to p1 (limb segments). local X stays close to `up`."""
    p0, p1 = np.array(p0, float), np.array(p1, float)
    z = p1 - p0
    L = np.linalg.norm(z)
    z /= L
    x = np.array(up, float)
    x = x - (x @ z) * z
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    R = np.stack([x, y, z], 1)
    return C(name, (p0 + p1) / 2, (hw, hd, L / 2 + ext), bone, style, taper=taper, ch=ch, R=R, cax=cax)


def _inside(ck, p):
    q = ck['R'].T @ (np.asarray(p, float) - ck['c'])
    hx, hy, hz = ck['h']
    if abs(q[2]) > hz:
        return False
    f = (q[2] + hz) / (2 * hz)
    tx, ty = ck['taper']
    return abs(q[0]) <= hx * (1 + (tx - 1) * f) and abs(q[1]) <= hy * (1 + (ty - 1) * f)


# ------------------------------------------------------------------ chamfered box -> planar faces
def _local_to_world(ck, p):
    hz = ck['h'][2]
    tx, ty = ck['taper']
    p = np.array(p, float)
    f = (p[2] + hz) / (2 * hz)                          # 0 at -Z end, 1 at +Z end
    p[0] *= 1 + (tx - 1) * f
    p[1] *= 1 + (ty - 1) * f
    return ck['c'] + ck['R'] @ p


def prism_faces(ck):
    """Octagonal prism: only the 4 edges parallel to local axis `cax` are chamfered (8 sides + two 3-quad caps
    = 28 tris). Used where the end caps are buried in a neighbouring chunk, so a full chamfer would be wasted."""
    h = ck['h']
    k = ck['cax']
    i, j = [a for a in range(3) if a != k]
    c = min(ck['ch'], 0.45 * min(h[i], h[j]))
    hi, hj = h[i], h[j]
    oct2 = [(hi - c, hj), (hi, hj - c), (hi, -hj + c), (hi - c, -hj), (-hi + c, -hj), (-hi, -hj + c), (-hi, hj - c),
            (-hi + c, hj)]
    ring = {}
    for s in (-1, 1):
        pts = []
        for a, b in oct2:
            p = np.zeros(3)
            p[k] = s * h[k]; p[i] = a; p[j] = b
            pts.append(_local_to_world(ck, p))
        ring[s] = pts
    faces = []
    for m in range(8):
        n = (m + 1) % 8
        faces.append(('main' if m % 2 else 'edge', [ring[-1][m], ring[-1][n], ring[1][n], ring[1][m]]))
    for s in (-1, 1):
        R = ring[s]
        for q in ((0, 1, 2, 3), (7, 0, 3, 4), (4, 5, 6, 7)):
            faces.append(('cap', [R[x] for x in q]))
    return faces


def box_faces_raw(ck):
    hx, hy, hz = ck['h']
    c = min(ck['ch'], 0.45 * min(ck['h']))
    verts = {}

    def V(sx, sy, sz, k):
        # k: which axis sits on the outer face (0=x,1=y,2=z); the other two are pulled in by c
        p = np.array([sx * (hx - (c if k != 0 else 0)), sy * (hy - (c if k != 1 else 0)), sz * (hz - (c if k != 2 else 0))])
        return _local_to_world(ck, p)

    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                for k in range(3):
                    verts[(sx, sy, sz, k)] = V(sx, sy, sz, k)
    faces = []
    # main faces
    for k in range(3):
        for s in (-1, 1):
            o = [i for i in range(3) if i != k]
            quad = []
            for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                key = [0, 0, 0]
                key[k] = s; key[o[0]] = a; key[o[1]] = b
                quad.append((*key, k))
            faces.append(('main', quad))
    # edge faces (between axis i face and axis j face along axis m)
    for i in range(3):
        for j in range(i + 1, 3):
            m = 3 - i - j
            for si in (-1, 1):
                for sj in (-1, 1):
                    q = []
                    for sm, kk in ((-1, i), (-1, j), (1, j), (1, i)):
                        key = [0, 0, 0]
                        key[i] = si; key[j] = sj; key[m] = sm
                        q.append((*key, kk))
                    faces.append(('edge', q))
    # corner triangles
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                faces.append(('corner', [(sx, sy, sz, 0), (sx, sy, sz, 1), (sx, sy, sz, 2)]))
    return [(kind, [verts[k] for k in keys]) for kind, keys in faces]


def chunk_faces(ck):
    if ck.get('custom') is not None:
        faces = ck['custom']
    elif ck.get('cax') is not None:
        faces = prism_faces(ck)
    else:
        faces = box_faces_raw(ck)
    out = []
    lax = ck['R'][:, int(np.argmax(ck['h']))]
    for kind, pts in faces:
        P = np.array(pts)
        n = np.cross(P[1] - P[0], P[2] - P[0])
        if len(P) == 4:
            n = np.cross(P[2] - P[0], P[3] - P[1])
        if np.linalg.norm(n) < 1e-9:
            continue
        n /= np.linalg.norm(n)
        cen = P.mean(0)
        if n @ (cen - ck['c']) < 0:                 # orient outward
            n = -n
            pts = pts[::-1]
            P = P[::-1]
        if kind in ('main', 'cap', 'ear_in'):
            up = np.array((0, 0, 1.0)) if abs(n[2]) < 0.9 else np.array((0, 1.0, 0))
            b = up - (up @ n) * n
            b /= np.linalg.norm(b)
            a = np.cross(b, n)
        else:                                       # chamfer strips: tight rect along the longest edge
            E = [P[(i + 1) % len(P)] - P[i] for i in range(len(P))]
            a = max(E, key=np.linalg.norm)
            a = a - (a @ n) * n
            a /= np.linalg.norm(a)
            b = np.cross(n, a)
        la, lb = (P - cen) @ a, (P - cen) @ b
        amin, amax, bmin, bmax = la.min(), la.max(), lb.min(), lb.max()
        rc = cen + a * (amin + amax) / 2 + b * (bmin + bmax) / 2
        out.append(dict(pts=[np.array(p) for p in pts], n=n, a=a, b=b, c=rc, ha=(amax - amin) / 2,
                        hb=(bmax - bmin) / 2, part=ck['name'], bone=ck['bone'], style=ck['style'],
                        kind=kind, bc=ck['c'], bax=lax, bh=float(max(ck['h']))))
    return out


