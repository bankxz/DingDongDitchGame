# Ancient Dragon (Roblox)

Stud-textured low-poly dragon, rigged, with idle and walk animations.

| | |
|---|---|
| Triangles | 3,994 (hidden faces removed; checked in rest pose and across both animations) |
| Meshes | 8 skinned meshes, one per material: Dark, Gold, Tan, Bone, Glow, Eye, Mouth, Membrane |
| Rig | 48 bones, max 2 influences per vertex |
| Animations | `Dragon_FlyIdle`: hovering flight (40 frames @ 30 fps, 1.33 s loop). `Dragon_Fly`: flying forward in place (28 frames @ 30 fps, 0.93 s loop). Both lift the body 4 studs off the rig origin. |
| Textures | 256px stud tiles + one shared stud normal map, 512px wing membrane, eye and glow sheets (all embedded in the FBX) |

## Files

- `AncientDragon.fbx`: rigged model in rest pose. Import this one as the model.
- `AncientDragon_FlyIdle.fbx`, `AncientDragon_Fly.fbx`: same rig with one baked flight animation each.
- `AncientDragon.blend`: source scene (actions in NLA tracks `Dragon_FlyIdle` / `Dragon_Fly`).
- `textures/`: every texture as separate PNGs, for SurfaceAppearance.

## Importing into Roblox Studio

1. **Model:** Home → Import 3D → `AncientDragon.fbx`. Keep "Import as rig" / skinned mesh on. The dragon is about 24 studs nose to tail. If it comes in at the wrong size, change the importer's scale unit to centimeters.
2. **Glow:** the runes (`Dragon_Glow`), eyes (`Dragon_Eye`) and wing webbing (`Dragon_Membrane`) are emissive in Blender. FBX can't carry emission into Studio, so re-apply it there:
   - `Dragon_Glow` and `Dragon_Eye`: set `Material = Neon`.
   - `Dragon_Membrane`: to keep the painted rune pattern, add a `SurfaceAppearance` with `ColorMap = textures/Dragon_WingMembrane.png`. If your Studio version shows emissive properties on SurfaceAppearance, use the same image as the emissive map. For a plain glow instead, set it to `Neon` with `Color = (20, 190, 215)`.
3. **Stud relief (optional):** add a `SurfaceAppearance` to a stud MeshPart, with `ColorMap` set to its `Dragon_*_Stud.png` and `NormalMap` set to `Dragon_Stud_Normal.png`.
4. **Animations:** open the Animation Editor on the imported rig → ⋯ → Import → From FBX Animation → pick `AncientDragon_FlyIdle.fbx`, then publish. Repeat for `AncientDragon_Fly.fbx`. Both loop seamlessly, so tick Looping before publishing. Play `Dragon_FlyIdle` while hovering and `Dragon_Fly` while your script moves the dragon; both are in place, so your game script handles the actual movement and altitude.

## Rebuilding

The model is fully procedural. The scripts are in `tools/blender/` in the repo (they need `pip install bpy`):

```
python3 tools/blender/make_dragon_textures.py assets/models/AncientDragon/textures
python3 tools/blender/build_ancient_dragon.py
python3 tools/blender/export_dragon_fbx.py
```
