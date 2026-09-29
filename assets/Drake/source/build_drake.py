"""Build the Stud Drake: mesh -> UV -> stud texture -> rig/weights -> idle/walk -> .blend + Roblox FBX.

Run:  python3 build_drake.py            (uses the `bpy` module; Blender 4.2)
  or: blender -b -P build_drake.py
Outputs go to ../ (assets/Drake/).
"""
import sys, os, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy, bmesh
import numpy as np
from mathutils import Vector, Quaternion, Matrix
from PIL import Image, ImageDraw
import drake_geo as G

OUT = os.path.abspath(os.path.join(HERE, '..'))
TEX_DIR = os.path.join(OUT, 'textures')
os.makedirs(TEX_DIR, exist_ok=True)

TEX_RES = 1024            # Roblox max texture size
STUD_SHADE = 0.15          # baked stud bevel contrast
STUD_AO = 0.06             # stud contact-shadow strength
STUD_NORMAL_SCALE = 0.44   # normal-map bevel depth (1.0 = source maps)
STUD_PITCH = 0.22         # metres between studs (reference body ~5 studs tall)
FPS = 30


# ------------------------------------------------------------------ mesh
def make_mesh(mb):
    me = bpy.data.meshes.new('Drake')
    me.from_pydata([tuple(v) for v in mb.v], [], mb.f)
    me.update()
    ob = bpy.data.objects.new('Drake', me)
    bpy.context.scene.collection.objects.link(ob)
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.faces.ensure_lookup_table()
    for i, fix in enumerate(mb.fix):
        if fix is not None and bm.faces[i].normal.dot(fix) < 0:
            bm.faces[i].normal_flip()
    bm.to_mesh(me); bm.free()
    attr = me.attributes.new('pal', 'INT', 'FACE')
    attr.data.foreach_set('value', list(mb.fc))
    for p in me.polygons:
        p.use_smooth = False
    return ob


SWATCH_V = 0.985   # top strip of the atlas holds flat palette swatches for hidden faces


def mirror_pairs(mb):
    """Pair every -X face with its +X twin so both halves can share texture space.
    Colours are made symmetric (left copies right)."""
    def key(f, sx):
        return tuple(sorted((round(sx * mb.v[i].x, 4), round(mb.v[i].y, 4), round(mb.v[i].z, 4)) for i in f))
    table = {}
    for fi, f in enumerate(mb.f):
        cx = sum(mb.v[i].x for i in f) / len(f)
        if cx > 1e-3:
            table[key(f, 1)] = fi
    pairs = {}
    for fi, f in enumerate(mb.f):
        cx = sum(mb.v[i].x for i in f) / len(f)
        if cx < -1e-3:
            j = table.get(key(f, -1))
            if j is not None and len(mb.f[j]) == len(f):
                pairs[fi] = j
                mb.fc[fi] = mb.fc[j]
    return pairs


def unwrap(ob, mb, pairs):
    me = ob.data
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(me)
    bm.faces.ensure_lookup_table()
    for f in bm.faces:
        f.select_set(f.index not in pairs and not mb.part[f.index].endswith('_hidden'))
    bmesh.update_edit_mesh(me)
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.003, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.pack_islands(rotate=True, margin=0.003, shape_method='CONCAVE')
    bpy.ops.object.mode_set(mode='OBJECT')
    uv = me.uv_layers.active.data
    # squeeze packed islands below the swatch strip
    for p in me.polygons:
        if p.index in pairs or mb.part[p.index].endswith('_hidden'):
            continue
        for li in p.loop_indices:
            u, v = uv[li].uv
            uv[li].uv = (u, v * SWATCH_V)
    # mirrored faces copy their twin's UVs vertex-for-vertex
    for fi, j in pairs.items():
        pj = me.polygons[j]
        lut = {}
        for li in pj.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            lut[(round(co.x, 4), round(co.y, 4), round(co.z, 4))] = tuple(uv[li].uv)
        for li in me.polygons[fi].loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uv[li].uv = lut[(round(-co.x, 4), round(co.y, 4), round(co.z, 4))]
    # hidden faces collapse onto their colour swatch
    n = len(G.PAL_NAMES)
    for p in me.polygons:
        if mb.part[p.index].endswith('_hidden') and p.index not in pairs:
            c = mb.fc[p.index]
            for li in p.loop_indices:
                uv[li].uv = ((c + 0.5) / n, (SWATCH_V + 1) * 0.5)


def face_uv_polys(me):
    uv = me.uv_layers.active.data
    polys = []
    for p in me.polygons:
        polys.append([tuple(uv[li].uv) for li in p.loop_indices])
    return polys


def uv_density(me, polys, mb):
    a3 = 0.0; a2 = 0.0
    for p, uvp in zip(me.polygons, polys):
        if mb.part[p.index].endswith('_hidden'):
            continue
        a3 += p.area
        pts = np.array(uvp)
        x, y = pts[:, 0], pts[:, 1]
        a2 += 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))
    return math.sqrt(a2 / a3)   # uv units per metre


# ------------------------------------------------------------------ texture
def bake_textures(ob, mb):
    me = ob.data
    polys = face_uv_polys(me)
    dens = uv_density(me, polys, mb)
    R = TEX_RES
    ss = 2  # supersample the colour raster
    img = Image.new('RGB', (R * ss, R * ss), (0, 0, 0))
    mask = Image.new('L', (R * ss, R * ss), 0)
    flat = Image.new('L', (R * ss, R * ss), 0)       # 1 = no studs (eyes)
    groove = Image.new('L', (R * ss, R * ss), 0)
    d = ImageDraw.Draw(img); dm = ImageDraw.Draw(mask); df = ImageDraw.Draw(flat); dg = ImageDraw.Draw(groove)
    pal = [G.PALETTE[n] for n in G.PAL_NAMES]
    nsw = len(G.PAL_NAMES)
    for c in range(nsw):
        box_ = [c / nsw * R * ss, 0, (c + 1) / nsw * R * ss, (1 - SWATCH_V) * R * ss]
        d.rectangle(box_, fill=pal[c]); dm.rectangle(box_, fill=255); df.rectangle(box_, fill=255)
    for i, uvp in enumerate(polys):
        if mb.part[i].endswith('_hidden'):
            continue
        pts = [(u * R * ss, (1 - v) * R * ss) for u, v in uvp]
        col = pal[mb.fc[i]]
        d.polygon(pts, fill=col, outline=col)
        dm.polygon(pts, fill=255, outline=255)
        if mb.part[i] == 'eye':
            df.polygon(pts, fill=255, outline=255)
        if mb.part[i] in ('body', 'head', 'jaw', 'brick'):
            dg.line(pts + [pts[0]], fill=255, width=2)
    import cv2
    colp = cv2.resize(np.array(img).astype(np.float32) / 255.0, (R, R), interpolation=cv2.INTER_AREA)
    alpha = cv2.resize(np.array(mask).astype(np.float32) / 255.0, (R, R), interpolation=cv2.INTER_AREA)
    flat = cv2.resize(np.array(flat).astype(np.float32) / 255.0, (R, R), interpolation=cv2.INTER_AREA)
    groove = cv2.resize(np.array(groove).astype(np.float32) / 255.0, (R, R), interpolation=cv2.INTER_AREA)
    # un-premultiply the anti-aliased island borders (black background must not leak in)
    m = alpha > 0.02
    col = np.zeros_like(colp)
    col[m] = colp[m] / alpha[m][:, None]
    col = np.clip(col, 0, 1)
    # bleed island colours outward (padding for mip-maps)
    k = np.ones((3, 3), np.uint8)
    for _ in range(32):
        grown = cv2.dilate(m.astype(np.uint8), k).astype(bool)
        new = grown & ~m
        if not new.any():
            break
        ssum = cv2.blur(col * m[..., None], (3, 3))
        cnt = cv2.blur(m.astype(np.float32), (3, 3))
        fill = ssum / np.maximum(cnt[..., None], 1e-6)
        col[new] = fill[new]
        m = grown

    # stud pattern: tile the HD stud maps in UV space at STUD_PITCH world spacing
    ao_src = np.array(Image.open(os.path.join(HERE, 'studs', 'studs_2x2_ao.png')).convert('L')).astype(np.float32) / 255.0
    nm_src = np.array(Image.open(os.path.join(HERE, 'studs', 'studs_2x2_normal.png')).convert('RGB')).astype(np.float32) / 255.0
    tile_px = 2 * STUD_PITCH * dens * R          # 2x2 source tile covers two studs
    print(f'uv density {dens:.4f} uv/m, stud tile {tile_px:.1f}px -> {tile_px / 2:.1f}px per stud')
    ys, xs = np.mgrid[0:R, 0:R].astype(np.float32)
    sx = ((xs / tile_px) % 1.0) * ao_src.shape[1]
    sy = ((ys / tile_px) % 1.0) * ao_src.shape[0]
    ao = cv2.remap(ao_src, sx, sy, cv2.INTER_AREA if tile_px < 256 else cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
    # pre-shrink source to avoid aliasing
    scale = max(1, int(ao_src.shape[0] / max(tile_px, 1)))
    if scale > 1:
        ao_small = cv2.resize(ao_src, (int(ao_src.shape[1] / scale), int(ao_src.shape[0] / scale)), interpolation=cv2.INTER_AREA)
        nm_small = cv2.resize(nm_src, (int(nm_src.shape[1] / scale), int(nm_src.shape[0] / scale)), interpolation=cv2.INTER_AREA)
    else:
        ao_small, nm_small = ao_src, nm_src
    sx = ((xs / tile_px) % 1.0) * ao_small.shape[1]
    sy = ((ys / tile_px) % 1.0) * ao_small.shape[0]
    ao = cv2.remap(ao_small, sx, sy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
    nm = cv2.remap(nm_small, sx, sy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
    ao = ao * (1 - flat) + flat
    nvec = nm * 2 - 1
    nvec[..., :2] *= STUD_NORMAL_SCALE            # shallower bevels = subtler studs
    nvec /= np.linalg.norm(nvec, axis=2, keepdims=True)
    nvec = nvec * (1 - flat[..., None]) + np.array([0, 0, 1], np.float32) * flat[..., None]
    # baked bevel lighting (top-left key) so studs read even without a normal map
    light = np.array([-0.45, 0.55, 0.70]); light /= np.linalg.norm(light)
    lam = np.clip((nvec @ light.astype(np.float32)), 0, 1)
    lam0 = float(np.array([0, 0, 1]) @ light)
    shade = 1.0 + STUD_SHADE * (lam - lam0)
    shade *= (1.0 - STUD_AO + STUD_AO * ao ** 1.5)            # AO contact shadow round the studs
    shade *= (1.0 - 0.28 * groove)                # brick seams
    final = np.clip(col * shade[..., None], 0, 1)
    Image.fromarray((final * 255).astype(np.uint8)).save(os.path.join(TEX_DIR, 'Drake_Color.png'))
    Image.fromarray((col * 255).astype(np.uint8)).save(os.path.join(TEX_DIR, 'Drake_FlatColor.png'))
    nvec[..., 2] = np.clip(nvec[..., 2], 0.05, 1)
    nvec /= np.linalg.norm(nvec, axis=2, keepdims=True)
    Image.fromarray(((nvec * 0.5 + 0.5) * 255).astype(np.uint8)).save(os.path.join(TEX_DIR, 'Drake_Normal.png'))
    rough = np.full((R, R), 0.42, np.float32)
    Image.fromarray((rough * 255).astype(np.uint8)).save(os.path.join(TEX_DIR, 'Drake_Roughness.png'))
    em = cv2.dilate((flat > 0.5).astype(np.uint8) * 255, k)
    Image.fromarray(em).save(os.path.join(TEX_DIR, 'Drake_EyeGlowMask.png'))


def make_material(ob):
    mat = bpy.data.materials.new('M_Drake')
    mat.use_nodes = True
    nt = mat.node_tree
    bs = nt.nodes['Principled BSDF']
    def tex(name, cs, loc):
        n = nt.nodes.new('ShaderNodeTexImage')
        n.image = bpy.data.images.load(os.path.join(TEX_DIR, name))
        n.image.colorspace_settings.name = cs
        n.location = loc
        n.interpolation = 'Linear'
        return n
    c = tex('Drake_Color.png', 'sRGB', (-600, 300))
    nt.links.new(c.outputs['Color'], bs.inputs['Base Color'])
    n = tex('Drake_Normal.png', 'Non-Color', (-600, -200))
    nm = nt.nodes.new('ShaderNodeNormalMap'); nm.location = (-300, -200)
    nt.links.new(n.outputs['Color'], nm.inputs['Color'])
    nt.links.new(nm.outputs['Normal'], bs.inputs['Normal'])
    bs.inputs['Roughness'].default_value = 0.42
    bs.inputs['Specular IOR Level'].default_value = 0.45
    e = tex('Drake_EyeGlowMask.png', 'Non-Color', (-600, 0))
    nt.links.new(c.outputs['Color'], bs.inputs['Emission Color'])
    mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = 1.2
    nt.links.new(e.outputs['Color'], mul.inputs[0])
    nt.links.new(mul.outputs[0], bs.inputs['Emission Strength'])
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    return mat


# ------------------------------------------------------------------ rig
def build_armature():
    arm = bpy.data.armatures.new('DrakeRig')
    arm.display_type = 'STICK'
    ao = bpy.data.objects.new('DrakeRig', arm)
    bpy.context.scene.collection.objects.link(ao)
    bpy.context.view_layer.objects.active = ao
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.edit_bones

    def add(name, head, tail, parent=None, connect=False):
        b = eb.new(name)
        b.head = Vector(head); b.tail = Vector(tail); b.roll = 0.0
        if parent:
            b.parent = eb[parent]; b.use_connect = connect
        return b

    s_root = 0.45
    add('Root', (0, G.Y(s_root), 0), (0, G.Y(s_root) - 0.6, 0))
    sp = G.spine_point
    add('Spine1', sp(0.45), sp(0.37), 'Root')
    add('Spine2', sp(0.37), sp(0.29), 'Spine1', True)
    add('Neck1', sp(0.29), sp(0.21), 'Spine2', True)
    add('Neck2', sp(0.21), G.HEAD_ORIGIN, 'Neck1', True)
    add('Head', G.HEAD_ORIGIN, G.H(0, 1.0, 0.0), 'Neck2', True)
    add('Jaw', G.H(0, -0.05, -0.12), G.JH(0, 0.95, -0.25), 'Head')
    add('Spine3', sp(0.45), sp(0.53), 'Root')
    prev = 'Spine3'
    for n, a, b in G.SPINE_BONES:
        if n in ('Spine1', 'Spine2', 'Neck1', 'Neck2', 'Spine3'):
            continue
        add(n, sp(a), sp(b), prev, True)
        prev = n
    for i, (s, k) in enumerate(G.SIDE):
        c = sp(s); t, up = G.spine_frame(s)
        par = max(G.spine_weights(s).items(), key=lambda kv: kv[1])[0]
        for sgn, side in ((1, 'L'), (-1, 'R')):
            X = Vector((sgn, 0, 0))
            base = c + X * (G.HW(s) * 0.85) - up * (G.HH(s) * 0.25)
            add(f'Fin{side}{i + 1}', base, base + (X * 0.8 - up * 0.4).normalized() * 0.45 * k, par)
    bpy.ops.object.mode_set(mode='OBJECT')
    return ao


def skin(ob, ao, mb):
    names = {n for w in mb.w for n in w}
    for n in names:
        ob.vertex_groups.new(name=n)
    for vi, w in enumerate(mb.w):
        tot = sum(w.values())
        for n, val in w.items():
            ob.vertex_groups[n].add([vi], val / tot, 'REPLACE')
    ob.parent = ao
    mod = ob.modifiers.new('Armature', 'ARMATURE')
    mod.object = ao


# ------------------------------------------------------------------ animation
FRONT = ['Spine1', 'Spine2', 'Neck1', 'Neck2', 'Head']
BACK = ['Spine3', 'Spine4', 'Tail1', 'Tail2', 'Tail3', 'Tail4', 'Tail5']
BONE_S = {'Spine1': 0.41, 'Spine2': 0.33, 'Neck1': 0.25, 'Neck2': 0.17, 'Head': 0.06,
          'Spine3': 0.49, 'Spine4': 0.57, 'Tail1': 0.65, 'Tail2': 0.73, 'Tail3': 0.80, 'Tail4': 0.87, 'Tail5': 0.93}

# base "display" pose (matches the reference 3/4 hero pose): neck reared up, head level, tail lifted
# values: (lift, yaw) in degrees; lift>0 raises the part further from the root, yaw>0 bends to +X
BASE_POSE = {
    'Spine1': (5, 5), 'Spine2': (14, 4), 'Neck1': (26, -3), 'Neck2': (8, -4), 'Head': (-44, -2),
    'Spine3': (0, -10), 'Spine4': (2, -8), 'Tail1': (4, 6), 'Tail2': (12, 10), 'Tail3': (22, 8), 'Tail4': (28, 4),
    'Tail5': (24, 0),
}


def world_rot(pb, lift_deg, yaw_deg, roll_deg=0.0):
    """Rotation for a chain bone given in body terms, converted to bone-local."""
    b = pb.bone
    R = b.matrix_local.to_3x3()
    Ri = R.inverted()
    front = b.name in FRONT or b.name == 'Jaw'
    # lift: rotate about world X. front chain points -Y, so raising needs a negative X rotation
    lx = math.radians(-lift_deg if front else lift_deg)
    yz = math.radians(-yaw_deg if front else yaw_deg)
    q = Quaternion(Ri @ Vector((0, 0, 1)), yz) @ Quaternion(Ri @ Vector((1, 0, 0)), lx)
    if roll_deg:
        q = Quaternion(Vector((0, 1, 0)), math.radians(roll_deg)) @ q
    return q


def key_pose(ao, frame, pose, loc=None):
    for name, (lift, yaw, *rest) in pose.items():
        pb = ao.pose.bones[name]
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = world_rot(pb, lift, yaw, rest[0] if rest else 0.0)
        pb.keyframe_insert('rotation_quaternion', frame=frame, group=name)
    if loc is not None:
        pb = ao.pose.bones['Root']
        pb.location = loc
        pb.keyframe_insert('location', frame=frame, group='Root')


def fin_rot(pb, swing_deg, flap_deg):
    """swing: rotate fin forward/back about world Z; flap: up/down about body axis (world Y)."""
    Ri = pb.bone.matrix_local.to_3x3().inverted()
    sgn = 1 if pb.name.startswith('FinL') else -1
    return (Quaternion(Ri @ Vector((0, 0, 1)), math.radians(swing_deg * sgn)) @
            Quaternion(Ri @ Vector((0, 1, 0)), math.radians(flap_deg * sgn)))


def make_action(ao, name, frames, fn):
    ao.animation_data_create()
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    ao.animation_data.action = act
    for f in range(0, frames + 1, 2):
        pose, loc, fins, jaw = fn(f / frames)
        key_pose(ao, f, pose, loc)
        for fname, (sw, fl) in fins.items():
            pb = ao.pose.bones[fname]; pb.rotation_mode = 'QUATERNION'
            pb.rotation_quaternion = fin_rot(pb, sw, fl)
            pb.keyframe_insert('rotation_quaternion', frame=f, group=fname)
        pb = ao.pose.bones['Jaw']; pb.rotation_mode = 'QUATERNION'
        Ri = pb.bone.matrix_local.to_3x3().inverted()
        pb.rotation_quaternion = Quaternion(Ri @ Vector((1, 0, 0)), math.radians(jaw))
        pb.keyframe_insert('rotation_quaternion', frame=f, group='Jaw')
    for fc in act.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'BEZIER'
            kp.handle_left_type = kp.handle_right_type = 'AUTO_CLAMPED'
    act.frame_range = (0, frames)
    return act


FIN_NAMES = [f'Fin{s}{i}' for s in 'LR' for i in range(1, 5)]
TAU = 2 * math.pi


def idle_fn(t):
    """4 s breathing / looking idle, loops seamlessly."""
    br = math.sin(TAU * t)                 # 1 breath per loop
    br2 = math.sin(TAU * 2 * t)
    pose = {}
    for n, (lift, yaw) in BASE_POSE.items():
        s = BONE_S[n]
        sway = math.sin(TAU * t - s * 5.0)
        if n in FRONT:
            pose[n] = (lift + 2.0 * br * (1 if n != 'Head' else -1.2), yaw + 3.0 * math.sin(TAU * t + 0.8) * (1.6 if n == 'Head' else 0.6))
        else:
            k = (s - 0.45) / 0.5
            pose[n] = (lift + 3.0 * k * math.sin(TAU * t - s * 4.0), yaw + 7.0 * k * sway)
    fins = {}
    for fname in FIN_NAMES:
        i = int(fname[-1])
        fins[fname] = (4.0 * math.sin(TAU * 2 * t - i * 0.7), 6.0 * math.sin(TAU * 2 * t - i * 0.7 + 1.0))
    jaw = -5.0 * (0.5 + 0.5 * br2)        # jaw opens/closes a little (negative = close)
    loc = Vector((0, 0, 0.015 * br))
    return pose, loc, fins, jaw


def walk_fn(t):
    """1.6 s serpentine slither/crawl: lateral travelling wave + alternating flipper strokes."""
    pose = {}
    front_sum = 0.0
    for n, (lift, yaw) in BASE_POSE.items():
        s = BONE_S[n]
        ph = TAU * t - TAU * 1.25 * s
        if n in FRONT:
            if n == 'Head':
                continue
            amp = {'Spine1': 9, 'Spine2': 8, 'Neck1': 6, 'Neck2': 3}[n]
            y = amp * math.sin(ph)
            front_sum += y
            pose[n] = (lift + 1.5 * math.sin(2 * ph), y)
        else:
            amp = {'Spine3': 10, 'Spine4': 12, 'Tail1': 14, 'Tail2': 15, 'Tail3': 16, 'Tail4': 16, 'Tail5': 16}[n]
            pose[n] = (lift + 2.0 * math.sin(2 * ph), amp * math.sin(ph))
    pose['Head'] = (BASE_POSE['Head'][0] - 1.5 * math.sin(TAU * 2 * t), -0.85 * front_sum)
    fins = {}
    for fname in FIN_NAMES:
        i = int(fname[-1]); side = 1 if fname[3] == 'L' else -1
        ph = TAU * t - TAU * 1.25 * G.SIDE[i - 1][0] + (0 if side > 0 else math.pi)
        fins[fname] = (28.0 * math.sin(ph), 14.0 * math.cos(ph))
    jaw = -3.0 * (0.5 + 0.5 * math.sin(TAU * 2 * t))
    loc = Vector((0, 0, 0.03 * abs(math.sin(TAU * t))))
    return pose, loc, fins, jaw


# ------------------------------------------------------------------ export
def export_fbx(path, ao, ob, action=None):
    bpy.ops.object.select_all(action='DESELECT')
    ao.select_set(True); ob.select_set(True)
    bpy.context.view_layer.objects.active = ao
    if action is not None:
        ao.animation_data.action = action
        bpy.context.scene.frame_start, bpy.context.scene.frame_end = int(action.frame_range[0]), int(action.frame_range[1])
    else:
        ao.animation_data.action = None
        for pb in ao.pose.bones:
            pb.rotation_quaternion = Quaternion(); pb.location = Vector()
    bpy.ops.export_scene.fbx(
        filepath=path, use_selection=True, object_types={'ARMATURE', 'MESH'},
        apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS', bake_space_transform=False,
        axis_forward='-Z', axis_up='Y', use_mesh_modifiers=False, mesh_smooth_type='FACE',
        use_tspace=True, add_leaf_bones=False, primary_bone_axis='Y', secondary_bone_axis='X',
        use_armature_deform_only=False, armature_nodetype='NULL',
        bake_anim=action is not None, bake_anim_use_all_bones=True, bake_anim_use_nla_strips=False,
        bake_anim_use_all_actions=False, bake_anim_force_startend_keying=True, bake_anim_step=1.0,
        bake_anim_simplify_factor=0.0, path_mode='COPY', embed_textures=True)
    print('exported', path, os.path.getsize(path))


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = FPS
    mb = G.build_all()
    global PAIRS
    PAIRS = mirror_pairs(mb)
    print('mirrored faces sharing UV space:', len(PAIRS), 'of', len(mb.f))
    ob = make_mesh(mb)
    tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    print('TRIS', tris, 'VERTS', len(ob.data.vertices))
    assert tris < 5000
    unwrap(ob, mb, PAIRS)
    bake_textures(ob, mb)
    make_material(ob)
    ao = build_armature()
    skin(ob, ao, mb)
    idle = make_action(ao, 'Drake_Idle', 120, idle_fn)
    walk = make_action(ao, 'Drake_Walk', 48, walk_fn)
    # NLA strips so both clips live in the .blend
    for act in (idle, walk):
        tr = ao.animation_data.nla_tracks.new(); tr.name = act.name
        st = tr.strips.new(act.name, 0, act); st.mute = True
    ao.animation_data.action = idle
    sc.frame_start, sc.frame_end = 0, 120
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'Drake.blend'))
    for nt in ao.animation_data.nla_tracks:
        nt.mute = True
    export_fbx(os.path.join(OUT, 'Drake_Idle.fbx'), ao, ob, idle)
    export_fbx(os.path.join(OUT, 'Drake_Walk.fbx'), ao, ob, walk)
    export_fbx(os.path.join(OUT, 'Drake.fbx'), ao, ob, None)
    print('DONE')


if __name__ == '__main__':
    main()
