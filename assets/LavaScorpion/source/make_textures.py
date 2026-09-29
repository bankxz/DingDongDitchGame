"""Generate the Lava Scorpion texture atlas (1024x1024, 4x4 cells of 256px).

Every box face of the mesh is UV-mapped onto exactly one cell. Each cell carries:
  * square Roblox studs (from the MIT "Roblox-HD-Studs" stud normal + AO maps, github.com/dudeax/Roblox-HD-Studs)
  * glowing lava seams on the cell border (so every block edge glows like the reference)
  * optional lava cracks (body plates)
Hot cells carry the deep red -> lava orange -> hot yellow gradient along V (base -> tip).

Outputs: LavaScorpion_Color.png (glow baked in, used by Roblox), LavaScorpion_Emission.png,
         LavaScorpion_Normal.png (OpenGL tangent space, optional SurfaceAppearance NormalMap).
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
STUDS = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "studs")
OUT = os.path.join(HERE, "..", "textures")
os.makedirs(OUT, exist_ok=True)

GRID = 6
CELL = 1024 // GRID  # 170
ATLAS = 1024
rng = np.random.default_rng(7)

# Palette sampled from the reference sheet swatches
CHARCOAL = np.array([42, 41, 46]) / 255
DARKGRAY = np.array([72, 64, 72]) / 255
DEEPRED = np.array([163, 40, 31]) / 255
ORANGE = np.array([253, 108, 9]) / 255
YELLOW = np.array([254, 221, 53]) / 255
ROCK = np.array([44, 33, 32]) / 255  # charcoal warmed by lava bounce (reference rock faces read warm brown)

# ---------------------------------------------------------------- stud source
stud_n = np.asarray(Image.open(os.path.join(STUDS, "Studs 2x2 Normal.png")).convert("RGB"), dtype=np.float32) / 255
stud_ao = np.asarray(Image.open(os.path.join(STUDS, "Studs 2x2 AO Diffuse.png")).convert("L"), dtype=np.float32) / 255
TILE = stud_n.shape[0] // 2  # one stud per quadrant
stud_n = stud_n[:TILE, :TILE]
stud_ao = stud_ao[:TILE, :TILE]


def stud_tile(nu, nv):
    """Return (normal rgb, ao) arrays of CELL x CELL holding nu x nv studs."""
    w, h = CELL // nu, CELL // nv
    n_img = Image.fromarray((stud_n * 255).astype(np.uint8)).resize((w, h), Image.LANCZOS)
    a_img = Image.fromarray((stud_ao * 255).astype(np.uint8)).resize((w, h), Image.LANCZOS)
    n = np.tile(np.asarray(n_img, np.float32) / 255, (nv, nu, 1))
    a = np.tile(np.asarray(a_img, np.float32) / 255, (nv, nu))
    n = np.asarray(Image.fromarray((n * 255).astype(np.uint8)).resize((CELL, CELL), Image.LANCZOS), np.float32) / 255
    a = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).resize((CELL, CELL), Image.LANCZOS), np.float32) / 255
    return n, a


def shade_from_normal(n):
    v = n * 2 - 1
    L = np.array([-0.35, 0.55, 0.76])
    L /= np.linalg.norm(L)
    s = (v @ L) / L[2]
    return np.clip(s, 0.35, 1.6)


def glow_ramp(t):
    """t in 0..1 (1 = hottest) -> lava colour."""
    t = np.clip(t, 0, 1)[..., None]
    c1 = DEEPRED * 0.55
    c = np.where(t < 0.35, c1 + (DEEPRED - c1) * (t / 0.35),
         np.where(t < 0.7, DEEPRED + (ORANGE - DEEPRED) * ((t - 0.35) / 0.35),
                  ORANGE + (YELLOW - ORANGE) * ((t - 0.7) / 0.3)))
    return c


yy, xx = np.mgrid[0:CELL, 0:CELL].astype(np.float32)
fx = (xx + 0.5) / CELL
fy = (yy + 0.5) / CELL


def border_dist(nu, nv):
    du = np.minimum(fx, 1 - fx) * nu
    dv = np.minimum(fy, 1 - fy) * nv
    return np.minimum(du, dv)  # in stud units


def inner_seam_dist(nu, nv):
    su = (fx * nu) % 1.0
    sv = (fy * nv) % 1.0
    return np.minimum(np.minimum(su, 1 - su), np.minimum(sv, 1 - sv))


def crack_mask(nu, nv, seed, n_cracks=2):
    r = np.random.default_rng(seed)
    img = Image.new("L", (CELL, CELL), 0)
    d = ImageDraw.Draw(img)
    for _ in range(n_cracks):
        # start on one edge, wander to another edge
        if r.random() < 0.5:
            p = [r.uniform(0.25, 0.75) * CELL, 0]
            direction = np.array([0, 1.0])
        else:
            p = [0, r.uniform(0.25, 0.75) * CELL]
            direction = np.array([1.0, 0])
        pts = [tuple(p)]
        pos = np.array(p, float)
        while 0 <= pos[0] <= CELL and 0 <= pos[1] <= CELL:
            step = direction * r.uniform(34, 56) + r.normal(0, 12, 2)
            pos = pos + step
            pts.append(tuple(pos))
        d.line(pts, fill=255, width=7, joint='curve')
        # a branch
        k = len(pts) // 2
        bp = np.array(pts[k])
        bdir = np.array([direction[1], direction[0]]) * (1 if r.random() < 0.5 else -1)
        bpts = [tuple(bp)]
        for _ in range(3):
            bp = bp + bdir * r.uniform(18, 30) + r.normal(0, 10, 2)
            bpts.append(tuple(bp))
        d.line(bpts, fill=255, width=5, joint='curve')
    core = np.asarray(img, np.float32) / 255
    soft = np.asarray(img.filter(ImageFilter.GaussianBlur(12)), np.float32) / 255
    return core, soft


def rock_cell(nu, nv, cracked=False, seed=0, joints_only=False, dark=False):
    n, ao = stud_tile(nu, nv)
    shade = shade_from_normal(n)
    r = np.random.default_rng(seed + nu * 10 + nv)
    # per-stud-block variation so it reads as separate cubes
    su = np.minimum((fx * nu).astype(int), nu - 1)
    sv = np.minimum((fy * nv).astype(int), nv - 1)
    var = r.uniform(0.85, 1.12, (nv, nu))[sv, su]
    noise = np.asarray(Image.fromarray((r.random((CELL // 8, CELL // 8)) * 255).astype(np.uint8)).resize((CELL, CELL), Image.BICUBIC), np.float32) / 255
    base = ROCK[None, None, :] * (var * (0.9 + 0.2 * noise))[..., None]
    col = base * shade[..., None] * (0.55 + 0.45 * ao[..., None])

    wob = np.asarray(Image.fromarray((r.random((6, 6)) * 255).astype(np.uint8)).resize((CELL, CELL), Image.BICUBIC), np.float32) / 255
    bd_all = border_dist(nu, nv)
    bd = np.minimum(fy, 1 - fy) * nv if joints_only else bd_all
    bd = np.maximum(bd + (wob - 0.5) * 0.09, 0)
    core = (bd < 0.03).astype(np.float32)
    # soft bevel on every block edge: bright lip on top/left, dark on bottom/right
    lip = (bd_all < 0.05).astype(np.float32) * (1 - core)
    tl = ((fx * nu < 0.05) | (fy * nv < 0.05)).astype(np.float32)
    col = col * (1 + lip[..., None] * (0.35 * tl[..., None] - 0.35 * (1 - tl[..., None])))
    # inner seams between studs of the same block: dark line with faint warm tint
    sd = inner_seam_dist(nu, nv)
    seam = (sd < 0.025).astype(np.float32) * (1 - core)
    col = col * (1 - 0.35 * seam[..., None]) + DEEPRED * 0.2 * seam[..., None]
    # lava seam: hot orange core + broad deep-red halo bleeding onto the rock
    g = np.exp(-np.maximum(bd - 0.045, 0) / 0.05)
    halo = np.exp(-np.maximum(bd - 0.045, 0) / 0.33)
    if dark:  # plain cube: no lava core, only a faint red bounce near its edges
        g = g * 0.0
        halo = np.exp(-np.maximum(bd_all, 0) / 0.2) * 0.45
    col = col * (1 - 0.6 * halo[..., None]) + (DEEPRED * 0.95)[None, None, :] * (0.9 * halo)[..., None]
    gcol = glow_ramp(0.45 + 0.47 * g)
    col = col * (1 - g[..., None]) + gcol * g[..., None]
    emis = gcol * g[..., None] + (DEEPRED * 0.35)[None, None, :] * halo[..., None]
    if cracked:
        ccore, csoft = crack_mask(nu, nv, seed + 99)
        ch = np.clip(csoft * 2.2, 0, 1)
        col = col * (1 - 0.5 * ch[..., None]) + (DEEPRED * 0.85)[None, None, :] * (0.75 * ch)[..., None]
        ccol = glow_ramp(0.5 + 0.5 * ccore)
        col = col * (1 - ccore[..., None]) + ccol * ccore[..., None]
        emis = np.maximum(emis, ccol * ccore[..., None] + (DEEPRED * 0.35)[None, None, :] * ch[..., None])
    nrm = n.copy()
    flat = np.array([0.5, 0.5, 1.0])
    nrm = nrm * (1 - core[..., None]) + flat * core[..., None]
    return col, emis, nrm


def hot_cell(t0, t1, nu=2, nv=2, seed=0):
    n, ao = stud_tile(nu, nv)
    shade = shade_from_normal(n)
    t = t0 + (t1 - t0) * (1 - fy)  # v=0 (image bottom) = base
    c = glow_ramp(t)
    c = c ** np.array([1.0, 1.25, 1.6])  # push saturation (reference claws are vivid, not pastel)
    col = c * (0.75 + 0.25 * shade[..., None]) * (0.8 + 0.2 * ao[..., None])
    # studs catch a lighter top edge
    col = np.clip(col + 0.08 * np.clip(shade - 1, 0, 1)[..., None], 0, 1)
    bd = border_dist(nu, nv)
    edge = (bd < 0.04).astype(np.float32)
    col = col * (1 - 0.25 * edge[..., None])
    emis = c * 0.4
    return col, emis, n


def eye_cell():
    t = 0.75 + 0.25 * (1 - np.abs(fy - 0.5) * 2)
    c = glow_ramp(t)
    return c, c, np.tile(np.array([0.5, 0.5, 1.0]), (CELL, CELL, 1))


# ---------------------------------------------------------------- atlas layout
LAYOUT = {}
cells = []
for nv in (1, 2, 3):
    for nu in (1, 2, 3):
        cells.append((f"R{nu}{nv}", (lambda nu=nu, nv=nv: rock_cell(nu, nv, seed=nu * 3 + nv))))
        cells.append((f"J{nu}{nv}", (lambda nu=nu, nv=nv: rock_cell(nu, nv, seed=40 + nu * 3 + nv, joints_only=True))))
        cells.append((f"D{nu}{nv}", (lambda nu=nu, nv=nv: rock_cell(nu, nv, seed=80 + nu * 3 + nv, dark=True))))
cells += [("R22C", lambda: rock_cell(2, 2, True, seed=10)), ("R33C", lambda: rock_cell(3, 3, True, seed=11)),
          ("R32C", lambda: rock_cell(3, 2, True, seed=12)), ("EYE", eye_cell),
          ("H0", lambda: hot_cell(0.45, 0.66)), ("H1", lambda: hot_cell(0.6, 0.86)),
          ("H2", lambda: hot_cell(0.86, 1.0))]
color = np.zeros((ATLAS, ATLAS, 3), np.float32)
emission = np.zeros_like(color)
normal = np.zeros_like(color)
for i, (name, fn) in enumerate(cells):
    cx, cy = i % GRID, i // GRID
    c, e, n = fn()
    ys, xs = cy * CELL, cx * CELL
    color[ys:ys + CELL, xs:xs + CELL] = c
    emission[ys:ys + CELL, xs:xs + CELL] = e
    normal[ys:ys + CELL, xs:xs + CELL] = n
    # UV rect (u0, v0, u1, v1) with v measured from the bottom of the image
    LAYOUT[name] = [cx * CELL / ATLAS, 1 - (cy + 1) * CELL / ATLAS, (cx + 1) * CELL / ATLAS, 1 - cy * CELL / ATLAS]


def save(a, name):
    Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)).save(os.path.join(OUT, name))


save(color, "LavaScorpion_Color.png")
save(emission, "LavaScorpion_Emission.png")
save(normal, "LavaScorpion_Normal.png")
with open(os.path.join(HERE, "atlas_regions.json"), "w") as f:
    json.dump(LAYOUT, f, indent=1)
print("atlas written", list(LAYOUT))
