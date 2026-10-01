"""Roblox back-face culls: report inside-out geometry.  python3 check_normals.py model.blend
Closed islands with negative signed volume are inside out. Open islands (open-based shards,
teeth, uncapped lofts) are flagged when most faces point toward the island centre.
Flat two-sided sheets (membranes) are expected to show up in the open-island list."""
import bpy, bmesh, sys
bpy.ops.wm.open_mainfile(filepath=sys.argv[-1])
def islands(bm):
    seen = set()
    for f0 in bm.faces:
        if f0.index in seen: continue
        st, isl = [f0], []; seen.add(f0.index)
        while st:
            f = st.pop(); isl.append(f)
            for e in f.edges:
                for g in e.link_faces:
                    if g.index not in seen: seen.add(g.index); st.append(g)
        yield isl
bad_total = 0
for ob in [o for o in bpy.data.objects if o.type == 'MESH']:
    bm = bmesh.new(); bm.from_mesh(ob.data); bm.faces.ensure_lookup_table()
    closed = inward = openflag = n = 0
    for isl in islands(bm):
        n += 1; cs = [f.calc_center_median() for f in isl]; c = sum(cs, cs[0] * 0) / len(cs)
        if all(len(e.link_faces) == 2 for f in isl for e in f.edges):
            closed += 1; vol = 0.0
            for f in isl:
                vs = [v.co for v in f.verts]
                for i in range(1, len(vs) - 1): vol += vs[0].dot(vs[i].cross(vs[i + 1])) / 6
            if vol < 0: inward += 1; print('  inside-out closed island near', tuple(round(x, 2) for x in c))
        elif sum(1 for f, fc in zip(isl, cs) if f.normal.dot(fc - c) < -1e-6) > len(isl) / 2:
            openflag += 1; print('  open island mostly inward near', tuple(round(x, 2) for x in c), 'faces', len(isl))
    bad_total += inward
    print(f'{ob.name}: islands {n}, closed {closed}, closed inside-out {inward}, open mostly-inward {openflag}')
print('RESULT', 'FAIL' if bad_total else 'PASS (review open-island list: only intentional sheets should appear)')
