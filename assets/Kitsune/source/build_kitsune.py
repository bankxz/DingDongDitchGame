"""
Build the complete Roblox-ready kitsune in Blender (headless or inside Blender).

    python build_kitsune.py -- --out ../            (pip 'bpy' module)
    blender -b -P build_kitsune.py -- --out ../     (Blender 4.2+)

Pipeline: geometry -> UV pack -> painted texture atlas -> 6 material slots ->
armature + procedural skin weights -> Idle / Sleep / Run actions -> .blend,
FBX exports and PNG textures.
"""
import os
import sys
import math
import json
import argparse

import numpy as np
import bpy
import bmesh
from mathutils import Vector, Matrix, Quaternion

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kitsune_geo as kg          # noqa: E402
import kitsune_paint as kp        # noqa: E402
import kitsune_sculpt as ks       # noqa: E402

WORLD_SCALE = 4.0                 # shoulder height in Blender units (= studs in Roblox)
TRI_BUDGET = 9900                 # hard limit 10k
TEX_SIZE = 2048
FPS = 30

MATERIAL_SLOTS = [                # (slot name, region id)
    ('M_Kitsune_Fur_Purple', kp.REG_FUR),
    ('M_Kitsune_Glow_Cyan_EMISSIVE', kp.REG_CYAN),
    ('M_Kitsune_TailTips_EMISSIVE', kp.REG_TIP),
    ('M_Kitsune_Rope_Red', kp.REG_ROPE),
    ('M_Kitsune_Ornament_Red', kp.REG_ORN),
    ('M_Kitsune_Eyes_Red_EMISSIVE', kp.REG_EYE),
]
PART_DEFAULT_REGION = {
    'rope': kp.REG_ROPE, 'knot': kp.REG_ROPE, 'gem': kp.REG_ORN, 'frame': kp.REG_ORN, 'bead': kp.REG_ORN,
    'tassel': kp.REG_ORN, 'eye': kp.REG_EYE, 'claw': kp.REG_CYAN, 'paw': kp.REG_CYAN, 'tuft_cyan': kp.REG_CYAN,
    'tuft_tip': kp.REG_FUR, 'tuft_cheek': kp.REG_FUR,
}
UV_IMPORTANCE = {
    'head': 2.6, 'eye': 3.6, 'gem': 2.5, 'frame': 2.0, 'ear': 2.7, 'neck': 1.3, 'torso': 1.2, 'tail': 0.80,
    'leg_f': 1.1, 'leg_h': 1.1, 'paw': 1.4, 'claw': 0.6, 'tuft': 0.8, 'tuft_cyan': 1.3, 'spike': 0.8,
    'tail_tuft': 0.8, 'tuft_tip': 1.0, 'tuft_cheek': 2.3, 'rope': 0.9, 'knot': 0.9, 'bead': 1.3, 'tassel': 1.2,
}
SLOT_EMISSION = {'M_Kitsune_Eyes_Red_EMISSIVE': 2.2}     # eyes glow hotter than the cyan fur markings


# ============================================================ mesh + UVs
def build_mesh(md, name='Kitsune'):
    S = WORLD_SCALE
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v * S) for v in md.verts], [], md.faces)
    me.update()
    assert len(me.polygons) == len(md.faces)
    # UVs: normalise each island to (3D area * importance), then pack
    inv = {v: k for k, v in kg.PART_IDS.items()}
    uv_raw = [np.array(f, float) for f in md.face_uv]
    isl_area3, isl_areauv = {}, {}
    for fi, f in enumerate(md.faces):
        pts = np.array([md.verts[v] for v in f])
        a3 = 0.0
        auv = 0.0
        uv = uv_raw[fi]
        for j in range(1, len(f) - 1):
            a3 += 0.5 * np.linalg.norm(np.cross(pts[j] - pts[0], pts[j + 1] - pts[0]))
            e1, e2 = uv[j] - uv[0], uv[j + 1] - uv[0]
            auv += 0.5 * abs(e1[0] * e2[1] - e1[1] * e2[0])
        isl = md.face_island[fi]
        isl_area3[isl] = isl_area3.get(isl, 0) + a3
        isl_areauv[isl] = isl_areauv.get(isl, 0) + auv
    me.uv_layers.new(name='UVMap')
    for nm_, ty_, dom_ in (('k_t', 'FLOAT', 'CORNER'), ('k_th', 'FLOAT', 'CORNER'), ('k_len', 'FLOAT', 'CORNER'),
                           ('k_part', 'INT', 'FACE')):
        me.attributes.new(nm_, ty_, dom_)
    loops_uv = np.zeros((len(me.loops), 2))
    lt = np.zeros(len(me.loops)); lth = np.zeros(len(me.loops)); lrl = np.zeros(len(me.loops))
    for poly in me.polygons:
        fi = poly.index
        isl = md.face_island[fi]
        part = inv[md.face_part[fi]]
        k = math.sqrt(isl_area3[isl] / max(isl_areauv[isl], 1e-12)) * UV_IMPORTANCE.get(part, 1.0)
        for j, li in enumerate(poly.loop_indices):
            loops_uv[li] = uv_raw[fi][j] * k
            lt[li], lth[li] = md.face_at[fi][j]
            lrl[li] = md.face_uv[fi][j][1]
    # (re-fetch attribute handles: adding layers invalidates earlier references)
    me.uv_layers['UVMap'].data.foreach_set('uv', loops_uv.ravel())
    me.attributes['k_t'].data.foreach_set('value', lt)
    me.attributes['k_th'].data.foreach_set('value', lth)
    me.attributes['k_len'].data.foreach_set('value', lrl)
    me.attributes['k_part'].data.foreach_set('value', np.array(md.face_part, dtype=np.int32))
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ks.assign_groups(ob, [dict(sorted(w.items(), key=lambda kv: -kv[1])[:4]) for w in md.weights])
    return ob


def join_objects(objs, name):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.data.name = name + '_Mesh'
    return ob


def pack_uvs(ob):
    bpy.context.view_layer.objects.active = ob
    for o in bpy.context.view_layer.objects:
        o.select_set(o == ob)
    bpy.context.scene.tool_settings.use_uv_select_sync = True
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.pack_islands(rotate=True, scale=True, margin=0.0025, shape_method='CONCAVE')
    bpy.ops.object.mode_set(mode='OBJECT')


# ============================================================ textures
def face_parts(ob):
    fp = np.zeros(len(ob.data.polygons), dtype=np.int32)
    ob.data.attributes['k_part'].data.foreach_get('value', fp)
    return fp


def gather_triangles(ob):
    me = ob.data
    me.calc_loop_triangles()
    S = WORLD_SCALE
    nT = len(me.loop_triangles)
    loops = np.array([lt.loops[:] for lt in me.loop_triangles])
    faces = np.array([lt.polygon_index for lt in me.loop_triangles])
    uv = np.zeros(len(me.loops) * 2); me.uv_layers['UVMap'].data.foreach_get('uv', uv); uv = uv.reshape(-1, 2)
    t = np.zeros(len(me.loops)); me.attributes['k_t'].data.foreach_get('value', t)
    th = np.zeros(len(me.loops)); me.attributes['k_th'].data.foreach_get('value', th)
    rl = np.zeros(len(me.loops)); me.attributes['k_len'].data.foreach_get('value', rl)
    vidx = np.zeros(len(me.loops), dtype=np.int64); me.loops.foreach_get('vertex_index', vidx)
    co = np.zeros(len(me.vertices) * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3) / S
    nrm = np.array([cn.vector[:] for cn in me.corner_normals])
    part = face_parts(ob)[faces]
    return dict(uv=uv[loops], t=t[loops], th=th[loops], P=co[vidx[loops]], N=nrm[loops], part=part,
                face=faces, rl=rl[loops])


def ear_frame(tri):
    """Left-ear frame and outline in metric (along, across) coordinates,
    measured on the final sculpted mesh (the right ear is its exact mirror)."""
    base = kg.EAR_BASE
    ax = kg.norm(kg.EAR_TIP - base)
    ref = kg.norm(kg.v3(1.0, 0.12, 0.0))
    side = kg.norm(ref - np.dot(ref, ax) * ax)
    back = np.cross(ax, side)
    back = back if back[1] > 0 else -back
    T = tri['P'][tri['part'] == kg.PART_IDS['ear']]
    T = T[T[:, :, 0].mean(1) > 0]
    # dense samples inside every triangle (the decimated ear has few vertices)
    g = np.array([(i, j) for i in range(9) for j in range(9 - i)], float) / 8.0
    bary = np.c_[1 - g.sum(1), g]
    P = np.einsum('kb,tbx->tkx', bary, T).reshape(-1, 3)
    d = P - base
    a, c = d @ ax, d @ side
    a_tip = float(a.max())
    bins = np.linspace(np.percentile(a, 0.5), a_tip - 0.004, 31)
    ac, lo, hi = [], [], []
    for b0, b1 in zip(bins, bins[1:]):
        k = (a >= b0) & (a < b1)
        if k.sum() >= 3:
            ac.append(0.5 * (b0 + b1)); lo.append(c[k].min()); hi.append(c[k].max())
    lo, hi = np.array(lo), np.array(hi)
    for _ in range(2):
        lo = np.convolve(np.r_[lo[0], lo, lo[-1]], [0.25, 0.5, 0.25], 'valid')
        hi = np.convolve(np.r_[hi[0], hi, hi[-1]], [0.25, 0.5, 0.25], 'valid')
    c_tip = float(c[a > a_tip - 0.006].mean())
    outline = np.array([(x, y) for x, y in zip(ac, lo)] + [(a_tip, c_tip)] + [(x, y) for x, y in zip(ac[::-1], hi[::-1])])
    near_base = np.array(ac) < ac[0] + 0.05
    return dict(base=base, ax=ax, side=side, back=back, outline=outline, a_tip=a_tip,
                c_mid=float(0.5 * (lo[near_base] + hi[near_base]).mean()))


def paint_textures(ob, lofts, outdir):
    tri = gather_triangles(ob)
    head = lofts['head']
    eye_c, eye_n, along, acr = lofts['eye_frames'][1]       # the seated lens frame (left eye)
    ctx = {'eye_center': eye_c, 'eye_n': eye_n, 'eye_along': along, 'eye_acr': acr,
           'head_line': np.array([[c[1], c[2]] for c in head.c]), 'nose_y': float(kg.HEAD_KEYS[-1, 0]) - 0.033,
           'eye_poly': np.array([ks.eye_outline(kg.TAU * k / 256) for k in range(256)]), 'ear': ear_frame(tri)}
    img, em, ro, nrm, face_reg, has = kp.paint_all(tri['uv'], tri['t'], tri['th'], tri['P'], tri['N'], tri['part'],
                                                   tri['face'], tri['rl'], len(ob.data.polygons), ctx, TEX_SIZE)
    inv = {v: k for k, v in kg.PART_IDS.items()}
    fp = face_parts(ob)
    for fi in np.where(~has)[0]:
        face_reg[fi] = PART_DEFAULT_REGION.get(inv[int(fp[fi])], kp.REG_FUR)
    from PIL import Image
    os.makedirs(outdir, exist_ok=True)
    paths = {
        'color': os.path.join(outdir, 'T_Kitsune_Color.png'),
        'emissive': os.path.join(outdir, 'T_Kitsune_EmissiveMask.png'),
        'roughness': os.path.join(outdir, 'T_Kitsune_Roughness.png'),
        'normal': os.path.join(outdir, 'T_Kitsune_Normal.png'),
        'metalness': os.path.join(outdir, 'T_Kitsune_Metalness.png'),
    }
    Image.fromarray((img * 255 + 0.5).astype(np.uint8), 'RGB').save(paths['color'], optimize=True)
    Image.fromarray((em * 255 + 0.5).astype(np.uint8), 'L').save(paths['emissive'], optimize=True)
    Image.fromarray((ro * 255 + 0.5).astype(np.uint8), 'L').save(paths['roughness'], optimize=True)
    Image.fromarray((nrm * 255 + 0.5).astype(np.uint8), 'RGB').save(paths['normal'], optimize=True)
    Image.fromarray(np.zeros((64, 64), np.uint8), 'L').save(paths['metalness'], optimize=True)
    return paths, face_reg


# ============================================================ materials
def load_img(path, colorspace):
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = colorspace
    return img


def make_materials(ob, paths, face_reg, emission_strength=0.55):
    me = ob.data
    col = load_img(paths['color'], 'sRGB')
    emi = load_img(paths['emissive'], 'Non-Color')
    rou = load_img(paths['roughness'], 'Non-Color')
    nor = load_img(paths['normal'], 'Non-Color')
    me.materials.clear()
    for name, reg in MATERIAL_SLOTS:
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        nt = mat.node_tree
        bsdf = nt.nodes['Principled BSDF']
        tc = nt.nodes.new('ShaderNodeTexImage'); tc.image = col; tc.location = (-700, 300)
        te = nt.nodes.new('ShaderNodeTexImage'); te.image = emi; te.location = (-700, 0)
        tr = nt.nodes.new('ShaderNodeTexImage'); tr.image = rou; tr.location = (-700, -300)
        tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = nor; tn.location = (-700, -600)
        nm = nt.nodes.new('ShaderNodeNormalMap'); nm.location = (-350, -600); nm.inputs['Strength'].default_value = 0.8
        mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.location = (-350, 0)
        glow = SLOT_EMISSION.get(name, emission_strength)
        mul.inputs[1].default_value = glow
        nt.links.new(tc.outputs['Color'], bsdf.inputs['Base Color'])
        nt.links.new(tc.outputs['Color'], bsdf.inputs['Emission Color'])
        nt.links.new(te.outputs['Color'], mul.inputs[0])
        nt.links.new(mul.outputs['Value'], bsdf.inputs['Emission Strength'])
        nt.links.new(tr.outputs['Color'], bsdf.inputs['Roughness'])
        nt.links.new(tn.outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
        bsdf.inputs['Metallic'].default_value = 0.0
        if name in SLOT_EMISSION:
            # preview-only glow pass (render_views adds it as a soft bloom); Roblox
            # gets the same look from EmissiveMaskContent + Lighting.Bloom
            gm = nt.nodes.new('ShaderNodeMixRGB'); gm.blend_type = 'MULTIPLY'; gm.location = (-350, 250)
            gm.inputs['Fac'].default_value = 1.0
            nt.links.new(tc.outputs['Color'], gm.inputs['Color1'])
            nt.links.new(te.outputs['Color'], gm.inputs['Color2'])
            aov = nt.nodes.new('ShaderNodeOutputAOV'); aov.aov_name = 'glow'; aov.location = (0, 400)
            nt.links.new(gm.outputs['Color'], aov.inputs['Color'])
        mat['roblox_slot_region'] = reg
        me.materials.append(mat)
    reg_to_slot = {reg: i for i, (_, reg) in enumerate(MATERIAL_SLOTS)}
    idx = np.array([reg_to_slot[int(r)] for r in face_reg], dtype=np.int32)
    me.polygons.foreach_set('material_index', idx)
    me.update()


# ============================================================ entry
def parse_args():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(HERE, '..'))
    ap.add_argument('--stage', default='all', choices=['model', 'all'])
    ap.add_argument('--no-render', action='store_true')
    return ap.parse_args(argv)


def main():
    args = parse_args()
    out = os.path.abspath(args.out)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'
    sc.unit_settings.scale_length = 0.01          # Roblox: 1 Blender unit = 1 stud with FBX Units Scale
    sc.render.fps = FPS

    md_body, md_acc, lofts = kg.build_kitsune()
    kg.add_claws(md_acc, lofts['toe_tips'])
    # budget: body gets whatever the accessories (+ eyes) leave under the limit
    body_target = TRI_BUDGET - md_acc.tri_count() - 2 * ks.EYE_TRIS
    body = ks.build_sculpted_body(md_body, lofts, WORLD_SCALE, body_target)
    ks.scale_uv_islands(body, UV_IMPORTANCE, WORLD_SCALE)
    print('HUG seated accessory pieces', ks.hug_accessories(md_acc, body, WORLD_SCALE))
    lofts['eye_frames'] = ks.add_eyes(md_acc, lofts, body, WORLD_SCALE)
    acc = build_mesh(md_acc, 'Kitsune_Acc')
    ob = join_objects([body, acc], 'Kitsune')
    ntri = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    print('KITSUNE tris', ntri, 'verts', len(ob.data.vertices), '(body', body_target, 'target)')
    md = None
    pack_uvs(ob)
    paths, face_reg = paint_textures(ob, lofts, os.path.join(out, 'Textures'))
    make_materials(ob, paths, face_reg)
    if args.stage == 'model':
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, '_model_stage.blend'))
        return ob, md, lofts, out
    import kitsune_rig as kr
    arm = kr.build_rig(ob, md)
    kr.build_actions(arm, ob)
    kr.finalize_and_export(arm, ob, out, md)
    return ob, md, lofts, out


if __name__ == '__main__':
    main()
