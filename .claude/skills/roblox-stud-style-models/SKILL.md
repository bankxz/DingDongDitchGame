---
name: roblox-stud-style-models
description: Build stud-style (classic Roblox "studs" look) low-poly models for Roblox in headless Blender - creatures, pets, mounts, bosses, props - from concept art or reference sheets, with the stud pattern as a TEXTURE (not geometry), a triangle budget, a Roblox-ready rig and looping Idle / Walk / flying clips exported as FBX. Use this whenever the user wants a Roblox model "with studs", "stud texture", "lego/brick look", a blocky voxel-style creature or pet, or attaches stud-textured example screenshots - and whenever they iterate on such a model ("eyes look like a block", "add a bevel to the brow", "gap between horn and head", "make the ice look like the reference", "studs too strong") even if they never say "skill", "Blender" or "pipeline".
---

# Roblox stud-style models

You are turning reference art into a **game-ready Roblox asset**: a flat-shaded low-poly mesh
whose surfaces carry the Roblox stud pattern **in the texture**, a simple rig with ≤ 4 weights per
vertex, and looping animations, exported so Roblox Studio's 3D Importer and Animation Editor take
it without fuss. The bundled scripts do the mechanical parts; your job is reading the reference
closely, building the shapes, and iterating with the user.

Everything below came from a real build (a 3-headed ice dragon pet, ~4.9k tris) and the user's
corrections along the way. The corrections are the most valuable part - they are in
`references/lessons.md`. **Read it before modelling and again before each feedback round.**

## 0. Environment (headless)

- If `blender` isn't installed, `pip install bpy==4.2.0 pillow numpy` (needs Python 3.11);
  download.blender.org may be blocked by the network policy while PyPI isn't.
- Stud source textures: `git clone https://github.com/dudeax/Roblox-HD-Studs` (MIT, credit it).
  Don't model studs as geometry - it wastes the whole triangle budget and the user expects a texture.
- Keep the build fully scripted (one `build.py` that regenerates everything). Iterating on
  feedback then means editing numbers and re-running, and the user can rebuild later.

## 1. Read the reference before touching Blender

Concept sheets usually have front / side / back / top views plus **detail close-up panels**
(head/eye, claws, ice, armour) and a **palette strip**. Before modelling:

1. Crop every view and every close-up at high zoom (PIL `crop` + `resize`, view them). Detail
   panels decide the look of eyes, claws, crystals - the full views are too small to read them.
2. Sample the palette swatches' exact hex values and use them in the atlas config.
3. Write down proportions in model units from the orthographic-ish views: head width vs neck
   width, snout width vs skull width, leg thickness, paw width, where heads sit, wing span.
   Typical misses on a first pass: heads too small, legs too thin, crystals too small/sparse,
   snout too wide. Measure these explicitly instead of guessing.
4. Decide the stud size: studs read well at about **1/5 of a head width** (0.45 studs on a
   ~12-stud-tall creature). Too small and they turn into noise at game distance.

## 2. Atlas (texture) - `scripts/make_stud_atlas.py`

Copy `assets/atlas_config_example.json`, set the palette and slots, run:

```
python3 scripts/make_stud_atlas.py <Roblox-HD-Studs> atlas_config.json textures/
```

- **studs** swatches bake stud relief + AO into the colour (works with a plain `TextureID`) and
  write a matching normal atlas (optional `SurfaceAppearance`). `stud_strength` (0-1) sets how
  strongly the studs show; 0.5 was preferred over full strength. `top_tint` lightens stud tops
  (navy studs with royal-blue tops read like the reference's blocks).
- Smooth swatches (`gradient`, `gold`, `flat`) for teeth, claws, mouth, gold trim - studs on
  teeth or claws look wrong.
- `crystal`: saturated cyan-blue facets lightening to the tip, every facet edge traced by a
  glowing line. Its lines match the two shard UV layouts in `stud_kit.shard`.
- `eye`: white-hot glow, iris, slit pupil, painted **pre-squashed** by `aspect` (eye surface
  width / height) so the iris reads round on the model.
- Keep it 1024² - Roblox downsizes bigger textures anyway.

## 3. Geometry - `scripts/stud_kit.py`

Import it in your build script (see its docstring). Conventions: Z up, model faces −Y, its left
is +X, **1 unit = 1 stud**. Every face carries an atlas slot; every vertex carries bone weights,
so rigging needs no auto-weights.

Toolbox and when to reach for each:

| Need | Use |
|---|---|
| bodies, necks, tails, limbs | `loft` (8 sides for bodies, 6 for limbs, flat shading) with a `color(normal, centre, ring)` rule, e.g. belly white where `n.z < -0.45` |
| blocky heads, paws, plates | `box` (taper, per-face slot overrides) |
| any block that needs a **big bevel on one edge** (brows, cheek plates) | `bevel_prism` - cut that corner off the outline |
| ice / crystal spikes | `shard` (4-tri blade by default, `hero=True` 12-tri for the few big ones), `cluster` for fans |
| horns, teeth, toe gems | `solid_spike` / `tooth` |
| claws | `claw` (chamfered, forward then down, blunt tip) + `chevron` trim |
| eyes | `eye_lens` inside a socket (see lessons) |
| gems | `gem_plate` |
| wing membranes | `two_sided_sheet` |

Put glowing parts (ice, eyes, gems) in a **separate `MeshAcc(..., glow=True)`**: it becomes its
own MeshPart in Roblox, so the user can set it to Neon/Glass/Transparency without touching the
body. `glow=True` also makes shards broad and flat like reference ice.

Keep a **triangle ledger** (`acc.tris()` printed every build). When the budget is tight, convert
filler crystals to 4-tri blades and spend the savings on density; don't drop silhouette pieces.

## 4. Rig

- Bones by construction (`build_armature`): Root at the origin on the ground → Torso → Pelvis;
  chains for necks/heads/jaws, legs (upper, lower, foot), wings (3 segments), tail (4-6).
  Weight each primitive rigidly or blend two bones along lofts (`W(a, b, t)`) - ≤ 2-3 influences,
  well under Roblox's 4.
- Rest pose = the "T-pose" equivalent: limbs straight and apart, wings spread clear of the body,
  mouths may stay open. Nothing should touch another limb.

## 5. Animation - `scripts/anim_kit.py`

- Write each clip as `pose_fn(f, n)` driven by `S(f, n, phase)` so frame n == frame 0 (seamless).
- Ground clips: legs on temporary IK targets so feet **plant**; `bake_clips` samples with IK live
  then writes plain FK keys and deletes the IK bones (Roblox imports constraints badly).
- Flying clips (`flying=True`): IK off, **Root never moves** - lift the Torso inside the
  animation (~2-2.5 studs), wing beats via `flap(w)` with each wing segment lagging the previous
  (≈0.08 of a beat), body bob synced just after the downstroke, legs tucked, tail as a hanging/
  streaming wave, heads counter-rotated to stay steady. Keeping Root still means the pet's
  CFrame and collision stay on its pen floor, so a flying idle costs the same as a standing one.
- Typical set: Idle (90 f), Walk (40 f, in place), FlyIdle (60 f), FlyWalk (40 f) at 30 fps.

## 6. Checks before every delivery (these caught real bugs)

```
python3 scripts/check_normals.py model.blend     # Roblox back-face culls: 0 inside-out islands
python3 scripts/check_clips.py   model.blend     # root drift 0, lowest point ~0 on ground / >1 flying, loop seam 0
python3 scripts/export_roblox.py model.blend out Name
python3 scripts/verify_export.py out             # tris, bones, max weights, clips, images NOT empty
python3 scripts/render_views.py  model.blend renders   # + CAM=... close-ups matching reference panels
python3 scripts/side_by_side.py  compare.png ref.png render.png ...
```

- `images []` in verify = the FBX has no embedded texture (relative image path). Fix before sending.
- Cycles renders both faces, so a render can look fine while Roblox shows holes - trust
  `check_normals`, not the render.
- Make a contact sheet per clip (8 frames, side + 3/4) and look at it before calling motion done.

## 7. Delivery

- Outputs: `Name.fbx` (mesh + rig + all clips → Avatar/3D Importer), one `Name_<Clip>.fbx` per clip
  (Animation Editor → Import → From FBX Animation), `Name.glb`, the `.blend`, textures, scripts,
  a README with importer steps: **File Dimensions / Scale Unit = Studs**, glow part → Neon or
  Glass, animations played client-side on an `AnimationController` + `Animator`, `Looped = true`.
- Zip **outside the repo** (scratchpad) so no untracked files are left; file uploads cap at
  **30 MiB** - exclude validation renders if the zip gets close.
- Show the user side-by-side comparisons with the reference, not just renders.
- Be honest: a <5k-tri textured model is a faithful stylisation of a high-detail voxel render,
  not a pixel copy. Say what still differs and offer the trade-off (more tris vs fidelity).

## 8. Feedback rounds

Each round: crop the user's screenshot and the matching reference panel, identify the exact part,
fix it in the build script, rebuild, rerun §6, render the **same camera angle** as the screenshot
or reference panel, send the side-by-side, commit/push if working in a repo.
See `references/lessons.md` for the recurring corrections and how they were solved, and
`references/roblox-notes.md` for importer, performance and pet-specific notes.
