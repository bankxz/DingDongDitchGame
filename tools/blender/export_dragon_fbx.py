"""Export AncientDragon.blend to Roblox-ready FBX files.

  AncientDragon.fbx       - skinned meshes + armature in rest pose (import with the 3D Importer)
  AncientDragon_FlyIdle.fbx - rig + hovering flight loop (Animation Editor > Import > From FBX Animation)
  AncientDragon_Fly.fbx     - rig + flying-forward loop
"""
import os

import bpy

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "assets", "models", "AncientDragon")
bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT, "AncientDragon.blend"))
arm = bpy.data.objects["AncientDragon"]
for tr in list(arm.animation_data.nla_tracks):
    arm.animation_data.nla_tracks.remove(tr)


def export(path, action=None):
    sc = bpy.context.scene
    if action:
        act = bpy.data.actions[action]
        arm.animation_data.action = act
        try:
            arm.animation_data.action_slot = arm.animation_data.action_suggested_slots[0]
        except Exception:
            pass
        fr = act.frame_range
        sc.frame_start, sc.frame_end = int(fr[0]), int(fr[1])
    else:
        arm.animation_data.action = None
        for pb in arm.pose.bones:
            pb.location = (0, 0, 0)
            pb.rotation_euler = (0, 0, 0)
            pb.rotation_quaternion = (1, 0, 0, 0)
    bpy.ops.export_scene.fbx(
        filepath=path,
        use_selection=False,
        object_types={"ARMATURE", "MESH"},
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_ALL",
        axis_forward="-Z",
        axis_up="Y",
        use_mesh_modifiers=False,
        mesh_smooth_type="FACE",
        add_leaf_bones=False,
        primary_bone_axis="Y",
        secondary_bone_axis="X",
        use_armature_deform_only=False,
        bake_anim=bool(action),
        bake_anim_use_all_bones=True,
        bake_anim_use_nla_strips=False,
        bake_anim_use_all_actions=False,
        bake_anim_force_startend_keying=True,
        bake_anim_step=1.0,
        bake_anim_simplify_factor=0.0,
        path_mode="COPY",
        embed_textures=True,
    )
    print("exported", path, os.path.getsize(path))


export(os.path.join(OUT, "AncientDragon.fbx"))
export(os.path.join(OUT, "AncientDragon_FlyIdle.fbx"), "Dragon_FlyIdle")
export(os.path.join(OUT, "AncientDragon_Fly.fbx"), "Dragon_Fly")
