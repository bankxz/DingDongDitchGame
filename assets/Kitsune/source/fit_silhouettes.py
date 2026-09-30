"""Multiview silhouette fit gate (reference-analysis-validator + multiview-fit-loop).

Builds the current geometry, renders flat alpha silhouettes from cameras that
match the reference sheet panels, compares them to the reference masks and
writes IoU / bbox-aspect deltas + red/green overlays.

python fit_silhouettes.py -- <ref_mask_dir> <outdir>
Reference masks: <ref_mask_dir>/{front,side_L,back,top}_mask.png
"""
import os, sys, json, math
import numpy as np
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kitsune_geo as kg

argv = sys.argv[sys.argv.index('--') + 1:]
refdir, out = argv[0], argv[1]
os.makedirs(out, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
_b, _a, _ = kg.build_kitsune()
md = kg.combined(_b, _a)
me = bpy.data.meshes.new('fit')
me.from_pydata([tuple(v) for v in md.verts], [], md.faces)
ob = bpy.data.objects.new('fit', me)
bpy.context.scene.collection.objects.link(ob)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'
sc.cycles.samples = 4
sc.cycles.use_denoising = False
sc.render.film_transparent = True
sc.render.resolution_x = sc.render.resolution_y = 512
cd = bpy.data.cameras.new('c')
cam = bpy.data.objects.new('c', cd)
sc.collection.objects.link(cam)
sc.camera = cam

# camera directions (from target) matching the sheet panels
VIEWS = {
    'front': Vector((0, -1, 0.27)),
    'side_L': Vector((1, 0, 0.02)),
    'back': Vector((0, 1, 0.27)),
    'top': Vector((0, -0.60, 1.0)),
}
tgt = Vector((0, 0.3, 0.85))
from PIL import Image


def norm_mask(m, H=300):
    ys, xs = np.nonzero(m)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    c = Image.fromarray((m[y0:y1, x0:x1] * 255).astype(np.uint8))
    w = max(1, int(round(c.width * H / c.height)))
    c = c.resize((w, H), Image.BILINEAR)
    return (np.array(c) > 127), (x1 - x0) / (y1 - y0)


report = {}
for v, d in VIEWS.items():
    d = d.normalized()
    # sheet panels read as near-orthographic; front/back are shot from ~15 deg
    # above (far tails appear higher than the ears), top from ~60 deg front-above
    cd.type = 'ORTHO'
    cd.ortho_scale = 4.2
    cam.location = tgt + d * 10
    cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    p = os.path.join(out, f'_sil_{v}.png')
    sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
    a = np.array(Image.open(p))[..., 3] > 128
    os.remove(p)
    r = np.array(Image.open(os.path.join(refdir, f'{v}_mask.png'))) > 127
    rn, ra = norm_mask(r)
    mn, ma = norm_mask(a)
    W = max(rn.shape[1], mn.shape[1]) + 20
    A = np.zeros((300, W), bool); B = np.zeros((300, W), bool)
    ox = (W - rn.shape[1]) // 2; A[:, ox:ox + rn.shape[1]] = rn
    ox = (W - mn.shape[1]) // 2; B[:, ox:ox + mn.shape[1]] = mn
    iou = (A & B).sum() / max((A | B).sum(), 1)
    ov = np.zeros((300, W, 3), np.uint8)
    ov[A & ~B] = (230, 40, 40)      # reference only  -> model is missing this
    ov[B & ~A] = (40, 200, 60)      # model only      -> model has extra
    ov[A & B] = (200, 200, 200)
    Image.fromarray(ov).save(os.path.join(out, f'overlay_{v}.png'))
    report[v] = dict(iou=round(float(iou), 4), ref_aspect=round(float(ra), 4), model_aspect=round(float(ma), 4),
                     aspect_drift=round(float(ma / ra - 1), 4))
json.dump(report, open(os.path.join(out, 'multiview_fit_report.json'), 'w'), indent=1)
print(json.dumps(report))
ims = [Image.open(os.path.join(out, f'overlay_{v}.png')) for v in VIEWS]
Wt = sum(i.width for i in ims) + 10 * len(ims)
sheet = Image.new('RGB', (Wt, 300), (0, 0, 0))
x = 0
for i in ims:
    sheet.paste(i, (x, 0)); x += i.width + 10
sheet.save(os.path.join(out, 'overlay_all.png'))
