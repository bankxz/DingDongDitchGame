import bpy, os
H = os.path.dirname(os.path.abspath(__file__)); bpy.ops.wm.open_mainfile(filepath=os.path.join(H, 'out/Qilin.blend'))
bpy.ops.export_scene.fbx(filepath=os.path.join(H, 'out/Qilin.fbx'), object_types={'MESH'}, apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE',
    axis_forward='-Z', axis_up='Y', mesh_smooth_type='FACE', embed_textures=True, path_mode='COPY')
bpy.ops.export_scene.gltf(filepath=os.path.join(H, 'out/Qilin.glb'), export_format='GLB', export_yup=True)
