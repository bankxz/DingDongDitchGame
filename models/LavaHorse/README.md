# Lava Horse (Roblox-ready)

Blocky lava horse built from the "Lava Horse" reference sheet: red lava-rock body with glowing
cracks, dark volcanic boulder armour on shoulders/hips/rump, flame mane and tail made of stud-covered
plates, dark stud hooves, black/white block eyes, dark ears.

| | |
|---|---|
| Triangles | **3,375** (< 5k): faces enclosed by other parts or never visible (render-tested from 32 directions × 8 idle/walk poses) are removed |
| Meshes / materials | 1 skinned mesh, 1 material, 1 texture (Roblox MeshPart friendly) |
| Bones | 22 (`Root`, `Torso`, `Chest`, `Hips`, `Neck`, `Head`, `Ear.L/R`, `Tail1/2`, 3 bones per leg) |
| Skin | rigid/blended weights, max 2 influences per vertex (Roblox limit is 4) |
| Rest pose | neutral square stance: legs straight and vertical, left/right symmetric (quadruped "T-pose") |
| Animations | `Idle` (120 f @ 30 fps, 4 s loop), `Walk` (32 f @ 30 fps, 4-beat in-place loop) |
| Studs | **painted into the texture, not modelled** (see `textures/stud_tile.png`) |
| Attachment | build gate: no floating parts; every mane/tail plate is buried ≥0.1 in what it grows from, every armour rock ≥0.1 into the body |

## Files
- `LavaHorse.blend` – rigged model; both actions stored (NLA tracks + fake users). Active action = Idle.
- `export/LavaHorse.fbx` – mesh + rig, rest pose (import this as the model).
- `export/LavaHorse_Idle.fbx`, `export/LavaHorse_Walk.fbx` – same rig with one baked animation each.
- `export/LavaHorse.glb` – mesh + rig + both animations (glTF alternative).
- `textures/LavaHorse_Color_1024.png` – colour atlas embedded in the FBX files (Roblox max in-game res).
- `textures/LavaHorse_Color.png` – 2048 version. `textures/LavaHorse_Emissive.png` – glow mask (optional).
- `previews/` – turnaround, reference comparisons, animation contact sheets.
- `src/` – scripts that rebuild everything from scratch (Blender 5.0 `bpy`):
  `gen_stud_tile.py` → `bake_texture.py` → `rig_animate_export.py`.

## Import into Roblox Studio
1. **File → Import 3D** → `export/LavaHorse.fbx`. Rig type is detected as a custom rig; keep
   "Import only as a model" off so bones are created. Scale: the horse is ~8 units tall in Blender –
   pick the importer's scale unit that gives you the size you want (Stud ≈ 8 studs tall).
2. The texture is embedded; if Studio doesn't apply it, set the MeshPart `TextureID` to
   `LavaHorse_Color_1024.png`.
3. Animations: open the Animation Editor on the imported model → **… → Import → From FBX Animation**
   → pick `LavaHorse_Idle.fbx`, publish; repeat with `LavaHorse_Walk.fbx`. Set both to Looped.
4. For the glow of the reference, add a `PointLight` (orange) to the body and optionally use
   `Neon`/bloom post-processing; Roblox's colour texture itself has no emission.

## Rebuild
```
pip install bpy pillow numpy          # Blender 5.0 as a Python module
python src/gen_stud_tile.py
python src/bake_texture.py            # geometry + UVs + texture bake -> src/LavaHorse_stage1.blend
python src/rig_animate_export.py      # rig, animations, exports -> LavaHorse.blend, export/*
```
