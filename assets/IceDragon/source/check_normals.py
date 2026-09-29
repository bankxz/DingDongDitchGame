"""Report closed mesh islands whose faces point inward (signed volume < 0)."""
import bpy, bmesh, sys
bpy.ops.wm.open_mainfile(filepath=sys.argv[-1])
for ob in bpy.data.objects:
    if ob.type != 'MESH': continue
    bm = bmesh.new(); bm.from_mesh(ob.data); bm.faces.ensure_lookup_table()
    seen = set(); bad = 0; closed = 0; total = 0
    for f0 in bm.faces:
        if f0.index in seen: continue
        stack = [f0]; isl = []; seen.add(f0.index)
        while stack:
            f = stack.pop(); isl.append(f)
            for e in f.edges:
                for g in e.link_faces:
                    if g.index not in seen: seen.add(g.index); stack.append(g)
        total += 1
        edges = {e for f in isl for e in f.edges}
        if any(len(e.link_faces) != 2 for e in edges): continue
        closed += 1
        vol = 0.0
        for f in isl:
            vs = [v.co for v in f.verts]
            for i in range(1, len(vs) - 1):
                vol += vs[0].dot(vs[i].cross(vs[i + 1])) / 6
        if vol < 0:
            bad += 1
            c = sum((v.co for f in isl for v in f.verts), vs[0] * 0) / sum(len(f.verts) for f in isl)
            if bad <= 12: print('  inward island near', tuple(round(x, 2) for x in c), 'faces', len(isl))
    print(ob.name, 'islands', total, 'closed', closed, 'inward', bad)

# open islands: majority of faces should point away from the island centre
for ob in bpy.data.objects:
    if ob.type != 'MESH': continue
    bm = bmesh.new(); bm.from_mesh(ob.data)
    seen = set(); flagged = []
    for f0 in bm.faces:
        if f0.index in seen: continue
        stack = [f0]; isl = []; seen.add(f0.index)
        while stack:
            f = stack.pop(); isl.append(f)
            for e in f.edges:
                for g in e.link_faces:
                    if g.index not in seen: seen.add(g.index); stack.append(g)
        cs = [f.calc_center_median() for f in isl]
        c = sum(cs, cs[0] * 0) / len(cs)
        inward = sum(1 for f, fc in zip(isl, cs) if f.normal.dot(fc - c) < -1e-6)
        if inward > len(isl) / 2: flagged.append((tuple(round(x, 1) for x in c), len(isl), inward))
    print(ob.name, 'open-or-closed islands mostly inward:', len(flagged))
    for fl in flagged[:15]: print('   ', fl)
