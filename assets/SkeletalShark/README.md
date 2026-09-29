# Skeletal Shark (Roblox-ready)

A skeletal shark built in Blender 4.2 from the "Skeletal Shark – Rare Aquatic Creature" reference sheet. It uses the smooth, chunky low-poly style of the example Roblox pets: large flat faces and clean diagonal edges, with no voxel stair-stepping.

| | |
|---|---|
| Triangles | **3,030**, under the 5k budget. One mesh and one material. |
| Texture | `textures/SkeletalShark_Color.png` (1024², baked colour, gradient and studs), `textures/SkeletalShark_Emissive.png` (glow mask) |
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
  - `shark_lowpoly.py`: the low-poly pieces (lofted skull, jaw and body, swept ribs, extruded fins with inset panels, teeth).
  - `shark_geo.py`: the reference measurements (profiles and outlines) the pieces are built from. It also holds the earlier voxel build.
  - `stud_bake.py`: rasterises every triangle into the UV atlas, painting the gradient, the edge highlights and the studs.
  - `build_blend.py`: builds the mesh, UV-unwraps it (smart project + pack), bakes the texture, and builds the rig, weights and animations. It then exports the FBX files.
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

The stud is painted into the colour texture, not modelled. It follows the example meshes: engraved squares with a dark inner shadow on two sides and a light lip on the other two. About 28% of them are partial corner marks.

**Uniform coverage:** studs are laid out on a grid in the model's own space, not in texture space. Every face uses the grid plane it faces most (the pectoral fins use their own tilted axes). As a result:
- every stud is the same size (about 0.95 blocks) on every surface;
- they are spaced evenly (1.8 blocks, about 62% of grid cells filled);
- they line up with the model regardless of how the texture is laid out.

**Anti-aliasing:** the texture is baked at 2048² and downsampled to the 1024² file Roblox uses, so the stud lines stay clean.

The texture also has two finishing touches:
- a soft painted gradient on every part, lighter on top and darker below;
- a light bevel highlight along every hard edge.

The teeth, glow cores and eyes are plain colours without studs. The eye sockets carry a cyan glow that fades out from the eye.

The stud pattern is generated procedurally rather than downloaded. That keeps it licence-free and matched to the example look.
