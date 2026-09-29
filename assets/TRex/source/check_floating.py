"""Report mesh pieces that float instead of being embedded in the body.

python3 check_floating.py <TRex.blend> [min_depth_studs] [action frame]

Every loose piece of the TRex mesh must intersect another piece (overlapping
triangles) and be sunk into it: either some vertex sits at least `min_depth`
studs inside, or (for small parts like claws) at least a fifth of its vertices
are inside another piece. Merely touching counts as floating. Exits non-zero if
any piece fails.
"""
import sys

import bpy
import bmesh
from mathutils.bvhtree import BVHTree

STUD = 0.28
blend = sys.argv[1]
min_depth = float(sys.argv[2]) if len(sys.argv) > 2 else 0.15
bpy.ops.wm.open_mainfile(filepath=blend)
obj = bpy.data.objects['TRex']
rig = bpy.data.objects['TRexRig']
if len(sys.argv) > 4:                      # check a posed frame of an animation
    rig.animation_data.action = bpy.data.actions[sys.argv[3]]
    bpy.context.scene.frame_set(int(sys.argv[4]))
else:
    if rig.animation_data:
        rig.animation_data.action = None
    for pb in rig.pose.bones:
        pb.rotation_euler = (0, 0, 0)
        pb.location = (0, 0, 0)
    bpy.context.view_layer.update()

bm = bmesh.new()
bm.from_mesh(obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh())
bm.verts.ensure_lookup_table()
bm.faces.ensure_lookup_table()

# loose pieces
island = {}
n = 0
for v in bm.verts:
    if v.index in island:
        continue
    stack = [v]
    island[v.index] = n
    while stack:
        a = stack.pop()
        for e in a.link_edges:
            b = e.other_vert(a)
            if b.index not in island:
                island[b.index] = n
                stack.append(b)
    n += 1

pieces = []
for i in range(n):
    faces = [f for f in bm.faces if island[f.verts[0].index] == i]
    vids = sorted({v.index for f in faces for v in f.verts})
    remap = {vid: k for k, vid in enumerate(vids)}
    verts = [bm.verts[vid].co.copy() for vid in vids]
    polys = [[remap[v.index] for v in f.verts] for f in faces]
    pieces.append((verts, polys, BVHTree.FromPolygons(verts, polys)))

groups = {g.index: g.name for g in obj.vertex_groups}
dl = obj.data.vertices


def main_bone(vids):
    tally = {}
    for vid in vids:
        for g in dl[vid].groups:
            tally[groups[g.group]] = tally.get(groups[g.group], 0) + g.weight
    return max(tally, key=tally.get) if tally else '?'


def depth_inside(p, verts_other, tree_other):
    """Distance a point sits inside another closed piece (0 if outside)."""
    loc, nrm, _, dist = tree_other.find_nearest(p)
    if loc is None:
        return 0.0
    return dist if (loc - p).dot(nrm) > 0 else 0.0


bad = []
for i, (verts, polys, tree) in enumerate(pieces):
    best = 0.0
    hits = 0
    inside = set()
    for j, (v2, p2, t2) in enumerate(pieces):
        if i == j:
            continue
        pairs = tree.overlap(t2)
        if not pairs:
            continue
        hits += len(pairs)
        depths = [depth_inside(p, v2, t2) for p in verts]
        best = max(best, max(depths))
        inside |= {k for k, d in enumerate(depths) if d > 0.01 * STUD}
    vids = [k for k, isl in island.items() if isl == i]
    c = sum(verts, verts[0] * 0) / len(verts) / STUD
    frac = len(inside) / len(verts)
    if hits == 0 or (best / STUD < min_depth and frac < 0.2):
        bad.append((i, main_bone(vids), tuple(round(x, 1) for x in c), hits, round(best / STUD, 2)))

print(f'pieces={n} floating_or_shallow={len(bad)}')
for b in bad:
    print('  piece', b[0], 'bone', b[1], 'centre(studs)', b[2], 'overlap_tris', b[3], 'max_depth', b[4])
sys.exit(1 if bad else 0)
