"""Side-by-side reference vs render sheet for every view.

python3 compare_sheet.py <reference_sheet.png> <render_dir> <out.png>
"""
import sys

from PIL import Image, ImageDraw

REF_CROPS = {
    'hero': (0, 0, 1180, 590),
    'head_front': (1025, 0, 1255, 335),
    'head_side': (1255, 0, 1536, 335),
    'front': (0, 595, 268, 985),
    'back': (270, 595, 558, 985),
    'left': (560, 600, 1078, 785),
    'right': (560, 800, 1078, 985),
    'top': (1080, 595, 1305, 985),
    'bottom': (1305, 595, 1536, 985),
}

ref = Image.open(sys.argv[1]).convert('RGB')
rows = []
for name, box in REF_CROPS.items():
    try:
        r = Image.open(f'{sys.argv[2]}/{name}.png').convert('RGB')
    except FileNotFoundError:
        continue
    a = ref.crop(box)
    h = 300
    a = a.resize((int(a.width * h / a.height), h))
    r = r.resize((int(r.width * h / r.height), h))
    row = Image.new('RGB', (a.width + r.width + 10, h + 20), (20, 20, 20))
    row.paste(a, (0, 20))
    row.paste(r, (a.width + 10, 20))
    ImageDraw.Draw(row).text((4, 4), f'{name}: reference | model', fill=(255, 255, 255))
    rows.append(row)
W = max(r.width for r in rows)
sheet = Image.new('RGB', (W, sum(r.height for r in rows)), (20, 20, 20))
y = 0
for r in rows:
    sheet.paste(r, (0, y))
    y += r.height
sheet.save(sys.argv[3])
