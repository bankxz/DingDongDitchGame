"""
Re-import every exported FBX into an empty scene and verify what Roblox will receive.

    python3 validate_fbx.py      -> ../validation/fbx_report.json
"""
import glob
import json
import os

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ASSET = os.path.dirname(HERE)


def check(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=path)
    objs = list(bpy.context.scene.objects)
    arms = [o for o in objs if o.type == 'ARMATURE']
    meshes = [o for o in objs if o.type == 'MESH']
    other = [o.name for o in objs if o.type not in ('ARMATURE', 'MESH')]
    rig, mesh = arms[0], meshes[0]
    me = mesh.data
    world = [mesh.matrix_world @ v.co for v in me.vertices]
    ys = [p.y for p in world]
    zs = [p.z for p in world]
    # Head/tail positions of the head bone vs tail bone give the facing direction
    head = rig.matrix_world @ rig.data.bones['Head'].head_local
    tail = rig.matrix_world @ rig.data.bones['Tail_04'].tail_local
    foot = rig.matrix_world @ rig.data.bones['FrontLeg_L_Foot'].head_local
    # every piece is a closed shell: outward normals <=> positive signed volume per shell
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    seen, shells, inverted, open_shells = set(), 0, 0, 0
    for f in bm.faces:
        if f in seen:
            continue
        stack, shell = [f], []
        seen.add(f)
        while stack:
            g = stack.pop()
            shell.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h not in seen:
                        seen.add(h)
                        stack.append(h)
        shells += 1
        vol = 0.0
        for g in shell:
            vs = [v.co for v in g.verts]
            for i in range(1, len(vs) - 1):
                vol += vs[0].dot(vs[i].cross(vs[i + 1])) / 6
        inverted += vol < 0
        open_shells += any(not e.is_manifold for g in shell for e in g.edges)
    bm.free()
    rep = dict(
        objects=[o.name for o in objs], non_mesh_non_armature=other,
        bones=len(rig.data.bones), bone_names=[b.name for b in rig.data.bones],
        root_bones=[b.name for b in rig.data.bones if b.parent is None],
        leaf_end_bones=[b.name for b in rig.data.bones if b.name.endswith('_end')],
        triangles=sum(len(p.vertices) - 2 for p in me.polygons),
        vertex_groups=len(mesh.vertex_groups),
        has_armature_modifier=any(m.type == 'ARMATURE' for m in mesh.modifiers),
        uv_layers=[u.name for u in me.uv_layers],
        materials=[m.name for m in me.materials if m],
        images=[i.name for i in bpy.data.images if i.has_data or i.packed_file],
        size_m=[round(v, 3) for v in mesh.dimensions],
        size_studs=[round(v / 0.28, 2) for v in mesh.dimensions],
        min_z_m=round(min(zs), 4),
        head_is_forward_of_tail=head.y < tail.y,
        feet_below_head=foot.z < head.z,
        mesh_length_axis_y=round(max(ys) - min(ys), 3),
        closed_shells=shells, inverted_shells=inverted, open_shells=open_shells,
    )
    if rig.animation_data and rig.animation_data.action:
        a = rig.animation_data.action
        rep['action'] = a.name
        rep['action_frames'] = [int(a.frame_range[0]), int(a.frame_range[1])]
        rep['animated_bones'] = len({fc.data_path.split('"')[1] for fc in a.fcurves if '"' in fc.data_path})
    return rep


def main():
    files = [os.path.join(ASSET, 'Triceratops.fbx')] + sorted(glob.glob(os.path.join(ASSET, 'animations', '*.fbx')))
    report = {}
    for f in files:
        r = check(f)
        r['file_size_kb'] = round(os.path.getsize(f) / 1024, 1)
        report[os.path.relpath(f, ASSET)] = r
        assert r['root_bones'] == ['Root'], r['root_bones']
        assert not r['leaf_end_bones'] and not r['non_mesh_non_armature'], r
        assert r['inverted_shells'] == 0 and r['open_shells'] == 0, r
        assert r['head_is_forward_of_tail'] and r['feet_below_head'] and r['min_z_m'] > -0.01, r
    with open(os.path.join(ASSET, 'validation', 'fbx_report.json'), 'w') as fh:
        json.dump(report, fh, indent=2)
    for k, r in report.items():
        print(k, {x: r.get(x) for x in ('bones', 'triangles', 'size_studs', 'images', 'action', 'action_frames',
                                         'animated_bones', 'file_size_kb')})


if __name__ == '__main__':
    main()
