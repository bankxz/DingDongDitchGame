"""Export TRex.blend for Roblox Studio.

python3 export_roblox.py <TRex.blend> <out_dir>

Writes:
  TRex.fbx       - skinned mesh + armature in bind pose (import this with the 3D Importer)
  TRex_Idle.fbx  - rig + Idle action (Animation Editor > Import > From FBX Animation)
  TRex_Walk.fbx  - rig + Walk action
  TRex.glb       - glTF with both actions + albedo/normal/emissive (optional alternative)
"""
import os
import sys

import bpy

blend, out = sys.argv[1], sys.argv[2]
bpy.ops.wm.open_mainfile(filepath=blend)
scene = bpy.context.scene
rig = bpy.data.objects['TRexRig']

FBX = dict(
    use_selection=False,
    object_types={'MESH', 'ARMATURE'},
    apply_unit_scale=True,
    apply_scale_options='FBX_SCALE_NONE',
    bake_space_transform=False,
    axis_forward='-Z',
    axis_up='Y',
    use_mesh_modifiers=False,
    mesh_smooth_type='FACE',
    use_armature_deform_only=True,
    add_leaf_bones=False,
    primary_bone_axis='Y',
    secondary_bone_axis='X',
    embed_textures=True,
    path_mode='COPY',
)


def export(name, action):
    if action is None:
        rig.animation_data.action = None
        for pb in rig.pose.bones:
            pb.rotation_euler = (0, 0, 0)
            pb.location = (0, 0, 0)
    else:
        act = bpy.data.actions[action]
        rig.animation_data.action = act
        scene.frame_start, scene.frame_end = (int(v) for v in act.frame_range)
    path = os.path.join(out, name)
    bpy.ops.export_scene.fbx(filepath=path, bake_anim=action is not None,
                             bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False,
                             bake_anim_use_all_bones=True, bake_anim_force_startend_keying=True,
                             bake_anim_step=1.0, bake_anim_simplify_factor=0.0, **FBX)
    print('exported', path, os.path.getsize(path))


export('TRex.fbx', None)
export('TRex_Idle.fbx', 'Idle')
export('TRex_Walk.fbx', 'Walk')

# glTF with both clips as separate animations
rig.animation_data.action = None
for act in ('Idle', 'Walk'):
    track = rig.animation_data.nla_tracks.new()
    track.name = act
    track.strips.new(act, int(bpy.data.actions[act].frame_range[0]), bpy.data.actions[act])
glb = os.path.join(out, 'TRex.glb')
bpy.ops.export_scene.gltf(filepath=glb, export_format='GLB', export_animations=True,
                          export_animation_mode='NLA_TRACKS', export_skins=True, export_yup=True)
print('exported', glb, os.path.getsize(glb))
