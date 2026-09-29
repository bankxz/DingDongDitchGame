import bpy, bmesh, sys
OUT = sys.argv[sys.argv.index('--') + 1]
bpy.ops.wm.open_mainfile(filepath=OUT + 'LavaHorse_Source.blend')
tot = 0
for o in bpy.data.objects:
    if o.type != 'MESH': continue
    bm = bmesh.new(); bm.from_mesh(o.data)
    ngon = sum(len(f.verts) > 4 for f in bm.faces)
    tris = sum(len(f.verts) - 2 for f in bm.faces)
    quads = sum(len(f.verts) == 4 for f in bm.faces)
    nonman = sum(not e.is_manifold for e in bm.edges)
    degen = sum(f.calc_area() < 1e-7 for f in bm.faces)
    nonplanar = 0
    for f in bm.faces:
        if len(f.verts) == 4:
            n = f.normal
            d = [abs((v.co - f.verts[0].co).dot(n)) for v in f.verts]
            nonplanar += max(d) > 1e-4
    loose = sum(not v.link_faces for v in bm.verts)
    islands = 0
    seen = set()
    for f in bm.faces:
        if f.index in seen: continue
        islands += 1; stack = [f]
        while stack:
            g = stack.pop()
            if g.index in seen: continue
            seen.add(g.index)
            stack += [h for e in g.edges for h in e.link_faces if h.index not in seen]
    tot += tris
    print(f'{o.name:18s} tris {tris:5d} quads {quads:4d} ngons {ngon} nonmanifold_edges {nonman} degenerate {degen} nonplanar_quads {nonplanar} loose_verts {loose} islands {islands}')
    bm.free()
print('TOTAL', tot)
# FBX re-import check
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=OUT + 'fbx/LavaHorse.fbx')
t = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in bpy.data.objects if o.type == 'MESH')
imgs = sorted(i.name for i in bpy.data.images)
print('FBX reimport tris', t, 'images', imgs)
