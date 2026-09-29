"""Export Roblox-ready FBX files (rig+mesh, idle, walk) from AncientDragon.blend."""
import bpy, os
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..'))
OUT = os.path.join(ROOT, 'export'); os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, 'AncientDragon.blend'))
rig = bpy.data.objects['DragonRig']; me = bpy.data.objects['AncientDragon']
tris = sum(len(p.vertices) - 2 for p in me.data.polygons)
print('EXPORT TRIS', tris)
assert tris < 5000
# at most 4 influences per vertex (Roblox limit)
for v in me.data.vertices:
    assert len(v.groups) <= 4

def export(path, action=None):
    sc = bpy.context.scene
    if action:
        rig.animation_data.action = bpy.data.actions[action]
        a, b = bpy.data.actions[action].frame_range
        sc.frame_start, sc.frame_end = int(a), int(b)
    else:
        rig.animation_data.action = None
        for pb in rig.pose.bones:
            pb.rotation_quaternion = (1, 0, 0, 0); pb.location = (0, 0, 0)
    bpy.ops.object.select_all(action='DESELECT')
    rig.select_set(True); me.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.export_scene.fbx(
        filepath=path, use_selection=True, object_types={'ARMATURE', 'MESH'},
        apply_unit_scale=True, apply_scale_options='FBX_SCALE_ALL', bake_space_transform=True,
        axis_forward='-Z', axis_up='Y', use_mesh_modifiers=True, mesh_smooth_type='FACE',
        add_leaf_bones=False, primary_bone_axis='Y', secondary_bone_axis='X', use_armature_deform_only=False,
        bake_anim=action is not None, bake_anim_use_all_bones=True, bake_anim_use_nla_strips=False,
        bake_anim_use_all_actions=False, bake_anim_force_startend_keying=True, bake_anim_simplify_factor=0.0,
        embed_textures=True, path_mode='COPY')
    print('exported', path, os.path.getsize(path) // 1024, 'KB')

export(os.path.join(OUT, 'AncientDragon.fbx'))
export(os.path.join(OUT, 'AncientDragon_Idle.fbx'), 'Idle')
export(os.path.join(OUT, 'AncientDragon_Walk.fbx'), 'Walk')
