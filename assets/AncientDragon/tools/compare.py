"""Side-by-side reference vs render sheets."""
import os, sys
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..'))
REF = sys.argv[1]
ref = Image.open(REF).convert('RGB')
PANELS = {'persp': (0, 0, 728, 612), 'front': (728, 0, 1090, 272), 'back': (1090, 0, 1448, 272),
          'left': (728, 275, 1090, 455), 'right': (1090, 275, 1448, 455), 'top': (728, 455, 1090, 612),
          'bottom': (1090, 455, 1448, 612)}
tag = sys.argv[2] if len(sys.argv) > 2 else 'Idle_001'
for name, box in PANELS.items():
    rp = os.path.join(ROOT, 'validation', f'{tag}_{name}.png')
    if not os.path.exists(rp):
        continue
    a = ref.crop(box); rgba = Image.open(rp).convert('RGBA')
    bb = rgba.getchannel('A').point(lambda v: 255 if v > 20 else 0).getbbox()
    rgba = rgba.crop(bb)
    bw, bh = a.size; mw, mh = int(bw * 0.94), int(bh * 0.8)
    k = min(mw / rgba.width, mh / rgba.height)
    rgba = rgba.resize((max(1, int(rgba.width * k)), max(1, int(rgba.height * k))), Image.LANCZOS)
    b = Image.new('RGB', a.size, (120, 180, 235))
    b.paste(Image.new('RGB', (bw, bh // 3), (40, 42, 58)), (0, bh - bh // 3))
    b.paste(rgba, ((bw - rgba.width) // 2, int(bh * 0.86) - rgba.height), rgba)
    h = 540; a = a.resize((int(a.width * h / a.height), h)); b = b.resize((int(b.width * h / b.height), h))
    s = Image.new('RGB', (a.width + b.width, h)); s.paste(a, (0, 0)); s.paste(b, (a.width, 0))
    s.save(os.path.join(ROOT, 'validation', f'cmp_{name}.png'))
print('ok')
