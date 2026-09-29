# Ancient Dragon (Roblox)

Stud-textured low-poly dragon, rigged, with idle and walk animations.

| | |
|---|---|
| Triangles | 4,430 (hidden faces removed; checked in rest pose and across both animations) |
| Meshes | 8 skinned meshes, one per material: Dark, Gold, Tan, Bone, Glow, Eye, Mouth, Membrane |
| Rig | 48 bones, max 2 influences per vertex |
| Animations | `Dragon_Idle` (120 frames @ 30 fps, 4 s loop), `Dragon_Walk` (48 frames @ 30 fps, 1.6 s in-place loop) |
| Textures | 256px stud tiles + one shared stud normal map, 512px wing membrane, eye and glow sheets (all embedded in the FBX) |

## Files

- `AncientDragon.fbx`: rigged model in rest pose. Import this one as the model.
- `AncientDragon_Idle.fbx`, `AncientDragon_Walk.fbx`: same rig with one baked animation each.
- `AncientDragon.blend`: source scene (actions in NLA tracks `Dragon_Idle` / `Dragon_Walk`).
- `textures/`: every texture as separate PNGs, for SurfaceAppearance.

## Importing into Roblox Studio

1. **Model:** Home → Import 3D → `AncientDragon.fbx`. Keep "Import as rig" / skinned mesh on. The dragon is about 24 studs nose to tail. If it comes in at the wrong size, change the importer's scale unit to centimeters.
2. **Glow parts:** the importer doesn't carry emission, so set the `Dragon_Glow` and `Dragon_Eye` MeshParts to `Material = Neon` (or keep their texture and add a PointLight) for the cyan glow.
3. **Stud relief (optional):** add a `SurfaceAppearance` to a stud MeshPart, with `ColorMap` set to its `Dragon_*_Stud.png` and `NormalMap` set to `Dragon_Stud_Normal.png`.
4. **Animations:** open the Animation Editor on the imported rig → ⋯ → Import → From FBX Animation → pick `AncientDragon_Idle.fbx`, then publish. Repeat for `AncientDragon_Walk.fbx`. Both loop seamlessly, so tick Looping before publishing.

## Rebuilding

The model is fully procedural. The scripts are in `tools/blender/` in the repo (they need `pip install bpy`):

```
python3 tools/blender/make_dragon_textures.py assets/models/AncientDragon/textures
python3 tools/blender/build_ancient_dragon.py
python3 tools/blender/export_dragon_fbx.py
```
