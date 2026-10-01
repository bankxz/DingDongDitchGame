"""Labeled image grid for review sheets.
python labeled_sheet.py out.png CELL_W CELL_H "label|path" "label|path" / "label|path" ...
('/' starts a new row)"""
import sys
from PIL import Image, ImageDraw, ImageFont

out, W, H = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
rows, cur = [], []
for a in sys.argv[4:]:
    if a == '/':
        rows.append(cur); cur = []
    else:
        cur.append(a.split('|', 1))
rows.append(cur)
cols = max(len(r) for r in rows)
try:
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 26)
except Exception:
    font = ImageFont.load_default()
S = Image.new('RGB', (W * cols, (H + 40) * len(rows)), (28, 28, 30))
d = ImageDraw.Draw(S)
for r, row in enumerate(rows):
    for c, (lab, p) in enumerate(row):
        im = Image.open(p).convert('RGB')
        im.thumbnail((W - 8, H - 8), Image.LANCZOS)
        x0, y0 = c * W, r * (H + 40)
        S.paste(im, (x0 + (W - im.width) // 2, y0 + 40 + (H - im.height) // 2))
        d.text((x0 + 10, y0 + 6), lab, fill=(235, 235, 235), font=font)
S.save(out)
print(out, S.size)
