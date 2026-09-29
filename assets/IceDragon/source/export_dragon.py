"""Export IceDragon.blend for Roblox Studio (FBX + per-clip FBX + GLB)."""
import bpy, os, sys, json
ROOT = os.path.abspath(sys.argv[-1])
bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, 'IceDragon.blend'))
arm = bpy.data.objects['IceDragon']
for img in bpy.data.images:
    img.filepath = bpy.path.relpath(img.filepath_raw) if False else img.filepath
def fbx(path, all_actions, action=None):
    if action: arm.animation_data.action = bpy.data.actions[action]
    sc = bpy.context.scene
    if action:
        a = bpy.data.actions[action]; sc.frame_start, sc.frame_end = int(a.frame_range[0]), int(a.frame_range[1])
    bpy.ops.export_scene.fbx(
        filepath=path, use_selection=False, object_types={'MESH', 'ARMATURE'},
        apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE', bake_space_transform=False,
        axis_forward='-Z', axis_up='Y', use_mesh_modifiers=True, mesh_smooth_type='FACE',
        add_leaf_bones=False, use_armature_deform_only=True, primary_bone_axis='Y', secondary_bone_axis='X',
        bake_anim=True, bake_anim_use_all_bones=True, bake_anim_use_nla_strips=False,
        bake_anim_use_all_actions=all_actions, bake_anim_force_startend_keying=True, bake_anim_step=1.0,
        bake_anim_simplify_factor=0.0, embed_textures=True, path_mode='COPY')
    print('export', path, os.path.getsize(path) // 1024, 'KB')
fbx(os.path.join(ROOT, 'IceDragon.fbx'), True, 'Idle')
fbx(os.path.join(ROOT, 'IceDragon_Idle.fbx'), False, 'Idle')
fbx(os.path.join(ROOT, 'IceDragon_Walk.fbx'), False, 'Walk')
fbx(os.path.join(ROOT, 'IceDragon_FlyIdle.fbx'), False, 'FlyIdle')
fbx(os.path.join(ROOT, 'IceDragon_FlyWalk.fbx'), False, 'FlyWalk')
arm.animation_data.action = bpy.data.actions['Idle']
bpy.ops.export_scene.gltf(filepath=os.path.join(ROOT, 'IceDragon.glb'), export_format='GLB', export_yup=True,
                          export_animations=True, export_animation_mode='ACTIONS', export_skins=True,
                          export_materials='EXPORT', export_image_format='AUTO')
print('export glb', os.path.getsize(os.path.join(ROOT, 'IceDragon.glb')) // 1024, 'KB')
