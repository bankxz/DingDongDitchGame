---
name: roblox-outfit-from-sheet
description: Build a 1:1 clothed Roblox R6 character (coats, robes, haori, kimono, hakama, capes, sleeves, boots, collars, gold trim) on the user's own R6 rig in headless Blender from a front/side/back reference sheet, part by part with the user's sign-off on each part, then paint it in the sheet's style and cut it to a game budget (8-10k tris) with baked colour + normal maps. Use this whenever Jordan sends a character/outfit reference sheet plus an R6 .blend and asks to "model this 1 to 1", "copy the reference", fix folds/flare/trim/clipping, texture it "like the reference", or lower the tri count - even if he doesn't name the skill. Also use for feedback like "looks boxy", "folds wrong", "gold trim not accurate", "it's clipping", "tri count too high".
---

# Roblox outfit from a reference sheet (R6, headless Blender)

Learnt on the Haori swordsman build (Nov 2026). Scripts that worked are in `scripts/` — reuse them, change the measured tables, don't rewrite from scratch.

## What failed first (don't repeat)
1. **Guessed shapes** ("plausible" coat/hair from memory) → "looks nothing like it".
2. **Projecting/baking the sheet onto simple shapes** → "you just baked the texture, didn't model it".
3. **Strand / blob / AI-mesh hair, AI image-to-3D (Hunyuan3D)** → lumpy, sculpted look; rejected. Hair from code is beyond reach: say so early, offer a Roblox UGC hair added in Studio, or ship without hair.
4. **Auto-traced cloud scrolls and vector-traced faces** → ragged/posterized. Hand-measured or own clean design wins.
5. Long apologetic loops. Be honest about limits in the first message, offer 2-3 concrete options.

## The process he approved
Work **one part at a time and wait for "approved"** before the next:
1 sleeves → 2 coat shape (no trim) → 2b coat trim → 3 collar + lapels → 4 kimono/obi/tassel → 5 hakama + boots → textures → face → low-poly. Commit + push after every change (Stop hook demands it).

Every check image: **sheet | model | 50% overlay** per view, registered to sheet pixels (`scripts/cmp2.py`), plus lit 3/4 renders (`scripts/shade.py`, EEVEE, two area lights) — flat Workbench hides folds. Numeric outline check per row with `scripts/silcmp.py` (aim ≤5 px).

## Registration (sheet → world)
- 1 stud = 121 px horizontally; rows: `z = 4+(372-y)/130` above y=632, `z = (958-y)/163` below (legs are drawn longer than R6). Front: `x=(280-px)/121`; back: `x=(px-1179.5)/121`; side: `y=(722-px)/121`. Re-measure for a new sheet (head top, shoulder line, waist, boot sole).
- Measure edges row-by-row from the foreground mask / darkest outline pixel, then **fit a smooth curve** (cubic polyfit with outlier rejection) — raw rows make lumps.

## Shape rules from his corrections
- **Nothing boxy.** Sleeves: measured curved profile on both axes + gently bulged faces (rounded-rect with bowed sides). Coat: built from **rounded fold lobes** (crest/valley list per side) not flat planes with creases; folds fade in from the waist (smoothstep) and deepen to the hem; hem scalloped (valleys hang lower).
- Panels = **one continuous shell per side** (separate panels left a seam crack).
- When he points at a bulge and says "invert", make it a clear **hollow** (radial inset ~0.1-0.19), check from his exact camera angle — a small change "looks the same" to him.
- Lapels are **turned-back folded flaps** (gold roll at the opening edge, purple lining face, gold outer edge, notched point) welded into the collar, not flat stripes.
- Pants flare **slightly and evenly** in x, +y and -y. Boots = R6 foot block +0.03 all round, gold band wrapping continuously.
- Gold trim must **wrap continuously** (over the arm top, round the neck, rails up into the neck binding) — gaps get rejected.
- Run the **clipping check** (`scripts/unclip.py`): pull under-layers inside the coat by raycast from the body axis; skip the front opening.

## Trim / clouds
- Raised bevelled strips (`strip()` in `common.py`) laid on the surface by raycasting from the view; for the folded coat use a **fold-free proxy** to place, then drop radially onto the real coat.
- Complex scrolls: if tracing looks bad, he accepts **"make your own design"** — `motif2d.py` + `clouds_design.py` (union-of-circles outline, spiral curls, plate inset) wrapped by surface arc-length.

## Textures (what he means by "the reference's style")
- Not projection, not generic marble. Paint per material in-shader (`p7_paint.py`): cel ramp (shadow/mid/light, linearised palette), AO in creases, wispy Voronoi-edge lavender cracks + soft clouds for marble, darker edges on gold. Bake EMIT to 2048 per piece.
- **No neon pieces** unless asked — glow parts become painted purple.
- Faces: drawing from code looks worse than the sheet. Best: give him a ChatGPT prompt (separate decals: neutral, half/full blink, mouths A, E/I, O/U, M/B/P, F/V; transparent 1024; features fixed in place; no skin fill).

## Budget (he expects 8-10k tris total)
Model freely at high detail, then `lowpoly.py`: per piece decimate (collapse) to a target (coat 3.3k, kimono 950, collar 800, legs 720, sleeves 520, tassel 300), smart-UV, bake **selected-to-active** DIFFUSE colour + tangent NORMAL from the high-poly (trim/bands merged in). Result 7.8k gear + 1.1k rig, visually identical. Studio: MeshPart + SurfaceAppearance (ColorMap/NormalMap). Roblox limit ~20k tris per mesh — report per-piece tris.

## Environment notes
- `pip install bpy` (5.x) in a venv; `apt-get install libegl1 ...` for Workbench renders; run with `python -I`.
- `rend.py` camera helper: az 180 = front, 0 = back, 270 = side (+y image-left).
- Background long bakes (>10 min) with `run_in_background`; never a second copy.
- Don't export FBX or touch Studio until he asks. Always say "not tested in Studio".
