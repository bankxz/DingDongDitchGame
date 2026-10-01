---
name: roblox-creature-from-reference
description: End-to-end, scripted (headless bpy) build of a stylized, game-ready creature for Roblox from concept art / reference sheets / in-game screenshots — sculpted organic body, painted texture atlas with emissive glow, accessories (harness, ropes, ornaments), fur tufts, eyes, rig, Idle/Run/Sleep loops and FBX + SurfaceAppearance export under a triangle budget. Use this whenever the user wants a creature, pet, mount, monster, fox/wolf/kitsune/dragon or other animal-like character modeled, textured, rigged or animated for Roblox (or any low-poly game engine) from reference images, and whenever they iterate on such a model with feedback like "make X look like the reference", "fix the seam", "texture is blurry", "cheek fur / ears / eyes / harness wrong" — even if they never say "pipeline" or name Blender.
---

# Roblox creature from reference

A procedural Blender pipeline that turns reference art into a sculpted, textured,
rigged, animated creature, plus the review loop that gets it to match what the user
actually wants. Everything is Python (pip `bpy` 4.2 or `blender -b -P`), so every
change is a code edit + rebuild + render, and every round is reviewable and
reproducible.

Read `references/pipeline.md` for the code patterns (loft builder, sculpt pipeline,
painter, eye sealing, accessory seating, rig grounding, FBX settings). Helper scripts
are in `scripts/`.

## The working loop (most important part)

The user judges by eye, in short messages, often with a cropped screenshot. The work
that succeeded followed this loop every round:

1. **Look at the reference crop the user sent, enlarged** (`scripts/ref_crop.py`
   upscales 3-6x). Describe the shape to yourself in words before editing:
   "one big curved tuft + 3 small spikes", "one tilted halo ring of bundled ropes,
   ends tie into the collar". Most failed rounds came from building what a phrase
   suggested ("fan of spikes", "double loop") instead of what the image showed.
2. **Change only what was asked.** Users say "do not redesign", "no tail changes".
   Keep every other constant untouched so earlier approved work survives.
3. **Rebuild the model stage only** (no rig) — ~2 min — and render the affected
   area close up *and* the full model (a fix in one place often breaks another:
   moving the head moves ears/halo/markings).
4. **Self-check the render against the reference before showing it.** If it is
   visibly off (horn-like tuft, egg-shaped eye, blob where spikes should be), do
   another pass yourself. Say what you changed on the second pass.
5. **Send a labeled sheet** (`scripts/labeled_sheet.py`): before | after, the
   user's reference next to the matching view, close-ups of the asked area.
6. **Commit + push every round** with a message listing the fixes; archive the
   previous round's renders into `validation/vNN/`. A stop hook will complain
   about untracked renders otherwise.
7. Report in plain words: what changed for each request, tri count, anything
   still imperfect and the one-line knob that adjusts it.

Do not rig before the user approves the model — they will say so ("rig and anims
now"). Rigging a model that keeps changing wastes the rig.

## Build order

```
reference analysis -> closed source lofts -> voxel remesh -> sculpt displacement
-> mirror (exact symmetry) -> symmetric decimate -> transfer part/params/weights
-> seam unwrap + texel-density scaling -> accessories (separate pieces) seated on
the sculpted surface -> eyes sealed into sockets -> join -> pack UVs -> paint atlas
(supersampled) -> 6 material slots -> [after approval] rig -> actions -> FBX
```

Key decisions and why:

- **Organic body = closed forms fused by a voxel remesh**, then displaced along
  normals for fur and sockets. Separate primitive "clumps" stuck on a body always
  read as seams and black shards; fused forms don't.
- **Mirror modifier (bisect X) after sculpting + decimate with symmetry** gives exact
  left/right symmetry; mirror texture parameters too (right side th -> -th).
- **Thin pointed things stay separate pieces** (cheek spikes, claws, ear-rim
  spikes): the remesh at body voxel size melts them into blobs. Broad tufts that
  must blend into the skin go *into* the remesh.
- **Seams where a piece meets the skin are fixed by sculpting the skin up to meet
  it** (a Gaussian displacement bump on the head/cheek before the remesh), not by
  adding a filler shape on the piece — a filler shape always shows its own outline.
  Then paint the piece's root with exactly the skin's colour, lighting and
  normal-map height so the texture has no step either.
- **Triangle budget**: give accessories their exact count and let the body
  decimate to whatever is left (`body_target = BUDGET - acc_tris - eye_tris`).

## Texture lessons

- Paint procedurally from per-corner loft parameters (t along the part, th around
  it) and world positions, rasterised in UV space at **2x supersampling** then
  box-filtered down; anti-alias masks with narrow smoothsteps.
- "Blurry/pixelated" is almost always UV density, not resolution: normalise every
  island to world area x per-part importance (faces/ears/eyes 2-3x), use seam-based
  angle-based unwrap (few big islands), check texels/unit per part
  (`references/pipeline.md` has the measurement snippet).
- When a mesh is decimated, paint shapes (ear rims, eye frames) from *metric
  distances to an outline measured on the final mesh*, not from loft params — loft
  params get noisy after remesh/decimate.
- Sample palette colours from the user's reference images
  (`scripts/sample_palette.py`) instead of guessing; users notice hue drift.
- One shared emissive mask drives the glow; eyes get a hotter emission slot.
- Watch for variable-name shadowing in big paint functions (e.g. reusing `hgt`
  for a local destroyed the height map) — use distinct local names.

## Eyes

Build the lens as rings projected onto the final sculpted surface with a small
lift, plus a buried "skirt" ring 7% larger and below the surface so no gap shows at
grazing angles. Share one outline function between the lens builder and the painter
so the painted liner/frame hugs the lens exactly. Watch angle wrap (2pi->0) inside
faces when painting by angle — compute painter coordinates from world position in
the eye frame instead. Keep shape edits to the outline function (length, upper/lower
lid curvature, corner pinch).

## Accessories (harness, ropes, ornaments)

Build them on the source surface, then **seat** them after the sculpt: rope rings
move to surface + normal x (radius + gap), offsets smoothed along the rope; rigid
ornaments move as one block. Loops that stand off the body (halo rings) are rigid
groups anchored at their lowest point. Make their ends *continue into* the rest of
the harness (collar ties) — floating ends look disconnected.

## Rig and animation

- Bones from the same anatomy constants as the mesh; measure positions of seated
  pieces (tassels) from the mesh's vertex groups.
- Skin weights: transfer from source forms during the sculpt (nearest-point blend),
  then `vertex_group_limit_total(4)` + `normalize_all`. Drop non-bone groups.
- Poses are functions of phase -> per-bone world-axis rotations; bake every frame,
  linear keys, frame 0 == frame N for seamless loops.
- **Ground on the paws, not the whole mesh** — tails that dip below the floor will
  otherwise lift the creature. Sleep grounds on the whole body.
- **Aim chains with an FK-aware helper** (`set_dir`: convert the target world
  direction through the parents' *posed* rotation). Aiming each bone from its rest
  orientation ignores the parent pose, so curls and legs end up wrong.
- Rigid accessories that should move in a pose (a halo loop lying down when asleep)
  get their own bone; blend the weight into the parent where the piece attaches.
- Ask which sleep style the user wants and follow their sheet: e.g. "head on paws,
  straight body, tails in a layered fan behind (low ones on the ground, upper ones
  arching, tips curling up)" vs a curled fox.
- Sleep (curled fox): body flat and curved into a C, tails steered bone-by-bone along
  a curled path on the ground round one side so the tips lie by the face, chin on
  the ground between forward-stretched front legs, hind legs folded *beside* the
  haunches. Folding legs straight under the body sinks them into the belly — keep
  them on the ground and outside the torso. Close eyes with small eye bones that
  sink the lenses into the sockets (Roblox animations can't scale bones).
- Tails: 4 bones each; "majestic" motion = a wave travelling base->tip (later bones
  lag and swing wider), phase offset per tail so the fan ripples, slow fan
  spread/lift, a small 2nd harmonic; integer frequencies keep loops seamless.
- Review with contact sheets (`scripts/anim_contact_sheet.py`), side + 3/4, 4-6
  frames per action, before exporting.

## Export for Roblox

- Scene unit scale 0.01, FBX `apply_scale_options='FBX_SCALE_UNITS'`,
  `axis_forward='-Z', axis_up='Y'`, `add_leaf_bones=False`,
  `use_armature_deform_only=True`; model FBX in rest pose with embedded textures,
  one FBX per animation (`path_mode='STRIP'` so textures aren't copied each time).
- Re-import every FBX in a clean scene and check bones, tris, materials, action
  frame ranges, max influences.
- SurfaceAppearance texture maps can only be set in Studio (command bar / plugin),
  not by game scripts — ship a command-bar script plus a runtime Animator module.
  Mention Lighting BloomEffect for the glow.

## Validation loop tooling

`scripts/labeled_sheet.py` (labeled image grids), `scripts/ref_crop.py`
(enlarge user crops / reference panels), `scripts/sample_palette.py` (reference
colours), `scripts/anim_contact_sheet.py` (per-action frame grids from a .blend).
Renders: Cycles CPU, Standard view transform, 24-64 samples, small resolution for
iteration; background long renders (>10 min) and tell the user they're running.
