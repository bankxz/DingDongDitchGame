"""Export the lava-textured Hellhound for Roblox (run after retexture.py). Same settings as the Lava Scorpion."""
import os
import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
OUT = os.path.join(ROOT, "export")
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, "LavaHellhound.blend"))
arm, mesh = bpy.data.objects["Hellhound"], bpy.data.objects["HellhoundMesh"]
for o in bpy.data.objects:
    o.select_set(o in (arm, mesh))
bpy.context.view_layer.objects.active = arm
fbx = os.path.join(OUT, "LavaHellhound.fbx")
bpy.ops.export_scene.fbx(
    filepath=fbx, use_selection=True, object_types={"ARMATURE", "MESH"},
    apply_unit_scale=True, apply_scale_options="FBX_SCALE_ALL", axis_forward="-Z", axis_up="Y",
    use_mesh_modifiers=False, mesh_smooth_type="FACE", add_leaf_bones=False, primary_bone_axis="Y",
    secondary_bone_axis="X", use_armature_deform_only=False, bake_anim=False, path_mode="COPY", embed_textures=True)
glb = os.path.join(OUT, "LavaHellhound.glb")
bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", use_selection=True, export_yup=True,
                          export_skins=True, export_materials="EXPORT", export_animations=False)
print("EXPORT", fbx, os.path.getsize(fbx), glb, os.path.getsize(glb))
