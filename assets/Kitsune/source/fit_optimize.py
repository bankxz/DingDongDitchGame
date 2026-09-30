"""Coordinate-descent solve of the tail-fan tunables against the sheet silhouettes.
python fit_optimize.py -- <ref_mask_dir> <out.json>
Objective: weighted IoU (side 0.4, front 0.35, back 0.25) of flat silhouettes.
"""
import os, sys, json
import numpy as np
import bpy
from mathutils import Vector
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kitsune_geo as kg

argv = sys.argv[sys.argv.index('--') + 1:]
refdir, outp = argv[0], argv[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'
sc.cycles.samples = 1
sc.cycles.use_denoising = False
sc.render.film_transparent = True
sc.render.resolution_x = sc.render.resolution_y = 256
cd = bpy.data.cameras.new('c'); cam = bpy.data.objects.new('c', cd); sc.collection.objects.link(cam); sc.camera = cam
cd.type = 'ORTHO'; cd.ortho_scale = 4.4
VIEWS = {'side_L': (Vector((1, 0, 0.02)), 0.40), 'front': (Vector((0, -1, 0.27)), 0.35), 'back': (Vector((0, 1, 0.27)), 0.25)}
tgt = Vector((0, 0.3, 0.85))
tmp = os.path.join(os.path.dirname(outp), '_opt.png')


def norm_mask(m, H=200):
    ys, xs = np.nonzero(m)
    c = Image.fromarray((m[ys.min():ys.max() + 1, xs.min():xs.max() + 1] * 255).astype(np.uint8))
    c = c.resize((max(1, int(round(c.width * H / c.height))), H), Image.BILINEAR)
    return np.array(c) > 127


REF = {v: norm_mask(np.array(Image.open(os.path.join(refdir, f'{v}_mask.png'))) > 127) for v in VIEWS}
ob = None


def score(tune):
    global ob
    kg.TAIL_TUNE.update(tune)
    _b, _a, _ = kg.build_kitsune()
    md = kg.combined(_b, _a)
    me = bpy.data.meshes.new('fit')
    me.from_pydata([tuple(v) for v in md.verts], [], md.faces)
    if ob is None:
        ob = bpy.data.objects.new('fit', me); sc.collection.objects.link(ob)
    else:
        old = ob.data; ob.data = me; bpy.data.meshes.remove(old)
    res = {}
    tot = 0
    for v, (d, w) in VIEWS.items():
        d = d.normalized()
        cam.location = tgt + d * 10
        cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = tmp
        bpy.ops.render.render(write_still=True)
        m = norm_mask(np.array(Image.open(tmp))[..., 3] > 128)
        r = REF[v]
        W = max(r.shape[1], m.shape[1]) + 4
        A = np.zeros((200, W), bool); B = np.zeros((200, W), bool)
        A[:, (W - r.shape[1]) // 2:(W - r.shape[1]) // 2 + r.shape[1]] = r
        B[:, (W - m.shape[1]) // 2:(W - m.shape[1]) // 2 + m.shape[1]] = m
        iou = (A & B).sum() / max((A | B).sum(), 1)
        res[v] = round(float(iou), 4)
        tot += w * iou
    return tot, res


tune = dict(kg.TAIL_TUNE)
steps = dict(lat=0.08, back=0.10, dz_top=0.10, dz_mid=0.10, dz_low=0.10, rs=0.08)
best, bres = score(tune)
print('start', round(best, 4), bres)
for rnd in range(3):
    improved = False
    for k in steps:
        for sgn in (1, -1):
            trial = dict(tune); trial[k] = round(trial[k] + sgn * steps[k], 4)
            s, r = score(trial)
            if s > best + 1e-4:
                best, bres, tune = s, r, trial
                improved = True
                print('  ', k, trial[k], round(best, 4), r)
                break
    steps = {k: v * 0.5 for k, v in steps.items()}
    if not improved and rnd > 0:
        break
json.dump(dict(tune=tune, score=best, per_view=bres), open(outp, 'w'), indent=1)
os.remove(tmp)
print('best', tune, round(best, 4), bres)
