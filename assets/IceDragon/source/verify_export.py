import bpy, sys, os, json
ROOT = os.path.abspath(sys.argv[-1]); rep = {}
for fn in ('IceDragon.fbx', 'IceDragon_Idle.fbx', 'IceDragon_Walk.fbx', 'IceDragon_FlyIdle.fbx', 'IceDragon_FlyWalk.fbx', 'IceDragon.glb'):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for a in list(bpy.data.actions): bpy.data.actions.remove(a)
    p = os.path.join(ROOT, fn)
    if fn.endswith('.fbx'): bpy.ops.import_scene.fbx(filepath=p)
    else: bpy.ops.import_scene.gltf(filepath=p)
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    tris = sum(sum(len(pl.vertices) - 2 for pl in o.data.polygons) for o in meshes)
    maxinf = max(max((len([g for g in v.groups if g.weight > 0]) for v in o.data.vertices), default=0) for o in meshes)
    dims = [max((o.matrix_world @ v.co)[i] for o in meshes for v in o.data.vertices) - min((o.matrix_world @ v.co)[i] for o in meshes for v in o.data.vertices) for i in range(3)]
    rep[fn] = dict(meshes=[o.name for o in meshes], tris=tris, bones=len(arms[0].data.bones) if arms else 0,
                   max_influences=maxinf, actions={a.name: [round(x) for x in a.frame_range] for a in bpy.data.actions},
                   images=[i.name for i in bpy.data.images if i.has_data or i.packed_file], size=[round(d, 2) for d in dims])
print(json.dumps(rep, indent=1))
json.dump(rep, open(os.path.join(ROOT, 'source', 'export_verification.json'), 'w'), indent=1)
