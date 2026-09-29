# Ancient Dragon: Roblox-ready model

This is a low-poly voxel dragon rebuilt from the "Ancient Dragon" reference sheet. It is rigged and ships with Idle and Walk animations.

| | |
|---|---|
| Triangles | 2,800 (budget < 5,000) |
| Bones | 33 (Root, Hips, Spine, Chest, Neck1-2, Head, Jaw, legs x12, Tail1-9, Wing1-2 x2) |
| Skinning | rigid, 1-2 influences per vertex (Roblox limit is 4) |
| Size | about 9.2 m long x 3.8 m tall x 6.2 m wingspan (1 Blender unit = 1 m) |
| Bind pose | standing quadruped with wings spread, the quadruped equivalent of a T-pose |
| Texture | one 1024² stud atlas (color + normal). 2048² masters are also included |

The studs, cube seams and glowing runes are **texture only**. None of that detail is modelled.

## Files
- `AncientDragon.blend`: source scene with the mesh, armature, material and `Idle` / `Walk` actions.
- `export/AncientDragon.fbx`: mesh and rig in rest pose. Import this in the Roblox 3D Importer.
- `export/AncientDragon_Idle.fbx`, `export/AncientDragon_Walk.fbx`: one animation per file, for the Animation Editor's *Import → From FBX Animation*.
- `textures/AncientDragon_Color.png`, `textures/AncientDragon_Normal.png`: use these for a `SurfaceAppearance` (ColorMap / NormalMap).
- `textures/*_2048.png`: full-resolution masters, plus an emission mask used for the Blender renders.
- `validation/`: reference-vs-model comparison renders.
- `tools/`: fully procedural build pipeline (`make_texture.py` → `build.py` (+`animate.py`) → `export.py`, `render.py`, `compare.py`).

## Import into Roblox Studio
1. Go to *File → Import 3D* and pick `export/AncientDragon.fbx`. Set Rig General → Rig Type to **Custom**, then import.
   Studio creates a Model with the skinned MeshPart, its Bones and an AnimationController.
2. On the MeshPart, add a `SurfaceAppearance`. Set ColorMap to `AncientDragon_Color.png` and NormalMap to `AncientDragon_Normal.png`.
   Set the MeshPart Material to *SmoothPlastic*.
3. Open the Animation Editor on the model, choose *Import → From FBX Animation* and pick `AncientDragon_Idle.fbx`. Publish it, then do the same with `AncientDragon_Walk.fbx`. Set both to Looped.

## Rebuild
Blender 4.2 is used as a Python module (`pip install bpy==4.2.0` on Python 3.11):
```
cd tools && python3.11 make_texture.py && python3.11 build.py && python3.11 export.py
python3.11 render.py && python3.11 compare.py <reference.webp>
```

## Known differences from the reference
- The reference is a painted concept sheet whose views disagree. In the TOP/BOTTOM panels the wings lie flat and face the camera. In the FRONT/BACK/SIDE panels the same wings are raised vertically. A rigid model can't match both, so the wings follow the 3/4, front, back and side views.
- The reference is made of thousands of individual cubes. Under 5k tris, the cube and stud detail lives in the texture on larger blocks, so the silhouette is blockier and less "noisy" than the render.
