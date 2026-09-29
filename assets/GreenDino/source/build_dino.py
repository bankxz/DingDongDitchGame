"""Green Dino builder: voxel-block crocodile-dinosaur, rigged + idle/walk, for Roblox.

Run:  python3 make_atlas.py && python3 build_dino.py
Output (one folder up): GreenDino.blend, GreenDino.fbx, GreenDino_Idle.fbx, GreenDino_Walk.fbx
Units: 1 voxel = U metres. Dino faces -Y (Blender front), Z up.
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
  """project a planar face into a random 4x4-block patch of its atlas category.
  fit=(tw,th): scale face to fill tw x th blocks (non-voxel parts)."""
  n = Vector(n).normalized()
  fwd = -n
  right = fwd.cross(Vector((0, 0, 1)))
  if right.length < 1e-4: right = Vector((1, 0, 0))
  right.normalize(); up = right.cross(fwd).normalized()
  st = [((p.dot(right)) / U, (p.dot(up)) / U) for p in pts]
  s0 = min(s for s, _ in st); t0 = min(t for _, t in st)
  st = [(s - s0, t - t0) for s, t in st]
  ws = max(s for s, _ in st) or 1; ht = max(t for _, t in st) or 1
  if fit:
    st = [(s / ws * fit[0], t / ht * fit[1]) for s, t in st]; ws, ht = fit
  ws, ht = min(ws, 4), min(ht, 4)
  st = [(min(s, 4), min(t, 4)) for s, t in st]
  p = rng.choice(LAYOUT[cat]); px, py = p % 8, p // 8
  ox = rng.uniform(0, 4 - ws) if not fit else rng.randint(0, int(4 - ws))
  oy = rng.uniform(0, 4 - ht) if not fit else rng.randint(0, int(4 - ht))
  if not fit: ox, oy = round(ox), round(oy)
  bx, by = px * 4 + ox, (7 - py) * 4 + oy
  return [((bx + s) / ATL, (by + t) / ATL) for s, t in st]

# ----------------------------------------------------------------------------- mesh accumulator
class MeshAcc:
  def __init__(self): self.v, self.f, self.uv, self.bone = [], [], [], []
  def quad(self, pts, cat, bone, fit=None, n=None):
    if n is None:
      n = (pts[1] - pts[0]).cross(pts[2] - pts[0])
      if len(pts) == 4: n = n + (pts[2] - pts[0]).cross(pts[3] - pts[0])
    uvs = face_uv(pts, n, cat, fit)
    base = len(self.v)
    self.v += pts; self.uv.append(uvs); self.bone.append(bone)
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
      n = (pts[1] - pts[0]).cross(pts[2] - pts[0])
      fc = sum(pts, Vector()) / len(pts)
      if n.dot(fc - c) < 0:
        self.f[fi] = self.f[fi][::-1]; self.uv[fi] = self.uv[fi][::-1]

ACC = MeshAcc()

# ----------------------------------------------------------------------------- face category rules
def face_cat(cls, d):
  """d = (axis, sign)"""
  if cls == 'roof':    return 'red' if d == (2, -1) else 'camo'
  if cls == 'floor':   return 'red' if d == (2, 1) else 'cream'
  if cls == 'nostril': return 'dark' if d == (2, 1) else 'camo'
  if cls == 'moss':    return 'camomoss'
  return cls

DIRS = [(0, 1), (0, -1), (1, 1), (1, -1), (2, 1), (2, -1)]

def greedy(vox, bonefn, maxr=4, infl=0.0):
  """emit exposed faces of a voxel dict {(i,j,k):cls} as greedy-merged quads"""
  for ax, sg in DIRS:
    a1, a2 = [a for a in (0, 1, 2) if a != ax]
    faces = {}
    for v, cls in vox.items():
      nb = list(v); nb[ax] += sg
      if tuple(nb) in vox: continue
      faces[(v[ax], v[a1], v[a2])] = face_cat(cls, (ax, sg))
    done = set()
    if infl:
      lo = [min(v[a] for v in vox) for a in range(3)]; hi = [max(v[a] for v in vox) + 1 for a in range(3)]
      ctr = [(lo[a] + hi[a]) / 2 for a in range(3)]
    for key in sorted(faces):
      if key in done: continue
      L, u, w = key; cat = faces[key]
      du = 1
      while du < maxr and (L, u + du, w) in faces and (L, u + du, w) not in done and faces[(L, u + du, w)] == cat: du += 1
      dw = 1
      while dw < maxr and all((L, u + x, w + dw) in faces and (L, u + x, w + dw) not in done
                              and faces[(L, u + x, w + dw)] == cat for x in range(du)): dw += 1
      for x in range(du):
        for y in range(dw): done.add((L, u + x, w + y))
      plane = L + (1 if sg > 0 else 0)
      corners = []
      for cu, cw in [(u, w), (u + du, w), (u + du, w + dw), (u, w + dw)]:
        c = [0, 0, 0]; c[ax] = plane; c[a1] = cu; c[a2] = cw
        if infl: c = [c[a] + infl * (1 if c[a] > ctr[a] else -1 if c[a] < ctr[a] else 0) for a in range(3)]
        corners.append(W(*c))
      nrm = Vector((0, 0, 0)); nrm[ax] = sg
      e = (corners[1] - corners[0]).cross(corners[2] - corners[0])
      if e.dot(nrm) < 0: corners.reverse()
      cen = sum(corners, Vector()) / 4
      ACC.quad(corners, cat, bonefn(cen), n=nrm)

# ----------------------------------------------------------------------------- body profile (from LEFT SIDE / TOP / BOTTOM crops)
L = 52
def prof(pts, j): xs, ys = zip(*pts); return float(np.interp(j, xs, ys))
HW = [(9, 4.6), (12, 5.8), (15, 6.9), (21, 6.9), (26, 6.1), (31, 5.7), (35, 5.0), (38, 4.0), (42, 3.0), (46, 2.1), (50, 1.3), (52, 0.8)]
ZB = [(9, 6.0), (12, 4.6), (15, 3.4), (28, 3.0), (35, 3.0), (40, 2.6), (46, 2.2), (52, 1.8)]
ZT = [(9, 13.6), (12, 13.0), (18, 12.8), (22, 12.2), (26, 11.4), (31, 10.2), (35, 9.0), (40, 7.2), (45, 5.6), (49, 4.6), (52, 3.6)]

body = {}
for j in range(9, L):
  hw, zb, zt = prof(HW, j + .5), prof(ZB, j + .5), prof(ZT, j + .5)
  zc, hh = (zb + zt) / 2, (zt - zb) / 2
  for i in range(-8, 8):
    for k in range(0, 18):
      u = abs(i + .5) / hw; v = (k + .5 - zc) / hh
      if abs(u) ** 2.6 + abs(v) ** 2.6 <= 1.0:
        rel = (k + .5 - zb) / (zt - zb)
        if rel < 0.22 and abs(i + .5) < hw * 0.75: cls = 'cream'
        elif rel < 0.44: cls = 'tan'
        else: cls = 'camo'
        body[(i, j, k)] = cls

# ---- head (upper skull + upper jaw), j 0..11; mouth open like the reference
def head_hw(j): return prof([(0, 2.8), (4, 3.3), (8, 4.3), (11, 4.8)], j + .5)
def upj_bot(j): return prof([(0, 10.8), (4, 10.3), (8, 9.6), (11, 9.0)], j + .5)
def upj_top(j): return prof([(0, 13.2), (3, 13.4), (5, 14.2), (7, 14.8), (10, 14.2), (12, 13.2)], j + .5)
for j in range(0, 12):
  hw = head_hw(j); zb = upj_bot(j); zt = upj_top(j)
  for i in range(-6, 6):
    if abs(i + .5) > hw: continue
    # round the top outer corners
    top = zt - (0.9 if abs(i + .5) > hw - 1 else 0)
    for k in range(int(round(zb)), int(round(top))):
      cls = 'camo'
      if k == int(round(zb)) and abs(i + .5) < hw - 1: cls = 'roof'
      body[(i, j, k)] = cls
# nostrils (dark holes on the snout top) + stone nose plate
for i in (-2, 1): body[(i, 0, int(round(upj_top(0))) - 1)] = 'nostril'
for i in (-1, 0):
  for j in (2, 3): body[(i, j, int(round(upj_top(j))) - 1)] = 'stone' if False else 'moss'
# brow ridges + glowing eyes (DETAIL (HEAD))
for s in (-1, 1):
  ei = 4 if s > 0 else -5
  ek = int(round(upj_top(5.5))) - 3
  for j in (5, 6):
    body[(ei, j, ek)] = 'camo'; body[(ei, j, ek + 1)] = 'camo'; body[(ei, j, ek + 2)] = 'camo'
  body[(ei + s, 5, ek)] = 'eye'          # eye block sticks out of the head side
  body[(ei + s, 5, ek + 1)] = 'camo'; body[(ei + s, 6, ek + 1)] = 'camo'; body[(ei + s, 4, ek + 1)] = 'camo'
# throat / back of mouth
for j in (8, 9, 10, 11):
  for i in range(-5, 5):
    for k in range(7, int(round(upj_bot(j)))):
      if abs(i + .5) > head_hw(j): continue
      inner = abs(i + .5) < head_hw(j) - 1
      body.setdefault((i, j, k), ('darkred' if j >= 10 else 'red') if inner else ('cream' if k < 8 else 'camo'))

# ---- surface lumps: extra blocks sticking out (the chunky voxel silhouette)
lumps = {}
for (i, j, k), cls in body.items():
  if cls != 'camo' or j < 12: continue
  for ax, sg in [(0, 1), (0, -1), (2, 1)]:
    nb = [i, j, k]; nb[ax] += sg
    if tuple(nb) in body: continue
    if rng.random() < 0.2:
      lumps[tuple(nb)] = 'moss' if rng.random() < 0.15 else 'camo'
body.update(lumps)

# ---- lower jaw: separate group (Jaw bone)
def lj_hw(j): return prof([(0, 2.7), (5, 3.3), (10, 4.3)], j + .5)
def lj_bot(j): return prof([(0, 2.4), (5, 3.4), (10, 5.2)], j + .5)
def lj_top(j): return prof([(0, 4.6), (5, 5.9), (10, 7.8)], j + .5)
jaw = {}
for j in range(0, 11):
  hw = lj_hw(j)
  for i in range(-5, 5):
    if abs(i + .5) > hw: continue
    zb, zt = int(round(lj_bot(j))), int(round(lj_top(j)))
    for k in range(zb, zt):
      jaw[(i, j, k)] = 'floor' if (k == zt - 1 and abs(i + .5) < hw - 1) else 'cream'
    # outer lip rim one block higher (jaw wall around the tongue)
    if abs(i + .5) > hw - 1: jaw[(i, j, zt)] = 'cream'
for j in range(2, 10):   # tongue
  for i in (-1, 0): jaw[(i, j, int(round(lj_top(j))))] = 'tongue'

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
  BONES['UpperArm_' + side] = ((s * 6.5, FRONT_J, 7), (s * 10.0, FRONT_J, 3.5), 'Chest')
  BONES['LowerArm_' + side] = ((s * 10.0, FRONT_J, 3.5), (s * 10.0, FRONT_J, 1.5), 'UpperArm_' + side)
  BONES['Hand_' + side] = ((s * 10.0, FRONT_J, 1.2), (s * 10.0, FRONT_J - 4, 0.8), 'LowerArm_' + side)
  BONES['Thigh_' + side] = ((s * 6.0, REAR_J, 6.5), (s * 9.0, REAR_J, 3.5), 'Hips')
  BONES['Shin_' + side] = ((s * 9.0, REAR_J, 3.5), (s * 9.0, REAR_J, 1.5), 'Thigh_' + side)
  BONES['Foot_' + side] = ((s * 9.0, REAR_J, 1.2), (s * 9.0, REAR_J - 4, 0.8), 'Shin_' + side)

# spine weight curve: bone centres along y-grid -> smooth 2-bone blend
CHAIN = [('Head', 7.5), ('Neck', 12), ('Chest', 16.5), ('Spine', 23.5), ('Hips', 31), ('Tail1', 37), ('Tail2', 42.5), ('Tail3', 49)]
def spine_w(p):
  j = p.y / U + JOFF
  if j <= CHAIN[0][1]: return {CHAIN[0][0]: 1.0}
  for (a, ja), (b, jb) in zip(CHAIN, CHAIN[1:]):
    if j <= jb:
      t = (j - ja) / (jb - ja)   # linear: keeps greedy-quad T-junctions closed under skinning
      return {a: 1 - t, b: t}
  return {CHAIN[-1][0]: 1.0}


# ----------------------------------------------------------------------------- legs (rigid blocky segments, overlap at joints)
def box_vox(i0, i1, j0, j1, k0, k1, cls='legcamo', round_=False, skip=()):
  d = {}
  for i in range(i0, i1):
    for j in range(j0, j1):
      for k in range(k0, k1):
        corner = (i in (i0, i1 - 1)) + (j in (j0, j1 - 1)) + (k in (k0, k1 - 1))
        if round_ and corner >= 3: continue
        d[(i, j, k)] = cls
  return d

def mirror(d):  # +x voxel dict -> -x
  return {(-i - 1, j, k): c for (i, j, k), c in d.items()}

def camo_mix(d, p=0.35):
  return dict(d)   # colour variety lives in the atlas patches; mixed classes would break greedy merging

def claw(x0, x1, y_back, z0, length, height, bone):
  """pentagon-profile claw (DETAIL (FOOT)): flat back, rounded front, pointing -Y"""
  ACC.begin()
  prof2 = [(0, 0), (length, 0), (length, height * 0.45), (length * 0.55, height), (0, height)]
  A = [W(x0, y_back - py, z0 + pz) for py, pz in prof2]
  Bv = [W(x1, y_back - py, z0 + pz) for py, pz in prof2]
  ACC.quad(list(reversed(Bv)), 'claw', bone, fit=(1, 1))  # side caps
  ACC.quad(A, 'claw', bone, fit=(1, 1))
  for a in range(5):
    b = (a + 1) % 5
    if a == 4: continue  # back face buried in the foot
    ACC.quad([A[a], A[b], Bv[b], Bv[a]], 'claw', bone, fit=(1, 1))
  ACC.end()

fj, rj = int(FRONT_J), int(REAR_J)
# shoulder / hip masses (the big rounded limb bulges of the reference) live in the body grid
def mass(cx, cy, cz, rx, ry, rz):
  for i in range(int(cx - rx) - 1, int(cx + rx) + 2):
    for j in range(int(cy - ry) - 1, int(cy + ry) + 2):
      for k in range(max(0, int(cz - rz) - 1), int(cz + rz) + 2):
        d = ((i + .5 - cx) / rx) ** 2 + ((j + .5 - cy) / ry) ** 2 + ((k + .5 - cz) / rz) ** 2
        if d <= 1.0 and (i, j, k) not in body:
          body[(i, j, k)] = 'tan' if k < 4.5 else ('moss' if rng.random() < 0.08 else 'camo')
for s in (1, -1):
  mass(s * 6.8, fj - 0.3, 7.0, 3.9, 4.4, 3.6)
  mass(s * 6.0, rj, 6.4, 3.5, 4.6, 3.3)
print('T0', ACC.tris()); greedy(body, spine_w); print('T body', ACC.tris())
greedy(jaw, lambda p: {'Jaw': 1.0}); print('T jaw', ACC.tris())

for s, side in ((1, 'L'), (-1, 'R')):
  upper = box_vox(7, 13, fj - 2, fj + 3, 2, 7, round_=True)
  lower = box_vox(8, 12, fj - 1, fj + 2, 1, 4)
  hand = box_vox(7, 14, fj - 3, fj + 3, 0, 2)
  thigh = box_vox(6, 12, rj - 2, rj + 3, 2, 7, round_=True)
  shin = box_vox(7, 11, rj - 1, rj + 2, 1, 3)
  foot = box_vox(6, 13, rj - 3, rj + 3, 0, 2)
  for group, x0c, base_j, ang in (([(upper, 'UpperArm_', 0.08), (lower, 'LowerArm_', 0.0), (hand, 'Hand_', 0.16)], 7, fj - 3, FRONT_YAW),
                                   ([(thigh, 'Thigh_', 0.08), (shin, 'Shin_', 0.0), (foot, 'Foot_', 0.16)], 6, rj - 3, REAR_YAW)):
    mark = len(ACC.v)
    for d, b, inf in group:
      if s < 0: d = mirror(d)
      greedy(d, (lambda bn: (lambda p: {bn: 1.0}))(b + side), infl=inf)
    bone = group[-1][1] + side
    for c in range(3):   # claws: 3 per foot, cream, at the front of each foot
      xa = x0c + 0.4 + c * 2.0; xb = xa + 1.5
      if s < 0: xa, xb = -xb, -xa
      claw(xa, xb, base_j + 0.6, 0.0, 1.6, 1.9, {bone: 1.0})
    # splay the whole limb around its hip/shoulder (TOP / BOTTOM views: feet point diagonally out)
    piv = W(*BONES[group[0][1] + side][0]); R = Matrix.Rotation(-s * ang, 3, 'Z')
    for vi in range(mark, len(ACC.v)): ACC.v[vi] = piv + R @ (ACC.v[vi] - piv)
    for bn in (g[1] + side for g in group):
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
  return prof(ZT, j) if j >= 9 else upj_top(j)

CENTRAL = [(8.4, 1.8, 2.6), (11.8, 2.6, 3.0), (15.2, 3.4, 3.4), (18.8, 4.4, 3.8), (22.6, 4.7, 3.8), (26.4, 4.4, 3.6),
           (30.0, 3.9, 3.4), (33.5, 3.3, 3.0), (36.8, 2.8, 2.7), (39.9, 2.4, 2.4), (42.8, 2.1, 2.1), (45.5, 1.8, 1.8),
           (48.0, 1.5, 1.5), (50.3, 1.2, 1.2)]
for j, h, w in CENTRAL:
  z0 = top_z(j) - 1.0
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
    z0 = prof(ZT, j) - 1.2 - 0.9 * (xo / hw) ** 2 * 1.6
    slab(x, j, z0, 1.3, 1.7, h + 1.0, lean=(s * 0.4, 0.2), slope=0.35)
# head crest (FRONT view: central plate + two horns behind the eyes)
for s in (1, -1):
  slab(s * 2.4, 8.6, upj_top(8.6) - 0.6, 1.2, 1.5, 2.4, lean=(s * 0.3, 0.3), slope=0.4)

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
    x = s * (head_hw(j) - 0.55)
    ln = [1.9, 2.2, 1.6, 2.0, 1.5, 1.4, 1.1][n]
    tooth(x, j, upj_bot(j) + 0.2, ln, True, {'Head': 1.0}, 0.9)
  for n, j in enumerate([0.8, 2.1, 3.5, 4.9, 6.3, 7.7]):
    x = s * (lj_hw(j) - 0.55)
    ln = [1.6, 2.0, 1.5, 1.7, 1.3, 1.1][n]
    tooth(x, j, lj_top(j) + 1.0 - 0.1, ln, False, {'Jaw': 1.0}, 0.9)
  tooth(s * 1.0, 0.45, upj_bot(0) + 0.2, 1.6, True, {'Head': 1.0}, 0.8)
  tooth(s * 1.0, 0.45, lj_top(0) - 0.1, 1.5, False, {'Jaw': 1.0}, 0.8)

JAW_DROP = math.radians(14)
piv = W(*BONES['Jaw'][0]); Rj = Matrix.Rotation(JAW_DROP, 3, 'X')
for fi, bw in enumerate(ACC.bone):
  if bw == {'Jaw': 1.0}:
    for vi in ACC.f[fi]: ACC.v[vi] = piv + Rj @ (ACC.v[vi] - piv)
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

for p in me.polygons: p.use_smooth = False

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
for poly, bw in zip(me.polygons, ACC.bone):
  for vi in poly.vertices:
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
