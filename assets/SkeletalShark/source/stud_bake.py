"""Texture baker for the low-poly shark: rasterises every triangle into the UV atlas with a soft
painted gradient, bevel-style edge highlights and sparse engraved "stud" squares (full squares
and partial corner marks), matching the user's example pets. Pure numpy."""
import numpy as np

BONE = np.array((245, 228, 204), float)
IVORY = np.array((212, 186, 161), float)
DARK_BLUE = np.array((30, 52, 103), float)
BLUE_ACCENT = np.array((80, 129, 193), float)
CYAN = np.array((80, 251, 254), float)
SOCKET = np.array((20, 38, 92), float)
MATS = ["bone", "blue", "cyan", "socket", "tooth", "eye", "pupil"]
STUDDED = (0, 1)


def _shade(mat, h, nz, t_tip):
    """h: 0..1 height inside the part, nz: normal z, t_tip: 0..1 along a tooth."""
    n = h.shape[0]
    col = np.zeros((n, 3))
    light = 0.74 + 0.32 * h + 0.06 * nz
    if mat == 0:
        col[:] = (IVORY * 0.35 + BONE * 0.65)[None] * (1 - h[:, None] * 0.0) + (BONE - (IVORY * 0.35 + BONE * 0.65))[None] * h[:, None]
        col *= light[:, None]
    elif mat == 1:
        col[:] = DARK_BLUE[None] + (BLUE_ACCENT - DARK_BLUE)[None] * (0.08 + 0.32 * h)[:, None]
        col *= light[:, None]
    elif mat == 2:
        col[:] = CYAN[None] * (0.92 + 0.08 * h)[:, None]
    elif mat == 3:
        col[:] = SOCKET[None] * (0.9 + 0.2 * h)[:, None]
    elif mat == 4:
        col[:] = IVORY[None] + (np.array((255, 250, 240.0)) - IVORY)[None] * t_tip[:, None]
    elif mat == 5:  # neon iris: t_tip = radius 0..1 from the eye centre
        r = t_tip
        deep = np.array((25, 150, 255.0))
        col[:] = deep[None] + (CYAN - deep)[None] * np.clip((r - 0.25) / 0.5, 0, 1)[:, None]
        rim = np.clip((r - 0.78) / 0.12, 0, 1) * np.clip((1.02 - r) / 0.08, 0, 1)
        col += (np.array((235, 255, 255.0))[None] - col) * (0.75 * rim)[:, None]
    else:  # pupil: near-black navy with a small catch-light (t_tip = 1 inside the highlight)
        col[:] = np.array((6, 12, 30.0))[None]
        col += (np.array((230, 250, 255.0))[None] - col) * t_tip[:, None]
    return col


def _hash(a, b, seed):
    h = (a.astype(np.int64) * 73856093) ^ (b.astype(np.int64) * 19349663) ^ np.int64(seed * 83492791)
    h = (h ^ (h >> 13)) * 1274126177
    return ((h ^ (h >> 16)) & 0xFFFF) / 65535.0


def stud_pattern(a, b, spacing=1.8, size=0.95, lw=0.11, density=0.62, seed=3):
    """World-space stud grid (cube units) -> (dark, light, inner) masks.
    Every stud has the same size everywhere on the model; ~28% are partial corner marks."""
    ca, cb = np.floor(a / spacing), np.floor(b / spacing)
    present = _hash(ca, cb, seed) < density
    ja = (_hash(ca, cb, seed + 1) - 0.5) * 0.35 * spacing
    jb = (_hash(ca, cb, seed + 2) - 0.5) * 0.35 * spacing
    s = 0.5 * size * (0.85 + 0.3 * _hash(ca, cb, seed + 3))
    la = a - (ca + 0.5) * spacing - ja
    lb = b - (cb + 0.5) * spacing - jb
    ins = present & (np.abs(la) < s) & (np.abs(lb) < s)
    partial = _hash(ca, cb, seed + 4) < 0.28
    top, left = lb > s - lw, la < -s + lw
    bot, right = lb < -s + lw, la > s - lw
    dark = ins & (top | left)
    dark &= ~partial | (((top) & (la < 0.2 * s)) | ((left) & (lb > -0.2 * s)))
    light = ins & (bot | right) & ~dark & ~partial
    inner = ins & ~dark & ~light & ~partial
    return dark, light, inner


def bake(uv, pos, nrm, mat, isl, zrange, frames=None, eyes=(), size=1024, seed=5):
    T = len(uv)
    img = np.zeros((size, size, 3))
    emis = np.zeros((size, size))
    islmap = np.full((size, size), -1, np.int32)
    matmap = np.full((size, size), -1, np.int32)
    P = np.stack([uv[..., 0] * size, (1 - uv[..., 1]) * size], -1)  # pixel coords
    a_uv = 0.5 * np.abs(np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]))
    a_w = 0.5 * np.linalg.norm(np.cross(pos[:, 1] - pos[:, 0], pos[:, 2] - pos[:, 0]), axis=1)
    k = float(np.sqrt(a_uv[mat != 4].sum() / max(a_w[mat != 4].sum(), 1e-9)))  # px per cube
    for t in range(T):
        p = P[t]
        x0, y0 = np.floor(p.min(0)).astype(int) - 1
        x1, y1 = np.ceil(p.max(0)).astype(int) + 1
        x0, y0 = max(x0, 0), max(y0, 0)
        x1, y1 = min(x1, size - 1), min(y1, size - 1)
        if x1 < x0 or y1 < y0:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        q = np.stack([xs.ravel(), ys.ravel()], -1)
        v0, v1 = p[1] - p[0], p[2] - p[0]
        d = v0[0] * v1[1] - v0[1] * v1[0]
        if abs(d) < 1e-12:
            continue
        r = q - p[0]
        b1 = (r[:, 0] * v1[1] - r[:, 1] * v1[0]) / d
        b2 = (v0[0] * r[:, 1] - v0[1] * r[:, 0]) / d
        b0 = 1 - b1 - b2
        inside = (b0 >= -0.02) & (b1 >= -0.02) & (b2 >= -0.02)
        if not inside.any():
            continue
        bc = np.stack([b0, b1, b2], -1)[inside]
        w = bc @ pos[t]
        z0, z1 = zrange[t]
        h = np.clip((w[:, 2] - z0) / max(z1 - z0, 1e-6), 0, 1)
        tip = h
        if mat[t] in (5, 6) and len(eyes):  # radial coordinates on the iris / pupil
            e = min(eyes, key=lambda e: abs(e[1] - w[:, 1].mean()))
            if mat[t] == 5:
                tip = np.clip(np.hypot(w[:, 0] - e[0], w[:, 2] - e[2]) / 0.68, 0, 1)
            else:
                tip = (np.hypot((w[:, 0] - e[0] + 0.06) / 0.07, (w[:, 2] - e[2] - 0.17) / 0.09) < 1).astype(float)
        col = _shade(int(mat[t]), h, np.full(len(h), nrm[t][2]), tip)
        if mat[t] == 3 and len(eyes):  # socket: cyan glow bleeding around the eye cube
            dmin = np.min([np.linalg.norm(w - np.asarray(e)[None], axis=1) for e in eyes], axis=0)
            g = 0.85 * np.exp(-np.maximum(dmin - 0.45, 0) / 0.9)[:, None]
            col = col * (1 - g) + np.array((50, 170, 235.0))[None] * g
        if mat[t] in STUDDED:
            R = np.eye(3) if frames is None else frames[t]
            wl = w @ R.T
            nl = R @ nrm[t]
            ax = int(np.argmax(np.abs(nl)))
            if ax == 0:
                sa, sb = wl[:, 1] * np.sign(nl[0]), wl[:, 2]
            elif ax == 1:
                sa, sb = -wl[:, 0] * np.sign(nl[1]), wl[:, 2]
            else:
                sa, sb = wl[:, 1], -wl[:, 0]
            dk, lt, inn = stud_pattern(sa, sb, seed=seed + 17 * ax)
            col[inn] *= 1.03
            col[dk] *= 0.62
            col[lt] += (255 - col[lt]) * 0.33
        px = q[inside].astype(int)
        img[px[:, 1], px[:, 0]] = col
        islmap[px[:, 1], px[:, 0]] = isl[t]
        matmap[px[:, 1], px[:, 0]] = mat[t]
        if mat[t] in (2, 5):
            emis[px[:, 1], px[:, 0]] = 1.0 if mat[t] == 2 else 0.8

    filled = islmap >= 0
    # bevel-style highlight along island borders (real geometric edges on a low-poly mesh)
    band = max(2, int(round(0.07 * k)))
    edge = np.zeros_like(filled)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        for r in range(1, band + 1):
            sh = np.roll(np.roll(islmap, dy * r, 0), dx * r, 1)
            edge |= filled & (sh != islmap)
    stud_ok = np.isin(matmap, STUDDED)
    img[edge & stud_ok] += (255 - img[edge & stud_ok]) * 0.14

    # dilate into the gutters so mip/linear filtering never samples black
    for _ in range(12):
        empty = islmap < 0
        if not empty.any():
            break
        acc = np.zeros_like(img)
        cnt = np.zeros(islmap.shape)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            sh_i = np.roll(np.roll(islmap, dy, 0), dx, 1)
            sh_c = np.roll(np.roll(img, dy, 0), dx, 1)
            sh_e = np.roll(np.roll(emis, dy, 0), dx, 1)
            ok = empty & (sh_i >= 0)
            acc[ok] += sh_c[ok]
            cnt[ok] += 1
            emis[ok] = np.maximum(emis[ok], sh_e[ok])
        grow = cnt > 0
        img[grow] = acc[grow] / cnt[grow][:, None]
        islmap[grow] = 0
    return np.clip(img, 0, 255), emis, k
