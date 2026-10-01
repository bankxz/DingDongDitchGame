"""Sample a colour family from a reference image (sRGB 0..1) by luminance percentile.
python sample_palette.py ref.png purple|cyan|red"""
import sys
import numpy as np
from PIL import Image

h = np.asarray(Image.open(sys.argv[1]).convert('RGB')).astype(float).reshape(-1, 3) / 255
fam = sys.argv[2] if len(sys.argv) > 2 else 'purple'
r, g, b = h[:, 0], h[:, 1], h[:, 2]
m = {'purple': (b > r) & (r > g + 0.08) & (g < 0.5),
     'cyan': (b > 0.6) & (g > 0.6) & (r < 0.5),
     'red': (r > 0.5) & (r > g * 2) & (r > b * 1.5)}[fam]
p = h[m]
print(fam, 'pixels', len(p))
o = np.argsort(p.mean(1))
for f in (0.1, 0.3, 0.5, 0.7, 0.9):
    print(f'lum {f:.1f}', np.round(p[o[int(f * (len(o) - 1))]], 3))
