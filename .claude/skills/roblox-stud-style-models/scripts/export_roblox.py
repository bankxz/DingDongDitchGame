"""Export a rigged stud model for Roblox.  python3 export_roblox.py model.blend out_dir Name
Writes Name.fbx (mesh + rig + every action as a take, for the 3D Importer), one
Name_<Action>.fbx per action (for Animation Editor > Import > From FBX Animation) and Name.glb."""
import bpy, os, sys
blend, out, name = sys.argv[-3], sys.argv[-2], sys.argv[-1]
bpy.ops.wm.open_mainfile(filepath=blend); os.makedirs(out, exist_ok=True)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE'); acts = [a for a in bpy.data.actions]
def fbx(path, all_actions, act=None):
    if act:
        arm.animation_data.action = act; sc = bpy.context.scene
        sc.frame_start, sc.frame_end = int(act.frame_range[0]), int(act.frame_range[1])
    bpy.ops.export_scene.fbx(filepath=path, object_types={'MESH', 'ARMATURE'}, apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_NONE', axis_forward='-Z', axis_up='Y', use_mesh_modifiers=True,
        mesh_smooth_type='FACE', add_leaf_bones=False, use_armature_deform_only=True,
        primary_bone_axis='Y', secondary_bone_axis='X', bake_anim=True, bake_anim_use_all_bones=True,
        bake_anim_use_nla_strips=False, bake_anim_use_all_actions=all_actions,
        bake_anim_force_startend_keying=True, bake_anim_step=1.0, bake_anim_simplify_factor=0.0,
        embed_textures=True, path_mode='COPY')
    print('export', os.path.basename(path), os.path.getsize(path) // 1024, 'KB')
fbx(os.path.join(out, name + '.fbx'), True, acts[0] if acts else None)
for a in acts: fbx(os.path.join(out, f'{name}_{a.name}.fbx'), False, a)
if acts: arm.animation_data.action = acts[0]
bpy.ops.export_scene.gltf(filepath=os.path.join(out, name + '.glb'), export_format='GLB', export_yup=True,
                          export_animations=True, export_animation_mode='ACTIONS', export_skins=True)
print('export', name + '.glb')
