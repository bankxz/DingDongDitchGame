"""Roblox FBX: rigged model (rest pose) + one FBX per animation. 1 Blender unit = 1 stud."""
import os, json, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import design as D
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'build') + '/'
FBX = OUT + 'fbx/'
os.makedirs(FBX, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=OUT + 'LavaHorse_Source.blend')
rig = bpy.data.objects['LavaHorse_Rig']
meshes = [bpy.data.objects[n] for n in D.OBJECTS]
COMMON = dict(use_selection=True, object_types={'ARMATURE', 'MESH'}, apply_unit_scale=True,
              apply_scale_options='FBX_SCALE_NONE', axis_forward='-Z', axis_up='Y', use_mesh_modifiers=False,
              mesh_smooth_type='FACE', use_tspace=True, add_leaf_bones=False, primary_bone_axis='Y',
              secondary_bone_axis='X', use_armature_deform_only=False, armature_nodetype='NULL',
              path_mode='COPY', embed_textures=True)


def select(objs):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.hide_set(False); o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


rig.animation_data.action = None
for pb in rig.pose.bones:
    pb.matrix_basis.identity()
select([rig] + meshes)
bpy.ops.export_scene.fbx(filepath=FBX + 'LavaHorse.fbx', bake_anim=False, **COMMON)
for act in ('LavaHorse_Idle', 'LavaHorse_Walk'):
    a = bpy.data.actions[act]
    rig.animation_data.action = a
    bpy.context.scene.frame_start, bpy.context.scene.frame_end = int(a.frame_range[0]), int(a.frame_range[1])
    bpy.context.scene.name = act
    select([rig] + meshes)
    bpy.ops.export_scene.fbx(filepath=FBX + f'{act}.fbx', bake_anim=True, bake_anim_use_all_bones=True,
                             bake_anim_use_nla_strips=False, bake_anim_use_all_actions=False,
                             bake_anim_force_startend_keying=True, bake_anim_step=1.0, bake_anim_simplify_factor=0.0,
                             **COMMON)
bpy.context.scene.name = 'Scene'
stats = {o.name: dict(triangles=sum(len(p.vertices) - 2 for p in o.data.polygons), material=o.data.materials[0].name)
         for o in meshes}
stats['TOTAL_triangles'] = sum(v['triangles'] for v in stats.values())
stats['bones'] = [b.name for b in rig.data.bones]
stats['actions'] = {a.name: [int(a.frame_range[0]), int(a.frame_range[1])] for a in bpy.data.actions}
json.dump(stats, open(OUT + 'stats.json', 'w'), indent=1)
print('EXPORT', stats['TOTAL_triangles'], 'tris', len(stats['bones']), 'bones', stats['actions'])
