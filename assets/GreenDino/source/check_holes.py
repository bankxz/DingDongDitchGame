# every open (boundary) edge must be hidden inside another part, at rest and in animation poses
import bpy, bmesh, sys
from mathutils import Vector
from mathutils.bvhtree import BVHTree
bpy.ops.wm.open_mainfile(filepath='' + __import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)), '..', 'GreenDino.blend') + '')
o = bpy.data.objects['GreenDino']; rig = bpy.data.objects['GreenDinoRig']
def check(tag):
  dg = bpy.context.evaluated_depsgraph_get(); me = o.evaluated_get(dg).to_mesh()
  bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
  bm.faces.ensure_lookup_table(); bm.verts.ensure_lookup_table()
  isl_of = {}; islands = []
  for f in bm.faces:
    if f.index in isl_of: continue
    st = [f]; isl = []; isl_of[f.index] = len(islands)
    while st:
      g = st.pop(); isl.append(g.index)
      for e in g.edges:
        for h in e.link_faces:
          if h.index not in isl_of: isl_of[h.index] = len(islands); st.append(h)
    islands.append(isl)
  def tree(isl):
    vs = sorted({v.index for fi in isl for v in bm.faces[fi].verts}); m = {v: n for n, v in enumerate(vs)}
    return BVHTree.FromPolygons([bm.verts[v].co.copy() for v in vs], [[m[v.index] for v in bm.faces[fi].verts] for fi in isl])
  closed = [i for i, isl in enumerate(islands) if all(e.is_manifold for fi in isl for e in bm.faces[fi].edges)]
  trees = {i: tree(islands[i]) for i in closed}
  def inside(p, t):
    n = 0; q = p.copy(); d = Vector((0.0123, 0.0071, 1.0)).normalized()
    for _ in range(60):
      hit = t.ray_cast(q, d)
      if hit[0] is None: break
      n += 1; q = hit[0] + d * 1e-4
    return n % 2 == 1
  bad = {}
  for e in bm.edges:
    if e.is_boundary:
      isl = isl_of[e.link_faces[0].index]
      for p in (e.verts[0].co, e.verts[1].co, (e.verts[0].co + e.verts[1].co) / 2):
        if not any(inside(p, t) for i, t in trees.items() if i != isl):
          bad.setdefault(isl, []).append(tuple(round(c, 2) for c in p))
  nb = sum(1 for e in bm.edges if e.is_boundary)
  print('HOLES', tag, 'open edges', nb, 'exposed', sum(len(v) for v in bad.values()),
        {k: (len(islands[k]), v[:2]) for k, v in list(bad.items())[:6]})
  o.evaluated_get(dg).to_mesh_clear()
check('rest')
for act, frames in (('Walk', (0, 8, 15, 23)), ('Idle', (0, 45))):
  rig.animation_data.action = bpy.data.actions[act]
  for t in rig.animation_data.nla_tracks: t.mute = True
  for f in frames:
    bpy.context.scene.frame_set(f); check(f'{act}{f}')
