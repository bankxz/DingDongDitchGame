# Lava Horse (Roblox)

- `fbx/LavaHorse.fbx`: rigged model (rest pose). Import with Studio's 3D Importer (Rig: Custom).
- `fbx/LavaHorse_Idle.fbx` (91 frames @30fps, loops), `fbx/LavaHorse_Walk.fbx` (37 frames @30fps, loops):
  Animation Editor > Import > From FBX.
- `textures/LavaHorse_<Material>_Color.png` (+ `_Normal.png` for the studded parts). Both are embedded in the FBX.
  For the raised-stud look in Studio, put the Color + Normal maps in a SurfaceAppearance on each MeshPart.
- 1 Blender unit = 1 stud; about 7.1 studs tall to the ear tips.
- **3,980 triangles total** (budget < 5k). See `stats.json`.

| Part | Tris | Roblox material |
|---|---|---|
| Body_Lava | 524 | SmoothPlastic + SurfaceAppearance (studded red lava body, painted glow + veins) |
| Lava_Cracks_Neon | 196 | Neon (orange-yellow) |
| Mane_Neon | 672 | Neon |
| Tail_Neon | 868 | Neon |
| Hooves_Dark | 176 | SurfaceAppearance (dark studded hooves) |
| Armour_Volcanic | 1496 | SurfaceAppearance (dark rock chunks) |
| Eyes | 48 | texture (white eye plate + black pupil plate) |

Rig: Root > Hips > Spine > Chest > Neck > Head > Jaw; Mane_1-3; Tail_1-3; per leg Upper / Lower / Hoof (x4).
Skinning is rigid (every face follows exactly one bone): blocky segments never stretch or collapse.

## Topology
Every piece is a closed, planar chamfered block (quads + corner tris; no n-gons, no degenerate faces, no loose
verts). Pieces whose end caps are buried in a neighbour (legs, neck, barrel, flame blades) chamfer only their long
edges (28 tris instead of 44), so the silhouette is unchanged. The few quads that a taper would twist are split
into two planar tris. Lava-crack strips are single floating quads (decals). Check with `source/topo.py`.

## Rebuild (Blender 5.x or `pip install bpy`)
```
cd source
python build.py    # meshes, UV atlases, Color + Normal textures -> ../build/
python rig.py      # rig, skin, Idle + Walk actions
python export.py   # FBX + stats.json
python shots.py -- ../build/LavaHorse_Source.blend ../build/validation   # preview renders
python topo.py -- ../build/                                              # topology report
```
