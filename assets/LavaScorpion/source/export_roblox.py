"""Export LavaScorpion for Roblox Studio (run after animate.py).

LavaScorpion.fbx        rig + skinned mesh + embedded texture, rest pose (import with the 3D Importer)
LavaScorpion_Idle.fbx   same rig, Idle clip only   (Animation Editor > Import > From FBX Animation)
LavaScorpion_Walk.fbx   same rig, Walk clip only
LavaScorpion.glb        everything incl. both clips (alternative format)
Settings follow Roblox's Blender export guidance: -Z forward / Y up, FBX All scaling, no leaf bones,
deform bones only, baked keys with forced start/end.
"""
import os

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
OUT = os.path.join(ROOT, "export")
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, "LavaScorpion.blend"))
sc = bpy.context.scene
arm = bpy.data.objects["LavaScorpion"]
mesh = bpy.data.objects["GEO-LavaScorpion"]
tris = sum(len(p.vertices) - 2 for p in mesh.data.polygons)
assert tris < 5000, tris

for o in bpy.data.objects:
    o.select_set(o in (arm, mesh))
bpy.context.view_layer.objects.active = arm


def mute_nla(m):
    for tr in arm.animation_data.nla_tracks:
        tr.mute = m


def fbx(path, action=None):
    arm.animation_data_create()
    mute_nla(True)
    arm.animation_data.action = bpy.data.actions[action] if action else None
    if action:
        act = bpy.data.actions[action]
        if hasattr(arm.animation_data, "action_slot") and act.slots:
            arm.animation_data.action_slot = act.slots[0]
        sc.frame_start, sc.frame_end = int(act.frame_range[0]), int(act.frame_range[1])
    bpy.ops.export_scene.fbx(
        filepath=path, use_selection=True, object_types={"ARMATURE", "MESH"},
        apply_unit_scale=True, apply_scale_options="FBX_SCALE_ALL", bake_space_transform=False,
        axis_forward="-Z", axis_up="Y", use_mesh_modifiers=False, mesh_smooth_type="FACE",
        add_leaf_bones=False, primary_bone_axis="Y", secondary_bone_axis="X", use_armature_deform_only=True,
        bake_anim=bool(action), bake_anim_use_all_bones=True, bake_anim_use_nla_strips=False,
        bake_anim_use_all_actions=False, bake_anim_force_startend_keying=True, bake_anim_step=1.0,
        bake_anim_simplify_factor=0.0, path_mode="COPY", embed_textures=True)
    print("EXPORT", path, os.path.getsize(path))


fbx(os.path.join(OUT, "LavaScorpion.fbx"))
fbx(os.path.join(OUT, "LavaScorpion_Idle.fbx"), "Idle")
fbx(os.path.join(OUT, "LavaScorpion_Walk.fbx"), "Walk")

arm.animation_data.action = None
mute_nla(False)
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "LavaScorpion.glb"), export_format="GLB", use_selection=True,
                          export_yup=True, export_animations=True, export_animation_mode="ACTIONS",
                          export_skins=True, export_materials="EXPORT", export_apply=False)
print("EXPORT glb", os.path.getsize(os.path.join(OUT, "LavaScorpion.glb")))
print(f"STATS tris={tris} bones={len(arm.data.bones)} actions={[a.name for a in bpy.data.actions]}")
