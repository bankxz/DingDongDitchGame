"""Flag floating pieces: small islands (spikes, teeth, plates) whose vertices neither touch nor sit inside the rest of the mesh.
python3 check_attached.py model.blend"""
import bpy, bmesh, sys
from mathutils.bvhtree import BVHTree
bpy.ops.wm.open_mainfile(filepath=sys.argv[-1])
ob = bpy.data.objects['BoneDragon_Body']; bm = bmesh.new(); bm.from_mesh(ob.data); bm.faces.ensure_lookup_table()
seen, isl = set(), []
for f0 in bm.faces:
    if f0.index in seen: continue
    st, cur = [f0], []; seen.add(f0.index)
    while st:
        f = st.pop(); cur.append(f)
        for e in f.edges:
            for g in e.link_faces:
                if g.index not in seen: seen.add(g.index); st.append(g)
    isl.append(cur)
bad = 0
for cur in isl:
    if len(cur) > 14: continue
    ids = {f.index for f in cur}; others = [f for f in bm.faces if f.index not in ids]
    verts = sorted({v.index: v for f in others for v in f.verts}.values(), key=lambda v: v.index); vmap = {v.index: i for i, v in enumerate(verts)}
    tree = BVHTree.FromPolygons([v.co.copy() for v in verts], [tuple(vmap[v.index] for v in f.verts) for f in others])
    pts = list({v.index: v.co for f in cur for v in f.verts}.values())
    dmin = min((tree.find_nearest(p)[3] or 99) for p in pts)
    inside = any(sum(1 for d in ((1, 0, 0), (0, 1, 0), (0, 0, 1)) if len(_r := [tree.ray_cast(p, d)]) and _r[0][0] is not None) >= 2 for p in pts)
    if dmin > 0.03 and not inside:
        bad += 1; c = sum(pts, pts[0] * 0) / len(pts); print('  FLOATING piece near', tuple(round(x, 2) for x in c), 'faces', len(cur), 'gap', round(dmin, 3))
print('small islands checked:', sum(1 for c in isl if len(c) <= 14), '| floating:', bad, '->', 'FAIL' if bad else 'PASS')
