# Lessons from user feedback (read before modelling and before each round)

Each entry: what the user said → what was actually wrong → the fix that landed.

## Shapes

- **"The heads look nothing like the reference."** First heads were tapered crocodile lofts.
  Reference heads were *built from blocks*: a flat-topped navy skull, a blunt rectangular snout
  that slopes slightly to a nose block, a white gum line with big fangs, white cheek blocks at
  the mouth corner, a white blocky lower jaw opened ~38° with a red mouth. → Build heads from
  `box`es in a head-local frame (x side, y forward, z up). Turn side heads outward (~35-40°) if
  the front view shows them in profile.
- **"Make the snout less wide."** Snout ≈ 60% of skull width; narrow jaw, gum and tooth rows with it.
- **"Eyebrows should be part of the eye structure, not separate."** Build an *eye socket*: a
  narrower skull core under a full-width cranium cap; the brow ledge grows out of the cap and
  overhangs the eye (pitched down to the front for the angry slant, rolled up at the outside for
  the V seen from the front); a cheek ridge flush with the skull side is the socket floor.
- **"Make the eyes like the reference - right now it's a block. It has no pupil."** Replace any
  glowing box with `eye_lens`: a slightly domed angry-almond surface (the brow cuts its top edge
  down toward the snout, curved lower edge, pointed front) facing outward + a little forward so
  it is visible head-on; texture = white-hot glow, iris, vertical slit pupil, highlight, painted
  pre-squashed for the surface aspect. Recess it ~0.15 studs inside the brow/cheek.
- **"Make a large bevel to the edge closest to the camera … the eyebrow."** Use `bevel_prism`
  with that corner cut from the outline (cut ≈ 40% of the block's depth), mirrored on both sides
  of every head. ⚠ "Edge closest to the camera" was first misread as the cheek block - when a
  screenshot shows several blocks, name the part you think they mean in your reply, or ask.
- **"There is a gap between the horn and the head; make it taller."** The horn was anchored
  beyond the end of the cranium cap and floated over the lower core. → Anchor attachments on
  the surface that is actually under them and **sink their base ~0.1 stud into it**. Check with a
  close-up render from above/behind, not only from the front.
- **"The claws look nothing like the reference."** Thin spikes → chunky white chamfered claws
  that run forward off a navy toe block then bend straight down to a flat blunt tip on the
  ground, gold inverted-V chevron with a small cyan crystal above each toe (`claw`, `chevron`).
  Keep the tip at z ≈ 0 - claws poking under the floor showed up in `check_clips`.
- First-pass proportion misses to check explicitly: legs/paws far too thin, heads too small,
  necks merging into one blob at the base (spread their roots apart), torso too small next to
  legs and wings.

## Ice / crystals

- **"Make the ice look more like the reference."** Needles with a dark gradient → broad flat
  blades (width ×1.85, thickness 50% of width), saturated cyan-blue lightening to the tip,
  glowing white-cyan lines on every facet edge plus faint fracture lines. Lower Blender emission
  (~0.55) so the ice keeps its colour instead of washing out white. Density matters more than
  facet count: most shards as 4-tri blades, a few 12-tri hero shards in the spine column and
  tail burst, savings spent on more crystals (layered spine, fringes, tail bursts, crests).

## Texture

- **"Half the transparency of the stud texture."** Interpreted as stud relief/tint at 50%
  strength (`stud_strength: 0.5`, also halves the normal map). If the request is ambiguous,
  state your interpretation in the reply so it can be corrected cheaply.
- Studs too small read as noise; ~0.45 studs on a 12-stud creature worked.
- Teeth swatch must be near-white (a grey gradient made fangs look dirty).

## Bugs the checks caught (not visible in Cycles renders)

- Shards and teeth were wound inside out (ring order clockwise around the spike axis) - Roblox
  culls back faces, so they'd have been invisible/hollow in Studio. `check_normals` now gates
  every delivery; `stud_kit` winds outward by construction.
- FBX with no embedded texture because the image path was relative - `verify_export` shows
  `images []`. `stud_kit.make_material` loads absolute paths.
- Flying idle tail dipped 3 studs below the ground (nose-up pitch + drooping tail) -
  `check_clips` lowest-point column. Fix by lifting the tail/pelvis pitch, not by raising Root.

## Process

- Every feedback round: crop the screenshot + the matching reference panel, render the same
  angle after the fix, send the side-by-side. Renders from a mismatched camera angle wasted a
  round (a close-up camera inside the crystals, a head close-up from the wrong side).
- Commit/push each round; zip outside the repo; keep zips under 30 MiB.
- Never claim a 1:1 copy; list what still differs and why (tri budget, Roblox glow limits).
