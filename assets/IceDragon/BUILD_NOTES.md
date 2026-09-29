# Build notes (reference-locked pipeline)
- **Source of truth:** the concept sheet's FRONT, LEFT SIDE and BACK views, plus its detail close-ups. The TOP view is drawn in perspective from behind and above, so it only served as a rough check.
- **Palette** (sampled from the sheet's swatches): navy #073588, royal #1657FC, cyan #4DD9FE, ice #CAE9FC, gold #FFCD53. White and mouth-red were added.
- **Coordinates:** Z is up, the dragon faces −Y, and its left side is +X (`.L`). The FBX is exported with −Z forward and Y up.
- **UVs:** each face on a studded material is planar-projected at 0.45 studs of world size. The projection is snapped to whole studs, so faces on the same plane line up. Crystals use a base-to-tip gradient cell in the atlas.
- **Iteration log:** 5 render-and-compare rounds (renders in `validation/`). Fixes, in order:
  1. Thicker legs and paws.
  2. Bigger crystals and fewer tiny ones.
  3. Larger heads, turned outward.
  4. Jaw opening and teeth size.
  5. Bigger torso, and the white/navy split on the necks.
- **Animation checks:** a contact sheet for each clip, plus a numeric foot-lock test:
  - idle: the feet move by 0.00
  - walk: the feet plant at the rest height, and the loop is seamless
- **Round 2 (after feedback on the heads and claws):**
  - The heads were rebuilt from blocks to match the HEAD / EYE close-up.
  - The claws were rebuilt as chamfered bent blocks with toe blocks, gold chevrons and gems.
  - The side heads now turn further outward.
  - Crystal and tooth faces were wound inside out. Roblox hides backfaces, so these would have looked hollow in Studio. `source/check_normals.py` now checks for this, and it reports 0 inside-out islands.
- **Round 3 (feedback: eyes, eyebrows, snout width):**
  - Each eye is now a recessed socket built into the skull: the brow ledge is fused into the cranium cap, the cheek ridge forms the socket floor, and a glowing block sits inside the socket.
  - The snout was narrowed from 1.66 to 1.25 studs, and the jaw, teeth and gum were narrowed to match.
  - To stay under 5k tris, I removed the lower-jaw chin sub-block and the small second gold spike on each side.
- **Round 4 (feedback: the eye is a block and has no pupil):** I replaced the glowing block with a domed eye surface in the angry-almond outline taken from the reference close-up. I also painted a new eye texture onto it: a white-hot glow, a cyan iris and a dark slit pupil, drawn at the eye's 2.3:1 aspect so the iris stays round. This saved 24 tris.
- **Round 5 (feedback: ice should look like the reference, studs at half strength):**
  - The stud relief, the stud-top tint and the normal map are now at 50% strength (`STUD_STRENGTH`).
  - The ice texture was redrawn with glowing facet edges.
  - The shards are now broad, flat blades.
  - Most shards became 4-tri blades, and the triangles this saved were spent on much denser ice.
  - The Blender glow on the ice was lowered from 1.4 to 0.55, so the ice keeps its colour instead of washing out to white.
- **Round 6:**
  - Added the `FlyIdle` (hover) and `FlyWalk` clips. The Root stays still and the Torso lifts. The foot IK is switched off while these clips are sampled.
  - Rested the claw tips on the ground.
  - Gave each eyebrow a large bevel on its front-outer edge, mirrored on both sides of all three heads.
