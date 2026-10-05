# Bone Dragon – Roblox stud-style model

Built from `reference/bone_dragon_reference.webp` with the stud-style pipeline (`build.py`, fully scripted).

| | |
|---|---|
| Triangles | **3,246** (body 2,894 + glow 352) – under the 5k budget |
| Bones | 40 (Root → Torso → Chest/Neck/Head/Jaw, 5 tail, 4 legs × 3, 2 wings × 8) |
| Weights | max 2 influences per vertex (Roblox limit is 4) |
| Texture | 1024² atlas; the stud pattern is **texture only** (no stud geometry) – stud tiles from [dudeax/Roblox-HD-Studs](https://github.com/dudeax/Roblox-HD-Studs) (MIT, vendored in `tools/studs`) |
| Rest pose | "T-pose" equivalent: wings fully spread, legs apart and straight, mouth slightly open |
| Animations | `Idle` (90 frames, 30 fps, loops) and `Walk` (40 frames, in place, loops) |

## Files (`out/`)
* `BoneDragon.fbx` – mesh + rig + both clips → **Avatar ▸ Import 3D** (set *Scale Unit = Studs*, rig type *Custom/Rigged*).
* `BoneDragon_Idle.fbx`, `BoneDragon_Walk.fbx` – one clip each → Animation Editor ▸ ⋯ ▸ Import ▸ From FBX Animation.
* `BoneDragon.glb` – same model for other viewers.
* `../BoneDragon.blend` – source scene; `../textures/Color.png` + `Normal.png` – atlas (colour has studs baked in; the normal map is optional for a `SurfaceAppearance`).

Two MeshParts are imported: **Body** (bone, horns, membranes) and **Glow** (flames, ember core, eyes, chest gem).
Set the Glow part's `Material` to `Neon` (or add a Bloom effect in Lighting) for the fire look. Play animations client-side on an `AnimationController` + `Animator` with `Looped = true`.

## Rebuild
```
pip install bpy==4.2.0 pillow numpy
python3 build.py                       # textures + BoneDragon.blend
python3 tools/export_roblox.py BoneDragon.blend out BoneDragon
```
Checks used: `tools/check_normals.py` (no inside-out geometry – the 2 "open islands" it lists are the two-sided wing membranes), `tools/check_clips.py` (root drift 0, loop seam 0), `tools/verify_export.py` (tris, bones, weights, textures embedded).

## Reference vs model
`renders/compare_*.png` show the reference panel next to the model render for every view; `renders/contact_*.png` are the animation contact sheets.

### What still differs from the reference (honest list)
This is a faithful low-poly **stylisation** of the reference, not a pixel copy:
* The reference is a smooth, high-detail render; the model is 3.2k flat-shaded triangles with a stud texture, so facets are coarser (skull plates, knuckles, claws).
* Bones are chunkier/blockier than the reference's rounded bone shapes, and the rib cage is 5 ribs rather than the reference's rounded rib bands.
* Wing membrane is 13 triangles per wing with the glow painted into the texture; the reference has softer, more detailed scalloping.
* The glow (flames, ember, eyes) is texture + a separate Neon-able part; Roblox has no soft bloom like the concept render.
* Reference 3/4 panels use perspective, so exact angles cannot be matched 1:1 with the orthographic comparison views.
