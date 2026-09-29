"""Green Dino builder: smooth low-poly crocodile-dinosaur with painted stud texture, rigged + idle/walk, for Roblox.

Run:  python3 make_atlas.py && python3 build_dino.py
Output (one folder up): GreenDino.blend, GreenDino.fbx, GreenDino_Idle.fbx, GreenDino_Walk.fbx
Units: 1 grid unit (= 1 stud block on the texture) = U metres. Dino faces -Y (Blender front), Z up.
"""
import json, math, os, random
import numpy as np
import bpy
from mathutils import Matrix, Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, '..'))
U = 0.25
JOFF = 24.0          # grid j of world y=0
ATL = 32.0           # blocks per atlas side
LAYOUT = json.load(open(os.path.join(HERE, 'atlas_regions.json')))
rng = random.Random(11)

def W(x, y, z):      # grid -> world
  return Vector((x * U, (y - JOFF) * U, z * U))


# ----------------------------------------------------------------------------- UV helper
def face_uv(pts, n, cat, fit=None):
  """map a face onto whole stud blocks inside a random 4x4-block patch of its atlas category.
  fit=(tw,th) forces the block count; fit='auto' rounds the face's own size to whole blocks."""
  n = Vector(n).normalized()
  fwd = -n
  right = fwd.cross(Vector((0, 0, 1)))
  if right.length < 1e-4: right = Vector((1, 0, 0))
  right.normalize(); up = right.cross(fwd).normalized()
  st = [((p.dot(right)) / U, (p.dot(up)) / U) for p in pts]
  s0 = min(s for s, _ in st); t0 = min(t for _, t in st)
  st = [(s - s0, t - t0) for s, t in st]
  ws = max(s for s, _ in st) or 1; ht = max(t for _, t in st) or 1
  if fit == 'auto':
    fit = (min(4, max(1, round(ws))), min(4, max(1, round(ht))))
  st = [(s / ws * fit[0], t / ht * fit[1]) for s, t in st]; ws, ht = fit
  p = rng.choice(LAYOUT[cat]); px, py = p % 8, p // 8
  ox = rng.randint(0, int(4 - ws)); oy = rng.randint(0, int(4 - ht))
  bx, by = px * 4 + ox, (7 - py) * 4 + oy
  return [((bx + s) / ATL, (by + t) / ATL) for s, t in st]

def newell(pts):
  n = Vector()
  for a, b in zip(pts, pts[1:] + pts[:1]):
    n += Vector(((a.y - b.y) * (a.z + b.z), (a.z - b.z) * (a.x + b.x), (a.x - b.x) * (a.y + b.y)))
  return n

# ----------------------------------------------------------------------------- mesh accumulator
class MeshAcc:
  def __init__(self): self.v, self.f, self.uv, self.bone, self.smooth, self.vw = [], [], [], [], [], {}
  def addv(self, p, w):
    self.v.append(p); self.vw[len(self.v) - 1] = w; return len(self.v) - 1
  def face(self, idx, cat, fit='auto', smooth=True, bone=None):
    pts = [self.v[i] for i in idx]
    if len(pts) == 4:
      # loft quad: lay whole stud blocks along the quad's own edges so rows follow the body (belly plates)
      w = min(4, max(1, round(((pts[1] - pts[0]).length + (pts[2] - pts[3]).length) / 2 / U)))
      h = min(4, max(1, round(((pts[3] - pts[0]).length + (pts[2] - pts[1]).length) / 2 / U)))
      p = rng.choice(LAYOUT[cat]); px, py = p % 8, p // 8
      bx, by = px * 4 + rng.randint(0, 4 - w), (7 - py) * 4 + rng.randint(0, 4 - h)
      uvs = [(bx, by), (bx + w, by), (bx + w, by + h), (bx, by + h)]
      self.uv.append([(x / ATL, y / ATL) for x, y in uvs])
    else:
      self.uv.append(face_uv(pts, newell(pts), cat, fit))
    self.f.append(list(idx))
    self.bone.append(bone); self.smooth.append(smooth)
  def quad(self, pts, cat, bone, fit=None, n=None):
    n = n if n is not None else newell(pts)
    base = len(self.v)
    self.v += pts; self.uv.append(face_uv(pts, n, cat, fit or 'auto')); self.bone.append(bone); self.smooth.append(False)
    self.f.append(list(range(base, base + len(pts))))
  def tris(self): return sum(len(f) - 2 for f in self.f)
  def begin(self): self._mark = len(self.f)
  def end(self):
    """make every face of the just-built convex part point away from its centroid"""
    fs = range(self._mark, len(self.f))
    idx = sorted({i for fi in fs for i in self.f[fi]})
    c = sum((self.v[i] for i in idx), Vector()) / len(idx)
    for fi in fs:
      pts = [self.v[i] for i in self.f[fi]]
      fc = sum(pts, Vector()) / len(pts)
      if newell(pts).dot(fc - c) < 0:
        self.f[fi] = self.f[fi][::-1]; self.uv[fi] = self.uv[fi][::-1]

ACC = MeshAcc()

# ----------------------------------------------------------------------------- lofting (smooth rounded forms)
def sexp(c, e): return math.copysign(abs(c) ** (2.0 / e), c)

def ring_pts(cx, cy, cz, rx, rz, n, e, axis_u=Vector((1, 0, 0)), axis_v=Vector((0, 0, 1)), jitter=None):
  """rounded (superellipse) ring in grid space; jitter(k) -> radial scale"""
  pts = []
  for k in range(n):
    th = 2 * math.pi * (k + 0.5) / n
    j = jitter(k) if jitter else 1.0
    pts.append(Vector((cx, cy, cz)) + axis_u * (rx * j * sexp(math.cos(th), e)) + axis_v * (rz * j * sexp(math.sin(th), e)))
  return pts

def loft(rings, cat_fn, wfn, cap0=True, cap1=True, fit='auto'):
  """rings: list of equal-length lists of grid points. cat_fn(r, k, centre_grid) -> atlas category"""
  idx = [[ACC.addv(W(*p), wfn(W(*p))) for p in ring] for ring in rings]
  n = len(rings[0])
  for r in range(len(rings) - 1):
    axis = (sum(rings[r], Vector()) + sum(rings[r + 1], Vector())) / (2 * n)
    for k in range(n):
      q = [idx[r][k], idx[r][(k + 1) % n], idx[r + 1][(k + 1) % n], idx[r + 1][k]]
      pts = [ACC.v[i] for i in q]
      cen = sum(pts, Vector()) / 4
      if newell(pts).dot(cen - W(*axis)) < 0: q = q[::-1]
      g = (rings[r][k] + rings[r][(k + 1) % n] + rings[r + 1][k] + rings[r + 1][(k + 1) % n]) / 4
      ACC.face(q, cat_fn(r, k, g), fit)
  for end, ring, ids, other in ((cap0, rings[0], idx[0], rings[1]), (cap1, rings[-1], idx[-1], rings[-2])):
    if not end: continue
    c = sum(ring, Vector()) / n
    out = (c - sum(other, Vector()) / n).normalized()
    ci = ACC.addv(W(*(c + out * 0.35)), wfn(W(*c)))
    g = c
    for k in range(n):
      t = [ids[k], ids[(k + 1) % n], ci]
      pts = [ACC.v[i] for i in t]
      if newell(pts).dot(out) < 0: t = t[::-1]
      ACC.face(t, cat_fn(-1, k, g), (1, 1))

def tube(path, sides, e, cat, bone, jit=0.0):
  """rigid limb segment: rounded rings along a path of ((x,y,z), rx, rz)"""
  d = (Vector(path[-1][0]) - Vector(path[0][0])).normalized()
  u = d.cross(Vector((0, 0, 1)))
  u = Vector((1, 0, 0)) if u.length < 1e-4 else u.normalized()
  v = u.cross(d).normalized()
  rings = [ring_pts(*c, rx, rz, sides, e, u, v, (lambda k: 1 + rng.uniform(-jit, jit)) if jit else None) for c, rx, rz in path]
  loft(rings, lambda r, k, g: cat, lambda p: {bone: 1.0})

# ----------------------------------------------------------------------------- body profile (from LEFT SIDE / TOP / BOTTOM crops)
L = 52
def prof(pts, j): xs, ys = zip(*pts); return float(np.interp(j, xs, ys))
HW = [(9, 4.6), (12, 5.8), (15, 6.9), (21, 6.9), (26, 6.1), (31, 5.7), (35, 5.0), (38, 4.0), (42, 3.0), (46, 2.1), (50, 1.3), (52, 0.8)]
ZB = [(9, 6.0), (12, 4.6), (15, 3.4), (28, 3.0), (35, 3.0), (40, 2.6), (46, 2.2), (52, 1.8)]
ZT = [(9, 13.6), (12, 13.0), (18, 12.8), (22, 12.2), (26, 11.4), (31, 10.2), (35, 9.0), (40, 7.2), (45, 5.6), (49, 4.6), (52, 3.6)]
def head_hw(j): return prof([(0, 2.8), (4, 3.3), (8, 4.3), (11, 4.8)], j + .5)
def upj_bot(j): return prof([(0, 10.8), (4, 10.3), (8, 9.6), (11, 9.0)], j + .5)
def upj_top(j): return prof([(0, 13.2), (3, 13.4), (5, 14.2), (7, 14.8), (10, 14.2), (12, 13.2)], j + .5)
def lj_hw(j): return prof([(0, 3.0), (5, 3.7), (10, 4.6)], j + .5)
def lj_bot(j): return prof([(0, 2.0), (5, 2.9), (10, 4.6)], j + .5)
def lj_top(j): return prof([(0, 4.6), (5, 5.9), (10, 7.8)], j + .5)
# ----------------------------------------------------------------------------- bones
BONES = {  # name: (head grid, tail grid, parent)
  'Root':      ((0, 30, 0),   (0, 26, 0),    None),
  'Hips':      ((0, 34, 7),   (0, 27, 7.5),  'Root'),
  'Spine':     ((0, 27, 7.5), (0, 20, 8),    'Hips'),
  'Chest':     ((0, 20, 8),   (0, 13, 9),    'Spine'),
  'Neck':      ((0, 13, 9),   (0, 10, 10),   'Chest'),
  'Head':      ((0, 10, 10),  (0, 1, 11.5),  'Neck'),
  'Jaw':       ((0, 10.5, 7.5), (0, 1, 4),   'Head'),
  'Tail1':     ((0, 34, 6.5), (0, 40, 5.5), 'Hips'),
  'Tail2':     ((0, 40, 5.5), (0, 45.5, 4.2), 'Tail1'),
  'Tail3':     ((0, 45.5, 4.2), (0, 52, 2.8), 'Tail2'),
}
FRONT_J, REAR_J = 16.5, 34.5
FRONT_YAW, REAR_YAW = math.radians(22), math.radians(-18)
for s, side in ((1, 'L'), (-1, 'R')):   # +X is the dino's LEFT (it faces -Y)
  BONES['UpperArm_' + side] = ((s * 6.0, FRONT_J, 8.0), (s * 10.2, FRONT_J, 4.6), 'Chest')
  BONES['LowerArm_' + side] = ((s * 10.2, FRONT_J, 4.6), (s * 10.3, FRONT_J, 1.6), 'UpperArm_' + side)
  BONES['Hand_' + side] = ((s * 10.3, FRONT_J, 1.2), (s * 10.3, FRONT_J - 4, 0.8), 'LowerArm_' + side)
  BONES['Thigh_' + side] = ((s * 5.6, REAR_J, 7.4), (s * 9.2, REAR_J, 4.4), 'Hips')
  BONES['Shin_' + side] = ((s * 9.2, REAR_J, 4.4), (s * 9.3, REAR_J, 1.6), 'Thigh_' + side)
  BONES['Foot_' + side] = ((s * 9.3, REAR_J, 1.2), (s * 9.3, REAR_J - 4, 0.8), 'Shin_' + side)

# spine weight curve: bone centres along y-grid -> smooth 2-bone blend
CHAIN = [('Head', 7.5), ('Neck', 12), ('Chest', 16.5), ('Spine', 23.5), ('Hips', 31), ('Tail1', 37), ('Tail2', 42.5), ('Tail3', 49)]
def spine_w(p):
  j = p.y / U + JOFF
  if j <= CHAIN[0][1]: return {CHAIN[0][0]: 1.0}
  for (a, ja), (b, jb) in zip(CHAIN, CHAIN[1:]):
    if j <= jb:
      t = (j - ja) / (jb - ja)   # linear blend along the spine
      return {a: 1 - t, b: t}
  return {CHAIN[-1][0]: 1.0}



# ----------------------------------------------------------------------------- body + head + tail: one smooth loft
fj, rj = FRONT_J, REAR_J
E_HEAD, E_BODY = 3.4, 2.5          # superellipse exponents: squarish croc head -> rounded body
def smooth01(t): t = min(1, max(0, t)); return t * t * (3 - 2 * t)
def ring_params(j):
  if j <= 9: hw, zb, zt, e = head_hw(j - .5), upj_bot(j - .5), upj_top(j - .5), E_HEAD
  elif j >= 12: hw, zb, zt, e = prof(HW, j), prof(ZB, j), prof(ZT, j), E_BODY
  else:
    t = smooth01((j - 9) / 3)
    a, b = ring_params(9), ring_params(12)
    hw, zb, zt, e = [a[i] * (1 - t) + b[i] * t for i in range(4)]
  hw = hw * (1.12 if j > 11 else 1.0) + 1.5 * math.exp(-((j - fj) / 3.2) ** 2) + 1.1 * math.exp(-((j - rj) / 3.4) ** 2)   # shoulder / hip bulges
  zt += 0.5 * math.exp(-((j - fj - 1) / 4.0) ** 2)
  return hw, zb, zt, e

def z_surf(j, x):
  hw, zb, zt, e = ring_params(j)
  u = min(0.999, abs(x) / hw)
  return (zb + zt) / 2 + (zt - zb) / 2 * (1 - u ** e) ** (1 / e)

NB = 18
JS = [0, 0.9, 2.0, 3.2, 4.4, 5.6, 6.8, 8.0, 9.2, 10.4, 11.6, 13.0] + [13.0 + 1.6 * i for i in range(1, 23)] + [49.5, 51.0, 52.0]
JS = sorted(set(round(j, 2) for j in JS if j <= L))
noise = {}
def jit_for(ri):
  def f(k):
    m = (NB // 2 - 1 - k) % NB            # mirror index across the centre plane -> symmetric lumps
    key = (ri, min(k, m))
    if key not in noise: noise[key] = 1 + rng.uniform(-0.05, 0.05) if 0 < ri < len(JS) - 2 else 1.0
    return noise[key]
  return f
rings = []
for ri, j in enumerate(JS):
  hw, zb, zt, e = ring_params(j)
  rings.append(ring_pts(0, j, (zb + zt) / 2, hw, (zt - zb) / 2, NB, e, jitter=jit_for(ri)))

def body_cat(r, k, g):
  j, x, z = g.y, g.x, g.z
  hw, zb, zt, e = ring_params(j)
  v = (z - zb) / max(0.1, zt - zb)
  if r == -1: return 'camo' if j < 26 else 'tan'           # caps: snout tip / tail tip
  if j < 9.0 and v < 0.25: return 'red'                        # roof of the open mouth
  if 9.0 <= j < 11.2 and v < 0.3 and abs(x) < hw * 0.6: return 'darkred'   # throat (inside the mouth only)
  if j < 1.9 and v > 0.75 and abs(x) < 1.8: return 'dark'      # nostrils
  if v < 0.2: return 'cream'
  if v < 0.42: return 'tan'
  return 'camomoss' if rng.random() < 0.07 else 'camo'
loft(rings, body_cat, spine_w)
print('T body', ACC.tris())

# ---- lower jaw (rigid, Jaw bone)
JJ = [0, 1.2, 2.4, 3.6, 4.8, 6.0, 7.2, 8.4, 9.6, 10.8]
jrings = [ring_pts(0, j, (lj_bot(j - .5) + lj_top(j - .5)) / 2, lj_hw(j - .5), (lj_top(j - .5) - lj_bot(j - .5)) / 2, 14, 3.2) for j in JJ]
def jaw_cat(r, k, g):
  j, x, z = g.y, g.x, g.z
  v = (z - lj_bot(j - .5)) / (lj_top(j - .5) - lj_bot(j - .5))
  if r >= 0 and v > 0.8 and abs(x) < lj_hw(j) * 0.7: return 'tongue' if abs(x) < 1.0 and j > 1.5 else 'red'
  return 'cream'
loft(jrings, jaw_cat, lambda p: {'Jaw': 1.0})
print('T jaw', ACC.tris())

# ---- glowing eyes under a brow block (DETAIL (HEAD))
def box(c, size, cat, bw):
  ACC.begin()
  cx, cy, cz = c; hx, hy, hz = [s / 2 for s in size]
  P = [W(cx + a * hx, cy + b * hy, cz + d * hz) for d in (-1, 1) for b in (-1, 1) for a in (-1, 1)]
  for q in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
    ACC.quad([P[i] for i in q], cat, bw, fit=(1, 1))
  ACC.end()
for s in (1, -1):
  ez = upj_top(5.0) - 2.0
  box((s * (head_hw(5.0) - 0.15), 5.4, ez), (1.0, 1.3, 1.2), 'eye', {'Head': 1.0})
  box((s * (head_hw(5.0) - 0.55), 5.4, ez + 1.25), (1.8, 2.6, 1.0), 'camo', {'Head': 1.0})

# ----------------------------------------------------------------------------- legs: rounded tapered limbs + big flat feet
def claw(x0, x1, y_back, z0, length, height, bone):
  """pentagon-profile claw (DETAIL (FOOT)): flat back, rounded front, pointing -Y"""
  ACC.begin()
  prof2 = [(0, 0), (length, 0), (length, height * 0.45), (length * 0.55, height), (0, height)]
  A = [W(x0, y_back - py, z0 + pz) for py, pz in prof2]
  Bv = [W(x1, y_back - py, z0 + pz) for py, pz in prof2]
  ACC.quad(list(reversed(Bv)), 'claw', bone, fit=(1, 1))
  ACC.quad(A, 'claw', bone, fit=(1, 1))
  for a in range(4):
    ACC.quad([A[a], A[a + 1], Bv[a + 1], Bv[a]], 'claw', bone, fit=(1, 1))
  ACC.end()

LEG = {
  'front': ([('UpperArm_', [((6.0, fj, 8.4), 3.8, 3.9), ((8.6, fj, 6.4), 3.6, 3.5), ((10.2, fj, 4.6), 3.0, 3.0)]),
             ('LowerArm_', [((10.2, fj, 5.4), 2.8, 2.9), ((10.3, fj, 2.0), 2.9, 3.0)]),
             ('Hand_', [((10.3, fj + 2.8, 1.2), 3.3, 1.25), ((10.3, fj, 1.5), 3.7, 1.5), ((10.3, fj - 3.0, 1.2), 3.5, 1.2)])],
            7.0, fj - 3.2, FRONT_YAW),
  'rear': ([('Thigh_', [((5.6, rj, 7.6), 3.8, 3.9), ((8.0, rj, 6.0), 3.5, 3.4), ((9.2, rj, 4.4), 2.9, 2.9)]),
            ('Shin_', [((9.2, rj, 5.0), 2.7, 2.7), ((9.3, rj, 2.0), 2.8, 2.8)]),
            ('Foot_', [((9.3, rj + 2.8, 1.2), 3.3, 1.25), ((9.3, rj, 1.5), 3.7, 1.5), ((9.3, rj - 3.0, 1.2), 3.5, 1.2)])],
           6.0, rj - 3.2, REAR_YAW),
}
for s, side in ((1, 'L'), (-1, 'R')):
  for key_, (segs, x0c, base_j, ang) in LEG.items():
    mark = len(ACC.v)
    for bn, path in segs:
      path = [((s * c[0], c[1], c[2]), rx, rz) for c, rx, rz in path]
      tube(path, 10, 2.6, 'legcamo', bn + side, jit=0.04)
    bone = segs[-1][0] + side
    for c in range(3):   # claws: 3 per foot, cream, at the front of each foot
      xa = x0c + 0.4 + c * 2.3; xb = xa + 1.8
      if s < 0: xa, xb = -xb, -xa
      claw(xa, xb, base_j + 0.8, 0.0, 1.9, 2.2, {bone: 1.0})
    # splay the whole limb around its hip/shoulder (TOP / BOTTOM views: feet point diagonally out)
    piv = W(*BONES[segs[0][0] + side][0]); R = Matrix.Rotation(-s * ang, 3, 'Z')
    for vi in range(mark, len(ACC.v)): ACC.v[vi] = piv + R @ (ACC.v[vi] - piv)
    for bn in (g[0] + side for g in segs):
      h, t, par = BONES[bn]
      rot = lambda q: tuple(((piv + R @ (W(*q) - piv)) - W(0, JOFF, 0)) / U + Vector((0, JOFF, 0)))
      BONES[bn] = (rot(h), rot(t), par)
print('T legs', ACC.tris())

# ----------------------------------------------------------------------------- spikes (mossy stone slabs along the spine + flanks)
def slab(cx, cy, z0, wx, wy, h, lean=(0, 0), taper=0.72, slope=0.35, bone=None):
  """tapered slab; top is slanted (front lower) like the jagged plates in the reference"""
  ACC.begin()
  hx, hy = wx / 2, wy / 2
  b = [W(cx - hx, cy - hy, z0), W(cx + hx, cy - hy, z0), W(cx + hx, cy + hy, z0), W(cx - hx, cy + hy, z0)]
  tx, ty = hx * taper, hy * taper
  lx, ly = lean
  hf, hb = h * (1 - slope), h           # front lower, back higher
  t = [W(cx - tx + lx, cy - ty + ly, z0 + hf), W(cx + tx + lx, cy - ty + ly, z0 + hf),
       W(cx + tx + lx, cy + ty + ly, z0 + hb), W(cx - tx + lx, cy + ty + ly, z0 + hb)]
  bw = bone or spine_w(W(cx, cy, z0))
  fitv = (min(4, max(1, round(max(wx, wy)))), 4)
  for a in range(4):
    c = (a + 1) % 4
    ACC.quad([b[a], b[c], t[c], t[a]], 'stone', bw, fit=fitv)
  ACC.quad(t, 'stone', bw, fit=(2, 2))
  ACC.end()

def top_z(j):
  return z_surf(j, 0)

CENTRAL = [(8.4, 1.8, 2.6), (11.8, 2.6, 3.0), (15.2, 3.4, 3.4), (18.8, 4.4, 3.8), (22.6, 4.7, 3.8), (26.4, 4.4, 3.6),
           (30.0, 3.9, 3.4), (33.5, 3.3, 3.0), (36.8, 2.8, 2.7), (39.9, 2.4, 2.4), (42.8, 2.1, 2.1), (45.5, 1.8, 1.8),
           (48.0, 1.5, 1.5), (50.3, 1.2, 1.2)]
for j, h, w in CENTRAL:
  z0 = top_z(j) - 0.9
  slab(0.0, j, z0, w * 0.95, w * 1.25, h * 1.2 + 1.0, lean=(0, 0.3), slope=0.3)
  if h > 2.2:  # jagged secondary shards next to the big plate (clusters in LEFT SIDE view)
    sx = rng.choice((-0.7, 0.7))
    slab(sx, j + 1.2, z0, w * 0.5, w * 0.6, h * 0.9 + 1.0, lean=(0, 0.25), slope=0.45)
    if h > 3.2: slab(-sx, j - 1.0, z0, w * 0.45, w * 0.5, h * 0.55 + 1.0, lean=(0, 0.1), slope=0.5)
SIDE = [(12.5, 1.4, 3.2), (16.0, 2.0, 4.8), (19.5, 2.4, 5.2), (23.0, 2.3, 5.0), (26.5, 2.1, 4.8), (30.0, 1.8, 4.4),
        (33.5, 1.5, 3.4), (37.0, 1.2, 2.8), (40.5, 1.0, 2.2), (44.0, 0.9, 1.6)]
for j, h, xo in SIDE:
  for s in (1, -1):
    x = s * xo
    hw = prof(HW, j)
    z0 = z_surf(j, xo) - 0.9
    slab(x, j, z0, 1.3, 1.7, h + 1.0, lean=(s * 0.4, 0.2), slope=0.35)
# head crest (FRONT view: central plate + two horns behind the eyes)
for s in (1, -1):
  slab(s * 2.4, 8.6, z_surf(8.6, 2.4) - 0.6, 1.2, 1.5, 2.4, lean=(s * 0.3, 0.3), slope=0.4)

print('T spikes', ACC.tris())
# ----------------------------------------------------------------------------- teeth
def tooth(x, y, zbase, length, down, bone, size=0.85):
  ACC.begin()
  hs = size / 2; tip = 0.12
  zt = zbase - length if down else zbase + length
  base = [W(x - hs, y - hs, zbase), W(x + hs, y - hs, zbase), W(x + hs, y + hs, zbase), W(x - hs, y + hs, zbase)]
  tp = [W(x - tip, y - tip, zt), W(x + tip, y - tip, zt), W(x + tip, y + tip, zt), W(x - tip, y + tip, zt)]
  for a in range(4):
    c = (a + 1) % 4
    q = [base[a], base[c], tp[c], tp[a]]
    if not down: q = q[::-1]
    ACC.quad(q, 'tooth', bone, fit=(1, 2))
  ACC.quad(tp if down else tp[::-1], 'tooth', bone, fit=(1, 1))
  ACC.end()

for s in (1, -1):
  for n, j in enumerate([0.6, 1.9, 3.2, 4.5, 5.8, 7.1, 8.4]):
    x = s * (head_hw(j) - 0.7)
    ln = [1.9, 2.2, 1.6, 2.0, 1.5, 1.4, 1.1][n]
    tooth(x, j, upj_bot(j) + 0.2, ln, True, {'Head': 1.0}, 0.9)
  for n, j in enumerate([0.8, 2.1, 3.5, 4.9, 6.3, 7.7]):
    x = s * (lj_hw(j) - 0.7)
    ln = [1.6, 2.0, 1.5, 1.7, 1.3, 1.1][n]
    tooth(x, j, lj_top(j) - 0.3, ln, False, {'Jaw': 1.0}, 0.9)
  tooth(s * 1.0, 0.45, upj_bot(0) + 0.2, 1.6, True, {'Head': 1.0}, 0.8)
  tooth(s * 1.0, 0.45, lj_top(0) - 0.1, 1.5, False, {'Jaw': 1.0}, 0.8)

JAW_DROP = math.radians(14)
piv = W(*BONES['Jaw'][0]); Rj = Matrix.Rotation(JAW_DROP, 3, 'X')
jaw_v = {vi for fi, bw in enumerate(ACC.bone) if bw == {'Jaw': 1.0} for vi in ACC.f[fi]}
jaw_v |= {vi for vi, w in ACC.vw.items() if w == {'Jaw': 1.0}}
for vi in jaw_v: ACC.v[vi] = piv + Rj @ (ACC.v[vi] - piv)
jt = piv + Rj @ (W(*BONES['Jaw'][1]) - piv)
BONES['Jaw'] = (BONES['Jaw'][0], tuple((jt - W(0, JOFF, 0)) / U + Vector((0, JOFF, 0))), 'Head')
print('TRIS', ACC.tris())

# ----------------------------------------------------------------------------- scene
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = 30

me = bpy.data.meshes.new('GreenDino')
me.from_pydata([tuple(v) for v in ACC.v], [], ACC.f)
uvl = me.uv_layers.new(name='UVMap')
li = 0
for poly, uvs in zip(me.polygons, ACC.uv):
  for k, loop in enumerate(poly.loop_indices): uvl.data[loop].uv = uvs[k]
me.validate(); me.update()
obj = bpy.data.objects.new('GreenDino', me)
sc.collection.objects.link(obj)

for p, sm in zip(me.polygons, ACC.smooth): p.use_smooth = sm

# material
mat = bpy.data.materials.new('GreenDino_Mat')
mat.use_nodes = True
nt = mat.node_tree; bsdf = nt.nodes['Principled BSDF']
tex = nt.nodes.new('ShaderNodeTexImage')
tex.image = bpy.data.images.load(os.path.join(OUT, 'GreenDino_Color.png'))
tex.interpolation = 'Closest'
nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
emi = nt.nodes.new('ShaderNodeTexImage')
emi.image = bpy.data.images.load(os.path.join(OUT, 'GreenDino_Emissive.png'))
emi.image.colorspace_settings.name = 'Non-Color'
nt.links.new(tex.outputs['Color'], bsdf.inputs['Emission Color'])
mathn = nt.nodes.new('ShaderNodeMath'); mathn.operation = 'MULTIPLY'; mathn.inputs[1].default_value = 6.0
nt.links.new(emi.outputs['Color'], mathn.inputs[0]); nt.links.new(mathn.outputs[0], bsdf.inputs['Emission Strength'])
bsdf.inputs['Roughness'].default_value = 0.75
obj.data.materials.append(mat)

# armature
arm = bpy.data.armatures.new('GreenDinoRig')
rig = bpy.data.objects.new('GreenDinoRig', arm)
sc.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode='EDIT')
for name, (h, t, par) in BONES.items():
  eb = arm.edit_bones.new(name)
  eb.head = W(*h); eb.tail = W(*t)
  eb.roll = 0
  if par: eb.parent = arm.edit_bones[par]; eb.use_connect = False
bpy.ops.object.mode_set(mode='OBJECT')

# weights (per-vertex, from each face's bone map; shared positions get identical weights)
for name in BONES: obj.vertex_groups.new(name=name)
VW = dict(ACC.vw)
for fv, bw in zip(ACC.f, ACC.bone):
  if bw:
    for vi in fv: VW[vi] = bw
for vi, bw in VW.items():
  for bn, w in bw.items():
    if w > 1e-3: obj.vertex_groups[bn].add([vi], w, 'REPLACE')
obj.parent = rig
mod = obj.modifiers.new('Armature', 'ARMATURE'); mod.object = rig

# ----------------------------------------------------------------------------- animation helpers
def world_rot_to_local(pb, axis, ang):
  """rotation about an armature-space axis -> pose-bone local quaternion (rest-frame)"""
  R = Quaternion(Vector(axis), ang).to_matrix().to_4x4()
  M = pb.bone.matrix_local.to_3x3().to_4x4()
  return (M.inverted() @ R @ M).to_quaternion()

CUR = [0]
def key(pb, _unused, rots, loc=None):
  frame = CUR[0]
  q = Quaternion()
  for axis, ang in rots: q = world_rot_to_local(pb, axis, ang) @ q
  pb.rotation_mode = 'QUATERNION'
  pb.rotation_quaternion = q
  pb.keyframe_insert('rotation_quaternion', frame=frame)
  if loc is not None:
    pb.location = pb.bone.matrix_local.to_3x3().inverted() @ Vector(loc)
    pb.keyframe_insert('location', frame=frame)

X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)
D = math.radians
PB = rig.pose.bones

def make_action(name, frames, fn):
  rig.animation_data_create()
  act = bpy.data.actions.new(name)
  act.use_fake_user = True
  rig.animation_data.action = act
  for f in range(0, frames + 1, 2):
    t = f / frames
    for pb in PB:
      pb.rotation_quaternion = Quaternion(); pb.location = (0, 0, 0)
    fn(t)
  for pb in PB: pb.rotation_quaternion = Quaternion(); pb.location = (0, 0, 0)
  act.frame_range = (0, frames)
  return act

TAU = 2 * math.pi
def idle(t):
  br = math.sin(TAU * t)                 # one slow breath per loop
  key(PB['Root'], 0, [], (0, 0, 0))
  key(PB['Hips'], 0, [(X, D(0.6) * br)])
  key(PB['Spine'], 0, [(X, D(-0.8) * br)])
  key(PB['Chest'], 0, [(X, D(-1.2) * br)])
  key(PB['Neck'], 0, [(X, D(-2.5) * br), (Z, D(4) * math.sin(TAU * t + 0.6))])
  key(PB['Head'], 0, [(X, D(-2.5) * br), (Z, D(5) * math.sin(TAU * t + 1.2))])
  key(PB['Jaw'], 0, [(X, D(4) * (0.5 + 0.5 * math.sin(TAU * t - 0.8)))])
  for n, b in enumerate(('Tail1', 'Tail2', 'Tail3')):
    key(PB[b], 0, [(Z, D(4 + 2 * n) * math.sin(TAU * t - 0.7 * (n + 1)))])
  for b in ('UpperArm_L', 'UpperArm_R', 'LowerArm_L', 'LowerArm_R', 'Hand_L', 'Hand_R',
            'Thigh_L', 'Thigh_R', 'Shin_L', 'Shin_R', 'Foot_L', 'Foot_R'):
    key(PB[b], 0, [])
  # counter the chest breath at the shoulders so the feet stay planted
  for s in 'LR':
    key(PB['UpperArm_' + s], 0, [(X, D(0.8 + 1.2) * br)])
    key(PB['Thigh_' + s], 0, [(X, D(-0.6) * br)])

def walk(t):
  ph = {'UpperArm_L': 0.0, 'Thigh_R': 0.0, 'UpperArm_R': 0.5, 'Thigh_L': 0.5}   # diagonal trot
  bob = math.cos(2 * TAU * t)
  key(PB['Root'], 0, [], (0, 0, 0.035 * bob))
  key(PB['Hips'], 0, [(Z, D(5) * math.sin(TAU * t)), (Y, D(2.5) * math.sin(TAU * t))])
  key(PB['Spine'], 0, [(Z, D(-3) * math.sin(TAU * t))])
  key(PB['Chest'], 0, [(Z, D(-4) * math.sin(TAU * t)), (Y, D(-2.5) * math.sin(TAU * t))])
  key(PB['Neck'], 0, [(Z, D(4) * math.sin(TAU * t - 0.4)), (X, D(1.5) * bob)])
  key(PB['Head'], 0, [(Z, D(3) * math.sin(TAU * t - 0.8)), (X, D(1.5) * bob)])
  key(PB['Jaw'], 0, [(X, D(3) * (0.5 + 0.5 * math.sin(TAU * 2 * t)))])
  for n, b in enumerate(('Tail1', 'Tail2', 'Tail3')):
    key(PB[b], 0, [(Z, D(7 + 3 * n) * math.sin(TAU * t - 0.9 * (n + 1)))])
  for up, lo, ft in (('UpperArm_L', 'LowerArm_L', 'Hand_L'), ('UpperArm_R', 'LowerArm_R', 'Hand_R'),
                     ('Thigh_L', 'Shin_L', 'Foot_L'), ('Thigh_R', 'Shin_R', 'Foot_R')):
    p = TAU * (t + ph[up])
    swing = D(20) * math.sin(p)                     # + = foot moves back (stance), - = forward
    lift = max(0.0, -math.cos(p))                   # raise the foot while it travels forward
    s = 1 if up.endswith('L') else -1
    key(PB[up], 0, [(X, swing), (Y, D(18) * lift * s)])
    key(PB[lo], 0, [(Y, D(-14) * lift * s), (X, D(-10) * lift)])
    key(PB[ft], 0, [(X, -swing * 0.9 + D(10) * lift), (Y, D(-4) * lift * s)])

def sampled(fn, frames):
  def run(t):
    CUR[0] = round(t * frames); fn(t)
  return run

ACT_IDLE = make_action('Idle', 90, sampled(idle, 90))     # 3 s loop
ACT_WALK = make_action('Walk', 30, sampled(walk, 30))     # 1 s loop (2 steps per foot pair)
for pb in PB: pb.rotation_quaternion = Quaternion(); pb.location = (0, 0, 0)

# NLA tracks so both actions export and are browsable
rig.animation_data.action = None
for act in (ACT_IDLE, ACT_WALK):
  tr = rig.animation_data.nla_tracks.new(); tr.name = act.name
  tr.strips.new(act.name, 0, act); tr.mute = True

sc.frame_start, sc.frame_end = 0, 90
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'GreenDino.blend'))
print('SAVED', 'tris=', sum(len(p.vertices) - 2 for p in me.polygons), 'verts=', len(me.vertices), 'bones=', len(BONES))
