# Lava Hellhound (Roblox-ready retexture)

Your Hellhound model retextured in the same lava style as the Lava Scorpion. **The geometry, rig and weights are unchanged**: same armature and mesh names, all 34 bones, 6,529 verts, 11,310 tris, same vertex groups and dimensions (verified by re-importing both FBX files). Only the UVs, texture and material changed.

| Original colour | Parts | Lava version |
|---|---|---|
| Grey stone | heads, necks, body, upper legs | Charcoal rock, Roblox studs, lava seams and cracks |
| Red-orange | lower legs, paws, chest, head accents | Magma rock: deep red, studded, glowing seams |
| Flame swatches | mane, back, rump and tail flames | Studded hot tones, red → orange → yellow |
| Cream | claws, teeth, horns | Hot yellow |
| White / red | eyes | Glowing yellow eyes with a hot red-orange centre |
| Deep red | mouth insides | Glowing ember maw |
| Charcoal / black | brows, lids, nose | Dark rock |
| Bevel strips | block edges | Ember edges, so lava shows between the blocks |

## Files
- `export/LavaHellhound.fbx`: the rig and mesh with the lava texture embedded. Import this into Roblox with Import 3D. Existing animations made for the original rig still work, because the bone names are identical.
- `export/LavaHellhound.glb`: alternative glTF version.
- `LavaHellhound.blend`: the Blender source.
- `textures/`: `LavaHellhound_Color.png` (glow baked in), plus the optional `_Normal.png` stud normal map for a `SurfaceAppearance` and the `_Emission.png` glow mask.
- `validation/`: renders from six views, plus `before_after.png`.
- `source/`: `make_textures.py`, `retexture.py`, `export_roblox.py`, `render_hh.py` and your original FBX.

For the glow in game, turn on `Lighting.Bloom`.

## Rebuilding
```bash
cd source && python3 make_textures.py && python3 retexture.py && python3 export_roblox.py
```
Stud normal and AO maps: [dudeax/Roblox-HD-Studs](https://github.com/dudeax/Roblox-HD-Studs), MIT licence.
