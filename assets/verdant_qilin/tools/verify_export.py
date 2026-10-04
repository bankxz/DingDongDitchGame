"""Re-import every FBX/GLB in a folder and report tris, bones, max weights/vertex, clips, textures.
python3 verify_export.py out_dir   (Blender's glTF importer adds an ~80-tri bone-display sphere)"""
import bpy, sys, os, glob
for p in sorted(glob.glob(os.path.join(sys.argv[-1], '*.fbx')) + glob.glob(os.path.join(sys.argv[-1], '*.glb'))):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    (bpy.ops.import_scene.fbx if p.endswith('.fbx') else bpy.ops.import_scene.gltf)(filepath=p)
    ms = [o for o in bpy.data.objects if o.type == 'MESH']; arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    tris = sum(sum(len(pl.vertices) - 2 for pl in o.data.polygons) for o in ms)
    inf = max((len([g for g in v.groups if g.weight > 0]) for o in ms for v in o.data.vertices), default=0)
    print(os.path.basename(p), '| tris', tris, '| bones', len(arms[0].data.bones) if arms else 0, '| max weights', inf,
          '| clips', {a.name: tuple(round(x) for x in a.frame_range) for a in bpy.data.actions},
          '| images', [i.name for i in bpy.data.images if i.has_data or i.packed_file])
