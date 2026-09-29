"""Render animation contact sheets (idle + walk) for the quality gate.  usage: python3 render_anim_sheet.py OUTDIR"""
import sys, os, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy
import numpy as np
from PIL import Image, ImageDraw
import preview as P

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, '..', 'Drake.blend'))
sc = bpy.context.scene
for o in list(sc.objects):
    if o.type in ('LIGHT', 'CAMERA'):
        bpy.data.objects.remove(o)
co = P.setup_scene()
sc.cycles.samples = 12
rig = bpy.data.objects['DrakeRig']
rig.hide_render = True
sc.render.resolution_x, sc.render.resolution_y = 520, 360
cams = {'q34': ((9.5, -6.0, 3.0), (0, -0.2, 0.9)), 'top': ((0, 0.5, 15), (0, 0.5001, 0))}
report = {}
for act_name, frames in (('Drake_Idle', [0, 20, 40, 60, 80, 100]), ('Drake_Walk', [0, 8, 16, 24, 32, 40])):
    rig.animation_data.action = bpy.data.actions[act_name]
    tiles = []
    for cam, (loc, tgt) in cams.items():
        P.aim(co, loc, tgt, 10.0 if cam == 'top' else None, lens=32)
        if cam == 'top':
            co.rotation_euler = (0, 0, math.radians(90))
        for f in frames:
            sc.frame_set(f)
            p = os.path.join(OUT, f'{act_name}_{cam}_{f:03d}.png')
            sc.render.filepath = p
            bpy.ops.render.render(write_still=True)
            im = Image.open(p).convert('RGB')
            ImageDraw.Draw(im).text((8, 8), f'{act_name} {cam} f{f}', fill=(255, 255, 255))
            tiles.append(im)
    W, H = tiles[0].size
    sheet = Image.new('RGB', (W * len(frames), H * len(cams)))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % len(frames)) * W, (i // len(frames)) * H))
    sheet.save(os.path.join(OUT, f'{act_name}_contact_sheet.png'))
    # loop check: first vs last frame of the action should match
    a0, a1 = rig.animation_data.action.frame_range
    sc.frame_set(int(a0)); m0 = [pb.matrix.copy() for pb in rig.pose.bones]
    sc.frame_set(int(a1)); m1 = [pb.matrix.copy() for pb in rig.pose.bones]
    err = max(max(abs(x - y) for rx, ry in zip(A, B) for x, y in zip(rx, ry)) for A, B in zip(m0, m1))
    report[act_name] = err
    print(act_name, 'loop seam max matrix delta', err)
print('REPORT', report)
