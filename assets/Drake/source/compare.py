"""Stack reference-sheet crops next to renders for visual validation."""
import sys, os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, '..', 'reference', 'drake_reference_sheet.png')
CROPS = {'front': (0, 0, 420, 390), 'back': (420, 0, 740, 390), 'q34': (740, 0, 1448, 400),
         'left': (0, 410, 735, 610), 'right': (735, 410, 1448, 610), 'top': (50, 615, 1400, 790)}


def main(render_dir, prefix, out):
    ref = Image.open(REF).convert('RGB')
    rows = []
    for k, box in CROPS.items():
        p = os.path.join(render_dir, f'{prefix}_{k}.png')
        if not os.path.exists(p):
            continue
        a = ref.crop(box)
        b = Image.open(p).convert('RGB')
        h = 360
        a = a.resize((int(a.width * h / a.height), h))
        b = b.resize((int(b.width * h / b.height), h))
        row = Image.new('RGB', (a.width + b.width + 10, h), (255, 255, 255))
        row.paste(a, (0, 0)); row.paste(b, (a.width + 10, 0))
        rows.append(row)
    W = max(r.width for r in rows)
    sheet = Image.new('RGB', (W, sum(r.height + 10 for r in rows)), (255, 255, 255))
    y = 0
    for r in rows:
        sheet.paste(r, (0, y)); y += r.height + 10
    sheet.save(out)


if __name__ == '__main__':
    main(*sys.argv[1:4])
