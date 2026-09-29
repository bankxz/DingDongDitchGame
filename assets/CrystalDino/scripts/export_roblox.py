"""Export CrystalDino.blend for Roblox Studio.

  export/CrystalDino.fbx        rigged, skinned model in bind pose (3D Importer)
  export/CrystalDino_Idle.fbx   Idle animation (Animation Editor > Import > From FBX Animation)
  export/CrystalDino_Walk.fbx   Walk animation
  export/CrystalDino.glb        model + both animations (preview / other engines)

Only deform bones are exported; the IK controllers are baked into the animation.
"""
import os

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "export")
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, "CrystalDino.blend"))
scene = bpy.context.scene
arm = bpy.data.objects["CrystalDino_Rig"]
meshes = [bpy.data.objects["CrystalDino_Body"], bpy.data.objects["CrystalDino_Glow"]]

tris = sum(len(p.vertices) - 2 for m in meshes for p in m.data.polygons)
assert tris < 5000, tris
print("triangles", tris)


def select_all():
    bpy.ops.object.select_all(action="DESELECT")
    for o in [arm] + meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = arm


def fbx(path, anim):
    select_all()
    bpy.ops.export_scene.fbx(
        filepath=path,
        use_selection=True,
        object_types={"ARMATURE", "MESH"},
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_ALL",
        axis_forward="-Z",
        axis_up="Y",
        use_mesh_modifiers=False,  # keep skinning (armature modifier must not be applied)
        mesh_smooth_type="FACE",
        use_armature_deform_only=True,
        add_leaf_bones=False,
        primary_bone_axis="Y",
        secondary_bone_axis="X",
        bake_anim=anim,
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


def rest():
    arm.animation_data.action = None
    for b in arm.pose.bones:
        b.location = (0, 0, 0)
        b.rotation_quaternion = (1, 0, 0, 0)
    scene.frame_set(1)


rest()
fbx(os.path.join(OUT, "CrystalDino.fbx"), anim=False)

for name, n in (("Idle", 90), ("Walk", 40)):
    arm.animation_data.action = bpy.data.actions[name]
    scene.frame_start, scene.frame_end = 1, n + 1  # last frame == first frame -> seamless loop
    fbx(os.path.join(OUT, "CrystalDino_%s.fbx" % name), anim=True)

# GLB with both clips (NLA tracks so glTF exports each action as its own animation)
rest()
arm.animation_data.action = None
for name, n in (("Idle", 90), ("Walk", 40)):
    tr = arm.animation_data.nla_tracks.new()
    tr.name = name
    st = tr.strips.new(name, 1, bpy.data.actions[name])
    st.action_frame_end = n + 1
    tr.mute = False
select_all()
bpy.ops.export_scene.gltf(
    filepath=os.path.join(OUT, "CrystalDino.glb"),
    export_format="GLB",
    use_selection=True,
    export_yup=True,
    export_apply=False,
    export_animations=True,
    export_animation_mode="NLA_TRACKS",
    export_force_sampling=True,
    export_def_bones=True,
    export_skins=True,
    export_image_format="AUTO",
)
print("exported glb")
