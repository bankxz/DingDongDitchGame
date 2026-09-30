"""
Sculpt pipeline for the organic body.

  1. closed source forms (torso, neck, head, ears, legs, toe paws)  ->  one mesh
  2. voxel REMESH (fuses neck/head, legs/body, toes/pads into one surface)
  3. smoothing (fillets at the joins, removes voxel steps)
  4. SCULPT: flow-aligned fur locks displaced along the normals
     (kitsune_fur.lock_field), eye sockets and brow ridges
  5. DECIMATE to the triangle budget
  6. transfer part / loft params (t, th) / skin weights from the source forms
     so the texture painter and the rig keep working
  7. UV unwrap (smart project, per-island texel density)
"""
import math
import numpy as np
import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import kitsune_geo as kg
import kitsune_fur as kf

INV_PART = {v: k for k, v in kg.PART_IDS.items()}


# ---------------------------------------------------------------- source
class Source:
    """Triangulated source forms with per-corner loft params and weights."""

    def __init__(self, md, S):
        self.S = S
        self.V = np.array(md.verts) * S
        tris, tf, tc = [], [], []
        for fi, f in enumerate(md.faces):
            for j in range(1, len(f) - 1):
                tris.append((f[0], f[j], f[j + 1]))
                tf.append(fi)
                tc.append((0, j, j + 1))
        self.tris = np.array(tris)
        self.tri_face = np.array(tf)
        self.tri_t = np.array([[md.face_at[fi][c][0] for c in cs] for fi, cs in zip(tf, tc)])
        self.tri_th = np.array([[md.face_at[fi][c][1] for c in cs] for fi, cs in zip(tf, tc)])
        self.tri_part = np.array(md.face_part)[self.tri_face]
        self.weights = md.weights
        vlist = [tuple(v) for v in self.V]
        self.bvh = BVHTree.FromPolygons(vlist, [tuple(t) for t in self.tris])
        self.part_bvh = {}
        for p in np.unique(self.tri_part):
            idx = np.where(self.tri_part == p)[0]
            self.part_bvh[int(p)] = (BVHTree.FromPolygons(vlist, [tuple(t) for t in self.tris[idx]]), idx)

    def nearest(self, pts, part=None):
        """-> (tri indices, barycentric (N,3))"""
        if part is None:
            bvh, remap = self.bvh, None
        else:
            bvh, remap = self.part_bvh[int(part)]
        idx = np.zeros(len(pts), dtype=np.int64)
        loc = np.zeros((len(pts), 3))
        for i, p in enumerate(pts):
            r = bvh.find_nearest(Vector(p))
            loc[i] = r[0]
            idx[i] = r[2] if remap is None else remap[r[2]]
        A, B, C = (self.V[self.tris[idx, k]] for k in range(3))
        v0, v1, v2 = B - A, C - A, loc - A
        d00 = (v0 * v0).sum(1); d01 = (v0 * v1).sum(1); d11 = (v1 * v1).sum(1)
        d20 = (v2 * v0).sum(1); d21 = (v2 * v1).sum(1)
        den = np.where(np.abs(d00 * d11 - d01 * d01) < 1e-18, 1e-18, d00 * d11 - d01 * d01)
        bv = (d11 * d20 - d01 * d21) / den
        bw = (d00 * d21 - d01 * d20) / den
        bu = 1 - bv - bw
        bary = np.clip(np.stack([bu, bv, bw], 1), 0, 1)
        bary /= np.maximum(bary.sum(1, keepdims=True), 1e-9)
        return idx, bary

    def params(self, idx, bary):
        t = (self.tri_t[idx] * bary).sum(1)
        th = (self.tri_th[idx] * bary).sum(1)
        return self.tri_part[idx], t, th

    def blend_weights(self, idx, bary):
        out = []
        for ti, b in zip(idx, bary):
            w = {}
            for k in range(3):
                for bone, val in self.weights[self.tris[ti, k]].items():
                    w[bone] = w.get(bone, 0.0) + val * b[k]
            items = sorted(w.items(), key=lambda kv: -kv[1])[:4]
            tot = sum(v for _, v in items) or 1.0
            out.append({k: v / tot for k, v in items if v > 1e-4})
        return out


# ---------------------------------------------------------------- helpers
def mesh_arrays(me):
    co = np.zeros(len(me.vertices) * 3); me.vertices.foreach_get('co', co)
    nr = np.zeros(len(me.vertices) * 3); me.vertices.foreach_get('normal', nr)
    return co.reshape(-1, 3), nr.reshape(-1, 3)


def evaluated_copy(ob, name):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    me.name = name
    return me


def link(me, name):
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def eye_sculpt(co_unit, part, head):
    """Eye sockets + brow ridges (unit-space displacement for head vertices)."""
    d_all = np.zeros(len(co_unit))
    hm = part == kg.PART_IDS['head']
    for sx in (1, -1):
        p, n, along, acr = kg.eye_frame(head, sx)
        d = np.linalg.norm(co_unit - p, axis=1)
        sock = -0.020 * np.clip(1 - (d / 0.090) ** 2, 0, 1) ** 1.5
        B = p + acr * 0.058 + along * 0.02 + n * 0.0
        db = np.linalg.norm(co_unit - B, axis=1)
        brow = 0.016 * np.clip(1 - db / 0.060, 0, 1) ** 2
        d_all += (sock + brow) * hm
    return d_all


# ---------------------------------------------------------------- main
def build_sculpted_body(md, info, S, target_tris, voxel=0.0085, smooth_iters=5, log=print):
    src = Source(md, S)
    me0 = bpy.data.meshes.new('KS_source')
    me0.from_pydata([tuple(v) for v in src.V], [], md.faces)
    me0.update()
    ob0 = link(me0, 'KS_source')

    # 2-3 voxel remesh + smoothing
    rm = ob0.modifiers.new('Remesh', 'REMESH')
    rm.mode = 'VOXEL'
    rm.voxel_size = voxel * S
    rm.adaptivity = 0.0
    sm = ob0.modifiers.new('Smooth', 'SMOOTH')
    sm.factor = 0.6
    sm.iterations = smooth_iters
    me1 = evaluated_copy(ob0, 'KS_remeshed')
    log('SCULPT remeshed verts', len(me1.vertices), 'faces', len(me1.polygons))

    # 4 sculpt: fur locks + eye sockets along the normals
    co, nr = mesh_arrays(me1)
    idx, bary = src.nearest(co)
    part, t, th = src.params(idx, bary)
    disp = np.zeros(len(co))
    for p in np.unique(part):
        m = part == p
        name = INV_PART[int(p)]
        disp[m] = kf.sculpt_height(name, t[m], th[m])
    disp += eye_sculpt(co / S, part, info['head'])
    co2 = co + nr * (disp[:, None] * S)
    me1.vertices.foreach_set('co', co2.ravel())
    me1.update()
    ob1 = link(me1, 'KS_sculpted')

    # 5 decimate to budget
    cur = sum(len(p.vertices) - 2 for p in me1.polygons)
    dec = ob1.modifiers.new('Decimate', 'DECIMATE')
    dec.decimate_type = 'COLLAPSE'
    dec.ratio = min(1.0, target_tris / cur)
    dec.use_collapse_triangulate = True
    me2 = evaluated_copy(ob1, 'Kitsune_Body')
    log('SCULPT decimated tris', sum(len(p.vertices) - 2 for p in me2.polygons), 'from', cur)
    for o in (ob0, ob1):
        bpy.data.objects.remove(o)

    # 6 transfer params / weights
    co, nr = mesh_arrays(me2)
    nf = len(me2.polygons)
    cen = np.zeros(nf * 3); me2.polygons.foreach_get('center', cen); cen = cen.reshape(-1, 3)
    fidx, fb = src.nearest(cen)
    fpart = src.tri_part[fidx]
    loops_v = np.zeros(len(me2.loops), dtype=np.int64); me2.loops.foreach_get('vertex_index', loops_v)
    lt = np.zeros(len(me2.loops)); lth = np.zeros(len(me2.loops))
    loop_face = np.zeros(len(me2.loops), dtype=np.int64)
    for poly in me2.polygons:
        loop_face[poly.loop_start:poly.loop_start + poly.loop_total] = poly.index
    lpart = fpart[loop_face]
    for p in np.unique(lpart):
        m = np.where(lpart == p)[0]
        i2, b2 = src.nearest(co[loops_v[m]], part=p)
        _, tt, tth = src.params(i2, b2)
        lt[m], lth[m] = tt, tth
    # unwrap th inside each face (relative to its first corner)
    for poly in me2.polygons:
        s0 = poly.loop_start
        ref = lth[s0]
        for li in range(s0 + 1, s0 + poly.loop_total):
            lth[li] = ref + ((lth[li] - ref + math.pi) % (2 * math.pi) - math.pi)
    vidx, vb = src.nearest(co)
    vweights = src.blend_weights(vidx, vb)
    _, _, vth = src.params(vidx, vb)

    for nm_, ty_, dom_ in (('k_t', 'FLOAT', 'CORNER'), ('k_th', 'FLOAT', 'CORNER'), ('k_len', 'FLOAT', 'CORNER'),
                           ('k_part', 'INT', 'FACE')):
        me2.attributes.new(nm_, ty_, dom_)
    me2.attributes['k_t'].data.foreach_set('value', lt)
    me2.attributes['k_th'].data.foreach_set('value', lth)
    me2.attributes['k_len'].data.foreach_set('value', np.zeros(len(me2.loops)))
    me2.attributes['k_part'].data.foreach_set('value', fpart.astype(np.int32))
    for p in me2.polygons:
        p.use_smooth = True
    ob = link(me2, 'Kitsune_Body')
    assign_groups(ob, vweights)

    # 7 UVs: one large island per part, cut only at part borders and along the
    # loft's underside seam (few seams, high atlas coverage, crisp texture)
    seam_unwrap(ob, fpart, vth)
    return ob


def assign_groups(ob, weights):
    groups = {}
    for vi, w in enumerate(weights):
        for bone, val in w.items():
            g = groups.get(bone) or ob.vertex_groups.new(name=bone)
            groups[bone] = g
            g.add([vi], float(val), 'REPLACE')


def seam_unwrap(ob, fpart, vth):
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    nseam = 0
    for e in bm.edges:
        lf = e.link_faces
        seam = len(lf) != 2
        if not seam and fpart[lf[0].index] != fpart[lf[1].index]:
            seam = True
        if not seam:
            a, b = e.verts
            if abs(vth[a.index] - vth[b.index]) > math.pi:          # wrap of the loft angle
                seam = True
        e.seam = seam
        nseam += seam
    bm.to_mesh(me)
    bm.free()
    if not me.uv_layers:
        me.uv_layers.new(name='UVMap')
    bpy.context.view_layer.objects.active = ob
    for o in bpy.context.view_layer.objects:
        o.select_set(o == ob)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.unwrap(method='ANGLE_BASED', fill_holes=True, margin=0.002)
    bpy.ops.object.mode_set(mode='OBJECT')
    me.uv_layers[0].name = 'UVMap'
    return nseam


def smart_uv(ob):
    bpy.context.view_layer.objects.active = ob
    for o in bpy.context.view_layer.objects:
        o.select_set(o == ob)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    if not ob.data.uv_layers:
        ob.data.uv_layers.new(name='UVMap')
    bpy.ops.uv.smart_project(angle_limit=math.radians(72), island_margin=0.002, area_weight=0.0)
    bpy.ops.object.mode_set(mode='OBJECT')
    ob.data.uv_layers[0].name = 'UVMap'


def scale_uv_islands(ob, importance, S=1.0, part_attr='k_part'):
    """Give every UV island the same texel density as the accessory islands
    (UV length == 3D length) times a per-part importance factor."""
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    uvl = bm.loops.layers.uv.active
    pl = bm.faces.layers.int.get(part_attr)
    bm.faces.ensure_lookup_table()
    # islands: faces connected through edges whose UVs agree on both sides
    parent = list(range(len(bm.faces)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for e in bm.edges:
        if len(e.link_faces) != 2:
            continue
        f1, f2 = e.link_faces
        ok = True
        for v in e.verts:
            u1 = [l[uvl].uv for l in f1.loops if l.vert == v][0]
            u2 = [l[uvl].uv for l in f2.loops if l.vert == v][0]
            if (u1 - u2).length > 1e-6:
                ok = False
        if ok:
            parent[find(f1.index)] = find(f2.index)
    islands = {}
    for f in bm.faces:
        islands.setdefault(find(f.index), []).append(f)
    print('UV body islands', len(islands))
    for faces in islands.values():
        a3 = sum(f.calc_area() for f in faces) / (S * S)        # unit-space area (matches accessory islands)
        auv = 0.0
        acc = {}
        cu = Vector((0, 0))
        n = 0
        for f in faces:
            uvs = [l[uvl].uv for l in f.loops]
            for j in range(1, len(uvs) - 1):
                e1, e2 = uvs[j] - uvs[0], uvs[j + 1] - uvs[0]
                auv += abs(e1.x * e2.y - e1.y * e2.x) * 0.5
            for u in uvs:
                cu += u; n += 1
            pn = INV_PART.get(f[pl], 'torso')
            acc[pn] = acc.get(pn, 0) + f.calc_area()
        dom = max(acc, key=acc.get)
        k = math.sqrt(a3 / max(auv, 1e-12)) * importance.get(dom, 1.0)
        cu /= max(n, 1)
        for f in faces:
            for l in f.loops:
                l[uvl].uv = (l[uvl].uv - cu) * k
    bm.to_mesh(me)
    bm.free()


def add_eyes(ma, info, body_ob, S):
    """Eyes seated flush in the sculpted sockets (projected onto the final
    surface), sharp almond outline, inner corner low toward the nose."""
    me = body_ob.data
    co = np.zeros(len(me.vertices) * 3); me.vertices.foreach_get('co', co)
    tris = []
    for p in me.polygons:
        vs = list(p.vertices)
        for j in range(1, len(vs) - 1):
            tris.append((vs[0], vs[j], vs[j + 1]))
    bvh = BVHTree.FromPolygons([tuple(v) for v in co.reshape(-1, 3)], tris)
    head = info['head']
    frames = {}
    for sx in (1, -1):
        p, n, along, acr = kg.eye_frame(head, sx)
        loc, sn, _, _ = bvh.find_nearest(Vector(p * S))
        c = np.array(loc) / S
        sn = np.array(sn)
        frames[sx] = (c, sn, along, acr)
        isl = ma.new_island('eye')
        first = len(ma.faces)
        K = 12
        rings = []
        # (scale of the almond outline, lift above the surface): the lens follows the
        # socket surface everywhere, so the head can never poke through it
        for sc_, lift in ((1.0, 0.004), (0.68, 0.008), (0.36, 0.010)):
            ring = []
            for k in range(K):
                a = kg.TAU * k / K
                ca_, sa_ = math.cos(a), math.sin(a)
                h = 0.030 * abs(sa_) ** 1.05 * (1.0 if sa_ > 0 else 0.62)
                q = c + (along * 0.058 * ca_ + acr * h * np.sign(sa_) - acr * 0.010 * max(0.0, -ca_)) * sc_
                l2, n2, _, _ = bvh.find_nearest(Vector(q * S))
                ring.append(ma.add_vert(np.array(l2) / S + np.array(n2) * lift, {'Head': 1.0}))
            rings.append((ring, sc_))
        l2, n2, _, _ = bvh.find_nearest(Vector(c * S))
        cvt = ma.add_vert(np.array(l2) / S + np.array(n2) * 0.011, {'Head': 1.0})
        uvp = lambda a, r: (.5 + .5 * r * math.cos(a), .5 + .5 * r * math.sin(a))
        for ri in range(len(rings) - 1):
            (ra, sa), (rb, sb) = rings[ri], rings[ri + 1]
            for k in range(K):
                k2 = (k + 1) % K
                a, b = kg.TAU * k / K, kg.TAU * k2 / K
                ma.add_face([ra[k], ra[k2], rb[k2], rb[k]], [uvp(a, sa), uvp(b, sa), uvp(b, sb), uvp(a, sb)],
                            [(sa, a), (sa, b), (sb, b), (sb, a)], 'eye', isl)
        rl, sl = rings[-1]
        for k in range(K):
            k2 = (k + 1) % K
            a, b = kg.TAU * k / K, kg.TAU * k2 / K
            ma.add_face([rl[k], rl[k2], cvt], [uvp(a, sl), uvp(b, sl), (.5, .5)], [(sl, a), (sl, b), (0, 0)], 'eye', isl)
        ma.orient_piece(first, c - sn * 0.05)
    return frames
