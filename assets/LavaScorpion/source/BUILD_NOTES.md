# Build notes: Lava Scorpion

## Source-of-truth policy (multiview-constraint-solver)
- **Conflict:** the TOP view shows the tail laid straight back with the stinger pointing backwards. The 3/4, FRONT, BACK, LEFT and RIGHT views all show the tail curled up over the body. One rigid model cannot satisfy both.
- **Policy `front_side_canonical`:** the tail is curled, as in 5 of the 6 views. The TOP view is used only for the body footprint (2.5 × 1.1 m), leg splay angles and claw spread.

## Measured proportions (metres, Z up, facing -Y)
- Body: Y -1.25 to +1.24; top about 1.37, belly about 0.42. There are three carapace plates (front, mid, rear) with glowing cracks between them.
- Head: 0.56 wide, with two angled glowing eye slits low on the front.
- Tail: 6 segments, 0.54 wide tapering to 0.44, curling to a height of about 2.85. The stinger has a red-orange bulb and a yellow stepped hook.
- Pincers: each hand is a 2×3×2 cluster of cubes, with the lava-lit cube at the front and bottom. The long outer finger is fixed; the inner finger is a movable bone. Fingers go red → orange → yellow toward the tip.
- Legs: 4 per side at angles of 25°, 5°, -12° and -38°. The knee is at about 1.15 and each foot reaches about 1.8 m out sideways. Every foot has an orange → yellow glowing tip.

## Surface rules
- Palette sampled from the sheet: charcoal #2A292E, dark grey #484048, deep red #A3281F, lava orange #FD6C09, hot yellow #FEDD35.
- Atlas cells, one per face:
  - `R`: all edges carry lava seams (plates, tail).
  - `J`: seams at the joints only (legs, arms, body cores).
  - `D`: plain dark cube with faint red bounce light (cluster and bump cubes).
  - `*C`: plates with lava cracks.
  - `H0`–`H2`: hot gradient cells.
  - `EYE`: glowing eye.
- The stud count on each face is `round(face size / 0.2 m)`, clamped to 1–3, so studs stay the same size everywhere.

## Validation
- `validation/compare_0.png` and `compare_1.png`: the reference panel next to a render from the matching camera, for all 6 views.
- `validation/walk_contact_sheet.png`: the walk loop closes exactly (the frame 1 vs frame 33 image difference is 0.0).
- `validation/idle_contact_sheet.png`: idle breathing, tail sway, stinger twitches and pincers opening and closing.

## Known remaining differences from the reference
- The reference is a stylised concept render. Its surfaces show many small modelled bumps and organic bevels. Under the < 5k-tri budget these are texture (studs, bevel lip, seams) on larger boxes, so silhouettes are slightly cleaner and more rectilinear.
- In the reference, the glow halo between cubes partly comes from scattered light between separate cubes. Here it is baked into the colour and emission maps, and Roblox shows it through `Lighting.Bloom`.
- TOP view tail pose: see the conflict above.
