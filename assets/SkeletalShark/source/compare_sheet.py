"""Side-by-side: reference sheet crop (top) vs render (bottom) per view."""
import sys, os
from PIL import Image
ref = Image.open(sys.argv[1]).convert("RGB")
rd, out = sys.argv[2], sys.argv[3]
CROPS = {"left": (20, 390, 705, 615), "right": (730, 390, 1420, 615), "front": (615, 15, 990, 355),
         "back": (995, 15, 1420, 355), "top": (35, 645, 690, 840), "three_quarter": (20, 20, 640, 390)}
for v, box in CROPS.items():
    p = os.path.join(rd, v + ".png")
    if not os.path.exists(p): continue
    a = ref.crop(box); b = Image.open(p).convert("RGB")
    W = 1000
    a = a.resize((W, int(a.height * W / a.width)), Image.LANCZOS)
    b = b.resize((W, int(b.height * W / b.width)), Image.LANCZOS)
    c = Image.new("RGB", (W, a.height + b.height + 6), (255, 0, 0))
    c.paste(a, (0, 0)); c.paste(b, (0, a.height + 6)); c.save(os.path.join(out, f"cmp_{v}.png"))
