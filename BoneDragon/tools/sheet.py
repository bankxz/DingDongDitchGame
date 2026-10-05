"""Composite renders on the reference's grey and tile them like the reference sheet. python3 sheet.py renders out.png [res]"""
import sys
from PIL import Image
d, out = sys.argv[1], sys.argv[2]; R = int(sys.argv[3]) if len(sys.argv) > 3 else 512
names = ['front', 'back', 'left', 'right', 'top', 'persp34']; s = Image.new('RGB', (R * 3, R * 2), (234, 234, 236))
for i, n in enumerate(names):
    im = Image.open(f'{d}/{n}.png').convert('RGBA').resize((R, R), Image.LANCZOS); s.paste(im, ((i % 3) * R, (i // 3) * R), im)
s.save(out)
