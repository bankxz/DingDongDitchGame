# Ice Dragon (three-headed, Roblox-ready)

A low-poly, rigged and animated version of the three-headed ice dragon concept sheet.
It uses the Roblox stud look (the studs are texture, not geometry).

| File | What it is |
|---|---|
| `IceDragon.fbx` | Mesh, rig and all four clips (`Idle`, `Walk`, `FlyIdle`, `FlyWalk`). Use this with the Roblox **3D Importer**. |
| `IceDragon_Idle.fbx` / `IceDragon_Walk.fbx` / `IceDragon_FlyIdle.fbx` / `IceDragon_FlyWalk.fbx` | One clip each, for **Animation Editor → ⋯ → Import → From FBX Animation**. |
| `IceDragon.glb` | Same model and clips as glTF. |
| `IceDragon.blend` | Blender 4.2 source scene. |
| `textures/IceDragon_Color.png` | 1024² colour atlas with Roblox studs baked in at 50% strength (works as a plain `TextureID`). |
| `textures/IceDragon_Normal.png` | Matching stud normal map (optional, for `SurfaceAppearance`). |
| `source/*.py` | Build scripts that regenerate everything (see below). |
| `validation/` | Renders compared with the reference, and animation contact sheets. |

## Stats
- **4,912 triangles** (the limit is 5,000). `IceDragon_Body` has 3,416 and `IceDragon_Ice` has 1,496.
- **41 bones**, with at most 3 weights per vertex:
  - Root, Torso, Pelvis
  - 3 necks × 3 bones, plus Head and Jaw for each head
  - UpperArm, Forearm and Hand for each front leg
  - Thigh, Shin and Foot for each back leg
  - Wing1, Wing2 and Wing3 for each wing
  - Tail1 to Tail5
- About 15.6 × 19.4 × 12.1 studs (W × L × H), with 1 Blender unit = 1 stud.
- Rest pose: legs straight and apart, wings spread clear of the body, jaws open, tail straight. No limb touches another limb, so each bone deforms its own part cleanly.
- Clips at 30 fps, both loop:
  - `Idle` (90 frames): breathing, the necks sway out of step, one jaw snap per head, wing flex, tail sway. The feet stay locked in place.
  - `FlyIdle` (60 frames): hovers about 2.4 studs up, with two slow wingbeats per loop and the body bobbing on each downstroke. It holds a slight nose-up posture, with legs tucked, the tail hanging and swaying, the necks drifting at staggered times and the heads held steady.
  - `FlyWalk` (40 frames, flies forward in place): faster, stronger wingbeats with the body pitched nose-down. The necks reach forward with the heads kept level, the legs are tucked tight and trailing, and the tail streams back with a wave.
  - In both flight clips the **Root bone never moves**: the lift is the Torso rising inside the animation. The pet's position in the world and its collision stay on the pen floor, so flying costs the same to run as the ground idle. `source/check_fly.py` checks that the Root stays still, that the dragon clears the ground (FlyIdle ≥ 1.4 studs, FlyWalk ≥ 3.1) and that each loop is seamless.
  - `Walk` (40 frames, walks in place): the legs step in the order back-left, front-left, back-right, front-right. The feet plant flat, and the body, necks, wings and tail move in time. It was solved with IK and then baked to plain keys, so no constraints get exported.

## Importing into Roblox Studio
1. **Avatar → Import 3D** (or File → Import 3D), then pick `IceDragon.fbx`.
2. In the importer, set **File Dimensions / Scale Unit = Studs**. The dragon should then be about 12 studs tall. Rig type: *Rigged / Custom*.
3. The importer brings the texture in automatically. The model becomes one Model with two skinned MeshParts sharing the bones.
4. To get the ice glow, select the `IceDragon_Ice` MeshPart and try `Material = Neon` or `Glass`, or add a light-blue `PointLight`.
5. Animations: open the **Animation Editor** on the model. Use **Import → From FBX Animation** with `IceDragon_Idle.fbx` and then `IceDragon_Walk.fbx`, and publish each one. Play them with an `AnimationController` + `Animator`, and set `Looped = true`.

## Rebuilding
```bash
pip install bpy==4.2.0 pillow numpy
git clone https://github.com/dudeax/Roblox-HD-Studs /tmp/studs      # MIT-licensed stud texture source
python3 source/make_atlas.py /tmp/studs textures    # builds the stud texture atlas
python3 source/build_dragon.py .                    # builds the model, rig and animations -> IceDragon.blend
python3 source/export_dragon.py .                   # exports the FBX and GLB files
python3 source/verify_export.py .                   # re-imports the exports and checks tris, bones and clips
python3 source/render_views.py . validation         # renders the validation views
```

## Credits
The stud relief comes from [dudeax/Roblox-HD-Studs](https://github.com/dudeax/Roblox-HD-Studs) (MIT, © 2024 dudeax).

## Heads and claws (matched to the HEAD / EYE and CLAW / FOOT close-ups)
- **Heads** are built from blocks:
  - a flat navy skull: a narrower core under a full-width cranium cap
  - a blunt box snout about 60% as wide as the skull, with a lighter bridge plate and a nose block with nostrils
  - an eye socket cut into each side of the skull:
    - a brow ledge with a large bevel on its front-outer edge grows out of the cranium cap and forms the top; overhangs the eye, slopes down toward the front (the angry slant) and rises at the outside (the V seen from the front)
    - a cheek ridge flush with the skull side forms the bottom
    - the eye inside the socket is a slightly domed, angry-almond-shaped surface, not a block: the brow cuts the top edge down toward the snout, and the bottom edge is curved
    - it faces outward and a little forward, so the eyes show head-on too
    - its texture is a white-hot glow with a bright cyan iris, a dark vertical slit pupil and a small highlight, painted pre-squashed so the iris looks round on the model
  - a white gum line with big white fangs, including a long pair at the front corners
  - stacked white cheek blocks at the mouth corner
  - a white blocky lower jaw with a chin block and upward fangs, open about 38°, with a red mouth and tongue
  - gold horn spikes at the back of the skull, plus a tall gold forehead horn on the centre head, set into the cranium with no gap
  - an ice mane and a chin icicle
- **Side heads** are turned outward (about 39°), so the front view shows their profiles like the reference.
- **Claws**: each paw has four chunky white claws with chamfered edges. Each claw runs forward off a navy toe block and then bends straight down to a flat, blunt tip on the ground. A gold chevron with a small cyan crystal sits on the foot above each toe.
- `validation/compare_head.png`, `compare_claw.png`, `compare_heads_front.png` and `compare_heads_side.png` show the reference next to the model.

## Ice (matched to the ICE CRYSTAL SPIKE close-up)
- The crystals are broad, flat, blade-like shards, 1.85× wider than before and half as thick as they are wide.
- Their texture is a saturated cyan-blue that lightens toward the tip. Every facet edge is traced by a glowing white-cyan line, and faint fracture lines run inside each facet.
- Most shards use the cheap 4-tri blade shape, and the texture draws their facets. The large hero shards (spine column, tail fan, crest centres) keep the full faceted shape.
- The saved triangles went into more crystals:
  - a layered spine column with side fringes
  - a double row on the tail
  - a 15-shard tail burst
  - 13-shard head crests
  - more crystals on the necks and wing edges
- In Roblox, set `IceDragon_Ice` to `Material = Glass` (or give it `Transparency ≈ 0.15`) for the translucent look, or to `Neon` for glow.

## Known differences from the concept sheet
The concept art is a high-detail voxel render made of thousands of separate blocks and several hundred crystals. At under 5k triangles, this model keeps these things from it:
- the silhouette and proportions
- three heads with open fanged mouths and glowing eyes
- the crystal crests and spine
- the gold diamond chest gem
- the gold wing joints with gems
- the gold shoulder, ankle and toe bands
- the white claws
- the crystal fan on the tail
- the palette, sampled from the sheet

These are simplified:
- The neck and body are faceted lofts, not individual blocks.
- There are fewer crystals, and each one is bigger.
- The wing membrane uses the stud tile instead of the scale pattern.
- The glow is emissive in Blender, but Roblox needs Neon or lights to show it.
