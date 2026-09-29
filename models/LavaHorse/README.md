# Lava Horse (Roblox-ready)

Blocky lava horse built from the "Lava Horse" reference sheet: red lava-rock body with glowing
cracks, dark volcanic boulder armour on shoulders/hips/rump, glowing flame mane and tail made of
stud-covered plates, dark stud hooves, black/white block eyes, dark ears.

| | |
|---|---|
| Triangles | **3,856** (< 5k); faces fully enclosed by other parts are removed (render-verified, no holes) |
| MeshParts | 3 skinned parts on one rig, each with its own 1024 texture + emissive mask: **Body** (lava skin, nose, eyes), **Armor** (rocks, ears, hooves), **Flames** (mane + tail) |
| Bones | 22 (`Root`, `Torso`, `Chest`, `Hips`, `Neck`, `Head`, `Ear.L/R`, `Tail1/2`, 3 bones per leg) |
| Skin | rigid/blended weights, max 2 influences per vertex (Roblox limit is 4) |
| Rest pose | neutral square stance: legs straight and vertical, left/right symmetric (quadruped "T-pose") |
| Animations | `Idle` (120 f @ 30 fps, 4 s loop), `Walk` (32 f @ 30 fps, 4-beat in-place loop) |
| Studs | **painted into the texture, not modelled** (see `textures/stud_tile.png`) |
| Attachment | build gate: no floating parts; every mane/tail plate is buried ≥0.1 in what it grows from, every armour rock ≥0.1 into the body |

## Files
- `LavaHorse.blend` – rigged model (3 meshes on `LavaHorseRig`); both actions stored (NLA tracks + fake users).
- `export/LavaHorse.fbx` – meshes + rig, rest pose (import this as the model).
- `export/LavaHorse_Idle.fbx`, `export/LavaHorse_Walk.fbx` – same rig with one baked animation each.
- `export/LavaHorse.glb` – meshes + rig + both animations (glTF alternative).
- `textures/LavaHorse_<Part>_Color.png` – 1024 colour maps (embedded in the FBX; `_2048` versions too).
- `textures/LavaHorse_<Part>_Emissive.png` – 1024 grayscale **emissive masks** (glow: mane/tail, lava cracks).
- `previews/` – turnaround, reference comparisons, close-ups, animation contact sheets.
- `src/` – scripts that rebuild everything (Blender 5.0 `bpy`).

## Import into Roblox Studio
1. **File → Import 3D** → `export/LavaHorse.fbx`. Rig type is detected as a custom rig; keep
   "Import only as a model" off so bones are created. You get three MeshParts sharing one rig.
   Scale: the horse is ~8 units tall in Blender – pick the importer's scale unit that gives you the
   size you want (Stud ≈ 8 studs tall).
2. Colour textures are embedded; if Studio doesn't apply one, set that MeshPart's `TextureID` to
   its `textures/LavaHorse_<Part>_Color.png`.
3. Animations: open the Animation Editor on the imported model → **… → Import → From FBX Animation**
   → pick `LavaHorse_Idle.fbx`, publish; repeat with `LavaHorse_Walk.fbx`. Set both to Looped.
4. **Glow (mane, tail, lava cracks)** – Roblox takes glow from a SurfaceAppearance emissive mask.
   For each MeshPart insert a **SurfaceAppearance**, set `ColorMap` to its
   `textures/LavaHorse_<Part>_Color.png` and `EmissiveMask` to `textures/LavaHorse_<Part>_Emissive.png`.
   Suggested: Flames `EmissiveStrength` 3–4, Body 2 (cracks only), `EmissiveTint` white; add a
   `BloomEffect` under Lighting for the halo. (Armor's mask is black – it doesn't glow.)

## Rebuild
```
pip install bpy pillow numpy          # Blender 5.0 as a Python module
python src/gen_stud_tile.py
python src/bake_texture.py            # geometry + attachment gate + hidden-face cull -> src/LavaHorse_stage1.blend
python src/rig_animate_export.py      # rig, animations, visibility cull, 3-part split, per-part bake, exports
```
