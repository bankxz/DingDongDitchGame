"""Export GreenDino.blend to Roblox-ready FBX files (settings follow Roblox's Blender export guidance)."""
import os
import bpy
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.abspath(os.path.join(HERE, '..'))
bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT, 'GreenDino.blend'))
rig = bpy.data.objects['GreenDinoRig']
COMMON = dict(use_selection=False, object_types={'MESH', 'ARMATURE'}, apply_unit_scale=True,
              apply_scale_options='FBX_SCALE_ALL', bake_space_transform=True, axis_forward='-Z', axis_up='Y',
              use_mesh_modifiers=False, mesh_smooth_type='FACE', add_leaf_bones=False,
              use_armature_deform_only=False, primary_bone_axis='Y', secondary_bone_axis='X',
              embed_textures=True, path_mode='COPY', bake_anim_force_startend_keying=True,
              bake_anim_simplify_factor=0.0)

def export(name, action):
  for tr in rig.animation_data.nla_tracks: tr.mute = True
  rig.animation_data.action = bpy.data.actions[action] if action else None
  if action:
    a = bpy.data.actions[action]; bpy.context.scene.frame_start, bpy.context.scene.frame_end = map(int, a.frame_range)
  else:
    for pb in rig.pose.bones: pb.matrix_basis.identity()
  bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, name), bake_anim=bool(action),
                           bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False, bake_anim_use_all_bones=True,
                           **COMMON)
  print('EXPORTED', name, os.path.getsize(os.path.join(OUT, name)) // 1024, 'KB')

export('GreenDino.fbx', None)            # rigged model (rest pose) -> Roblox 3D Importer
export('GreenDino_Idle.fbx', 'Idle')     # -> Animation Editor > Import from FBX
export('GreenDino_Walk.fbx', 'Walk')
