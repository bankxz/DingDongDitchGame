"""Reference-vs-render comparison strips.  python3 side_by_side.py out.png ref1.png render1.png [ref2 render2 ...]
Each pair becomes one row: reference left, render right, same height."""
import sys
from PIL import Image
out, files = sys.argv[1], sys.argv[2:]; H = 450; rows = []
for a, b in zip(files[::2], files[1::2]):
    A, B = (Image.open(x).convert('RGB') for x in (a, b))
    A = A.resize((int(A.width * H / A.height), H)); B = B.resize((int(B.width * H / B.height), H))
    r = Image.new('RGB', (A.width + B.width, H)); r.paste(A, (0, 0)); r.paste(B, (A.width, 0)); rows.append(r)
s = Image.new('RGB', (max(r.width for r in rows), H * len(rows)))
for i, r in enumerate(rows): s.paste(r, (0, i * H))
s.save(out); print('wrote', out)
