"""Animation quality gate: render contact sheets for each action.
python render_contact_sheets.py -- <Kitsune.blend> <outdir> [frames_per_anim]
Writes <outdir>/contact_<Action>.png plus a JSON report with per-frame
silhouette stats (ground contact, bounding box, frame-to-frame change).
"""
import os, sys, json
import numpy as np
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import render_views as rv

argv = sys.argv[sys.argv.index('--') + 1:]
blend, out = argv[0], argv[1]
nf = int(argv[2]) if len(argv) > 2 else 6
os.makedirs(out, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=blend)
arm = bpy.data.objects['Kitsune_Rig']
ob = bpy.data.objects['Kitsune']
rv.setup_scene(res=(420, 300), samples=12)
S = 4.0
report = {}
from PIL import Image
for act in ('Kitsune_Idle', 'Kitsune_Run', 'Kitsune_Sleep'):
    a = bpy.data.actions[act]
    arm.animation_data.action = a
    N = int(a.frame_range[1])
    frames = [int(round(i * N / nf)) for i in range(nf)]
    tiles, stats = [], []
    for f in frames:
        bpy.context.scene.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        me = ob.evaluated_get(dg).to_mesh()
        co = np.zeros(len(me.vertices) * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
        ob.evaluated_get(dg).to_mesh_clear()
        stats.append(dict(frame=f, min_z=float(co[:, 2].min()), max_z=float(co[:, 2].max()),
                          bbox=[float(x) for x in np.r_[co.min(0), co.max(0)]]))
        row = []
        for v in ('side_left', 'q34_front_right'):
            p = os.path.join(out, f'_{act}_{f}_{v}.png')
            rv.render_view(v, p, Vector((0, 0.35, 0.8)) * S, 3.0 * S)
            row.append(Image.open(p).convert('RGB'))
            os.remove(p)
        tiles.append(row)
    W, H = tiles[0][0].size
    sheet = Image.new('RGB', (W * len(tiles), H * 2))
    for i, row in enumerate(tiles):
        for j, im in enumerate(row):
            sheet.paste(im, (i * W, j * H))
    sheet.save(os.path.join(out, f'contact_{act}.png'))
    report[act] = stats
json.dump(report, open(os.path.join(out, 'animation_report.json'), 'w'), indent=1)
print(json.dumps({k: [round(s['min_z'], 3) for s in v] for k, v in report.items()}))
