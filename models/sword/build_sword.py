"""Untextured 1:1 sword model built from the reference sheet silhouettes.
Front view (X/Z) is locked from the front silhouette contour; thickness (Y)
comes from the side-view profile. Run: python3 build_sword.py
"""
import bpy, bmesh, cv2, numpy as np, math, json, sys
from mathutils import Vector

REF = '/tmp/claude-0/-home-user-DingDongDitchGame/25723ca7-107e-59a5-b2ba-96635f274c48/scratchpad/ref/3.png'
OUT = '/home/user/DingDongDitchGame/models/sword/sword_model'
img = cv2.imread(REF, cv2.IMREAD_GRAYSCALE)
mask = (img < 235).astype(np.uint8)

FRONT = (40, 239)       # x range of front view
SIDE = (582, 639)       # x range of side view
Y0, Y1 = 11, 861        # sword top / bottom rows
H = Y1 - Y0
SCALE = 1.2 / H * 1.0   # sword ~ 1.2 m tall (blade+hilt+chain)... 1 px = SCALE m
CX = (FRONT[0] + FRONT[1]) / 2

# side thickness profile per row (px)
side_t = np.zeros(img.shape[0])
for y in range(Y0, Y1 + 1):
    xs = np.where(mask[y, SIDE[0]:SIDE[1]])[0]
    side_t[y] = (xs.max() - xs.min() + 1) if len(xs) else 1
# side centre-line offset (blade curve in profile)
side_c = np.zeros(img.shape[0])
sc0 = None
for y in range(Y0, Y1 + 1):
    xs = np.where(mask[y, SIDE[0]:SIDE[1]])[0]
    side_c[y] = (xs.max() + xs.min()) / 2 + SIDE[0] if len(xs) else np.nan
ref_c = np.nanmedian(side_c[Y0:Y1])
side_c = np.where(np.isnan(side_c), ref_c, side_c) - ref_c
side_t = np.convolve(side_t, np.ones(5) / 5, mode='same')


def to_world(x, y, yoff=0.0):
    """px -> metres: X right, Z up, Y depth; origin at guard centre row."""
    return Vector(((x - CX) * SCALE, yoff * SCALE, -(y - 500) * SCALE))


def build_part(name, ya, yb, taper_x=False, depth_mul=1.0, bevel=0.0015):
    sub = np.zeros_like(mask)
    sub[ya:yb, FRONT[0]:FRONT[1]] = mask[ya:yb, FRONT[0]:FRONT[1]]
    cs, hier = cv2.findContours(sub, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    objs = []
    for ci, c in enumerate(cs):
        if hier[0][ci][3] != -1 or cv2.contourArea(c) < 12:
            continue  # holes handled via fill below
        pts = cv2.approxPolyDP(c, 0.7, True)[:, 0, :].astype(float)
        if len(pts) < 3:
            continue
        # tiny blobs -> skip
        bm = bmesh.new()
        top, bot = [], []
        xmin, xmax = pts[:, 0].min(), pts[:, 0].max()
        half = max((xmax - xmin) / 2, 1)
        mid = (xmin + xmax) / 2
        for (x, y) in pts:
            yi = int(min(max(y, Y0), Y1))
            t = max(side_t[yi], 3) * depth_mul / 2
            if taper_x:
                f = 1 - 0.75 * min(abs(x - mid) / half, 1) ** 1.5
                t *= max(f, 0.18)
            co = side_c[yi]
            top.append(bm.verts.new(to_world(x, y, co + t)))
            bot.append(bm.verts.new(to_world(x, y, co - t)))
        n = len(pts)
        # polygon (non-convex) caps via triangle_fill on edge loops
        e_top = [bm.edges.new((top[i], top[(i + 1) % n])) for i in range(n)]
        e_bot = [bm.edges.new((bot[i], bot[(i + 1) % n])) for i in range(n)]
        for i in range(n):
            try:
                bm.faces.new((top[i], top[(i + 1) % n], bot[(i + 1) % n], bot[i]))
            except ValueError:
                pass
        r1 = bmesh.ops.triangle_fill(bm, edges=e_top, use_beauty=True)
        r2 = bmesh.ops.triangle_fill(bm, edges=e_bot, use_beauty=True)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        me = bpy.data.meshes.new(f'{name}_{ci}M')
        bm.to_mesh(me); bm.free()
        ob = bpy.data.objects.new(f'GEO-{name}_{ci}', me)
        bpy.context.collection.objects.link(ob)
        objs.append(ob)
    # cut holes (e.g. chain link interiors, guard cut-outs) with boolean
    for ci, c in enumerate(cs):
        if hier[0][ci][3] == -1 or cv2.contourArea(c) < 12:
            continue
        pts = cv2.approxPolyDP(c, 0.7, True)[:, 0, :].astype(float)
        if len(pts) < 3:
            continue
        bm = bmesh.new()
        ring = []
        for (x, y) in pts:
            ring.append((bm.verts.new(to_world(x, y, -40)), bm.verts.new(to_world(x, y, 40))))
        n = len(ring)
        bt = [r[0] for r in ring]; tp = [r[1] for r in ring]
        et = [bm.edges.new((tp[i], tp[(i + 1) % n])) for i in range(n)]
        eb = [bm.edges.new((bt[i], bt[(i + 1) % n])) for i in range(n)]
        for i in range(n):
            try: bm.faces.new((tp[i], tp[(i + 1) % n], bt[(i + 1) % n], bt[i]))
            except ValueError: pass
        bmesh.ops.triangle_fill(bm, edges=et); bmesh.ops.triangle_fill(bm, edges=eb)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        me = bpy.data.meshes.new('cutM'); bm.to_mesh(me); bm.free()
        cut = bpy.data.objects.new('CUT', me); bpy.context.collection.objects.link(cut)
        # apply to nearest part (hole centroid inside its bbox)
        cc = Vector(np.mean([to_world(x, y) for x, y in pts], axis=0))
        for ob in objs:
            bb = [ob.matrix_world @ Vector(v) for v in ob.bound_box]
            if min(v.x for v in bb) <= cc.x <= max(v.x for v in bb) and min(v.z for v in bb) <= cc.z <= max(v.z for v in bb):
                md = ob.modifiers.new('hole', 'BOOLEAN'); md.object = cut; md.operation = 'DIFFERENCE'; md.solver = 'EXACT'
                bpy.context.view_layer.objects.active = ob
                bpy.ops.object.modifier_apply(modifier='hole')
                break
        bpy.data.objects.remove(cut)
    return objs


def join(objs, name):
    if not objs: return None
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    o = bpy.context.active_object; o.name = name
    for p in o.data.polygons: p.use_smooth = True
    if bpy.app.version < (4, 1):
        pass
    bv = o.modifiers.new('bevel', 'BEVEL'); bv.width = 0.0012; bv.segments = 2; bv.limit_method = 'ANGLE'
    ws = o.modifiers.new('wn', 'WEIGHTED_NORMAL'); ws.keep_sharp = True
    return o


bpy.ops.wm.read_factory_settings(use_empty=True)
parts = {}
parts['blade'] = join(build_part('blade', Y0, 450), 'GEO-sword_blade')
parts['guard'] = join(build_part('guard', 450, 560, taper_x=True, depth_mul=1.0), 'GEO-sword_guard')
parts['grip'] = join(build_part('grip', 560, 690), 'GEO-sword_grip')
parts['chain'] = join(build_part('chain', 690, 800), 'GEO-sword_chain')
parts['pommel'] = join(build_part('pommel', 800, Y1 + 1, taper_x=True), 'GEO-sword_pommel')
for k, o in parts.items():
    print('PART', k, None if o is None else (len(o.data.vertices), len(o.data.polygons)))

bpy.ops.wm.save_as_mainfile(filepath=OUT + '.blend')
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=OUT + '.glb', export_format='GLB', use_selection=True, export_apply=True)
print('SAVED', OUT)
