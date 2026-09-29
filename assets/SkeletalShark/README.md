# Skeletal Shark (Roblox-ready)

A voxel skeletal shark built in Blender 4.2 from the "Skeletal Shark – Rare Aquatic Creature" reference sheet.

| | |
|---|---|
| Triangles | **4,812**, under the 5k budget. One mesh and one material. |
| Texture | `textures/SkeletalShark_Color.png` (1024², stud atlas), `textures/SkeletalShark_Emissive.png` (glow mask) |
| Rig | 11 bones. Max 2 influences per vertex. Every vertex is weighted. |
| Animations | `Idle` (90 f, loop), `Walk` (40 f, loop, swim cycle), `Run` (24 f, loop, fast swim), `Attack` (41 f, lunge + bite). All at 30 fps. |
| Size | About 14.3 × 6.3 × 4.7 studs (length × width × height) |
| Rest pose | Straight spine, fins spread, mouth open as on the sheet. This neutral pose is the shark equivalent of a T-pose. |

## Files

- `SkeletalShark.blend` is the full scene. It contains the mesh, the rig and all four actions (kept as muted NLA tracks, fake-user). The textures are packed into the file.
- `fbx/SkeletalShark.fbx` has the mesh and rig in rest pose. Import this one as the model.
- `fbx/SkeletalShark_<Idle|Walk|Run|Attack>.fbx` each contain the rig and a single baked animation, for Roblox's Animation Editor.
- `textures/` holds the colour atlas and the emissive mask.
- `validation/` holds the reference-vs-model comparisons, per-view renders, the animation contact sheet and the multiview fit report.
- `source/` holds the scripts that regenerate everything:
  - `shark_geo.py`: voxel parts measured from the reference, a greedy mesher with cross-part culling, and the stud atlas painter.
  - `build_blend.py`: builds the mesh, material, rig, weights and animations, then exports the FBX files.
  - `render_views.py`, `compare_sheet.py`, `fit_report.py`, `anim_sheet.py` and `iterate.sh`: validation tools.

To rebuild: `python source/build_blend.py <out_dir>` with a Python that has `bpy` 4.2 (`pip install bpy==4.2.*`).

## Rig

```
Root
└─ Torso
   ├─ Head ── Jaw
   ├─ PectoralL, PectoralR
   └─ Spine2 ─ Tail1 ─ Tail2 ─ TailFin
      └─ Dorsal
```

The body and rib vertices are blended along the spine chain, so the swim wave bends smoothly. The skull, jaw, fins and tail fin are rigid.

## Importing into Roblox Studio

1. **Avatar/3D Importer → `fbx/SkeletalShark.fbx`.**
   - Keep "Rig" enabled.
   - The file is exported with Blender unit scale 0.01 and *FBX Units Scale*, so 1 Blender unit = 1 stud. The shark should come in about 14 studs long.
   - If your importer settings bring it in 100× too big or too small, change *File Dimensions* / scale in the importer.
2. Colour texture:
   - The colour texture is embedded in the FBX.
   - If it doesn't come through, set the MeshPart's `TextureID` (or a SurfaceAppearance `ColorMap`) to an upload of `SkeletalShark_Color.png`.
   - Use texture filtering "Point" if you want crisp studs.
3. Put an `AnimationController` + `Animator` in the model. A shark is not a Humanoid.
4. Animation Editor → select the rig → **⋯ → Import → From FBX Animation** → choose each `fbx/SkeletalShark_<Name>.fbx` in turn.
   - Save/publish each clip.
   - Set Idle/Walk/Run to loop.
   - Leave Attack as a one-shot. Suggested priority is `Action`.
5. The glow (eyes, rib cores) is painted bright cyan in the colour map. For extra bloom you can add `PointLight`s/`SurfaceLight`s. The emissive mask is included for engines or SurfaceAppearance setups that support it.

## Stud texture

The stud is painted into the colour atlas, not modelled. It is one inset square per voxel block, with a dark upper-left inner edge, a light lower-right edge and soft block seams. This follows the example Roblox pets you supplied. Every face gets its own atlas island, so studs line up with the block grid on every surface.

The stud pattern is generated procedurally rather than downloaded. That keeps it licence-free and exactly matched to the example look.
