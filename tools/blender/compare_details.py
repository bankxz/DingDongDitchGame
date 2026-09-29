"""Reference detail panels next to matching model close-ups.

python3 tools/blender/compare_details.py <reference_sheet> <detail_render_dir> <out_png>
"""
import sys

from PIL import Image, ImageDraw

ref_path, d, out = sys.argv[1:4]
im = Image.open(ref_path).convert("RGB")
# (reference crop box on the 1448x1086 sheet, model render name)
PAIRS = [
    ((0, 522, 176, 700), "head_front", "FRONT HEAD"),
    ((176, 522, 352, 700), "head_34", "3/4 HEAD"),
    ((352, 522, 548, 700), "head_side", "SIDE HEAD"),
    ((0, 885, 585, 1070), "tail", "TAIL"),
    ((585, 885, 985, 1070), "claw", "CLAW / FOOT"),
]
rows = []
for box, name, label in PAIRS:
    ref = im.crop(box)
    h = 320
    ref = ref.resize((int(ref.width * h / ref.height), h))
    ren = Image.open(f"{d}/{name}.png").convert("RGB")
    ren = ren.resize((int(ren.width * h / ren.height), h))
    row = Image.new("RGB", (ref.width + ren.width + 20, h + 24), (20, 20, 28))
    row.paste(ref, (0, 24))
    row.paste(ren, (ref.width + 20, 24))
    dr = ImageDraw.Draw(row)
    dr.text((6, 6), "REFERENCE " + label, fill=(255, 255, 255))
    dr.text((ref.width + 26, 6), "MODEL " + label, fill=(255, 255, 255))
    rows.append(row)
W = max(r.width for r in rows)
sheet = Image.new("RGB", (W, sum(r.height for r in rows)), (20, 20, 28))
y = 0
for r in rows:
    sheet.paste(r, (0, y))
    y += r.height
sheet.save(out)
