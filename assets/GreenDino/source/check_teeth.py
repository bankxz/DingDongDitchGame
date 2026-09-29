# every tooth: its 4 root corners must be inside the jaw loft (odd ray-crossing count) -> no visible gap
import bpy, bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
bpy.ops.wm.open_mainfile(filepath='' + __import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)), '..', 'GreenDino.blend') + '')
o = bpy.data.objects['GreenDino']; me = o.data
bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5); bm.faces.ensure_lookup_table(); bm.verts.ensure_lookup_table()
# islands
islands = []; seen = set()
for f in bm.faces:
  if f.index in seen: continue
  st = [f]; isl = []; seen.add(f.index)
  while st:
    g = st.pop(); isl.append(g.index)
    for e in g.edges:
      for h in e.link_faces:
        if h.index not in seen: seen.add(h.index); st.append(h)
  islands.append(isl)
big = [i for i in islands if len(i) > 60]   # body loft + jaw loft
def tree(isl):
  vs = sorted({v.index for fi in isl for v in bm.faces[fi].verts}); m = {v: n for n, v in enumerate(vs)}
  return BVHTree.FromPolygons([bm.verts[v].co.copy() for v in vs], [[m[v.index] for v in bm.faces[fi].verts] for fi in isl])
trees = [tree(i) for i in big]
def inside(p, t):
  n = 0; q = p.copy(); d = Vector((0.0123, 0.0071, 1.0)).normalized()
  for _ in range(50):
    hit = t.ray_cast(q, d)
    if hit[0] is None: break
    n += 1; q = hit[0] + d * 1e-4
  return n % 2 == 1
teeth = [i for i in islands if len(i) == 4 and all(len(bm.faces[fi].verts) == 3 for fi in i)]   # tooth = 4-sided pyramid
bad = 0
for isl in teeth:
  vs = {v for fi in isl for v in bm.faces[fi].verts}
  zs = sorted(vs, key=lambda v: v.co.z)
  cen = sum((v.co for v in vs), Vector()) / len(vs)
  # root = the 4 verts farthest from the tip (tip verts are tightly clustered)
  pts = sorted(vs, key=lambda v: -(v.co - cen).length)
  apex = max(vs, key=lambda v: sum(v in bm.faces[fi].verts for fi in isl))   # the vertex shared by all 4 faces
  root = [v for v in vs if v is not apex]
  ok = all(any(inside(v.co, t) for t in trees) for v in root)
  bad += not ok
  if not ok: print('BAD', [tuple(round(c,2) for c in v.co) for v in root][:2], [inside(v.co, t) for v in root for t in trees])
print('TEETH', len(teeth), 'roots_not_embedded', bad)
