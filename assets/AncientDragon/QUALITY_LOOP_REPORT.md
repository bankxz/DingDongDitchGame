# Quality loop report

## v1 rejected
**User feedback:** "looks nothing like the reference", "make it less blocky".
The evidence is in `validation/v1_rejected/reference_vs_model.png`.

**Diagnosis:** the problem was geometry and silhouette. Texture and UVs were fine.
- v1 built every part from axis-aligned boxes. The body, neck and head were rectangular slabs, the legs were box stacks, and the wing was a flat fan of straight beams.
- The reference has sculpted, rounded masses. It has an S-curved neck, a barrel torso, a wedge head with crescent horns, curved spars that arch over a billowing membrane, and a tapering segmented tail. It has more horns, all curved, and its cyan runes are larger.

**Skill-gap decision:** the existing skills already cover this. `reference-to-3d`, `landmark-fit-repair` and `multiview-fit-loop` all say to build from measured landmarks rather than primitives. v1 skipped that and used primitive-first modelling. The fix is to follow those skills, and no skill patch is needed.

## v2 plan
- Loft rounded (squircle) tubes along measured side-view (L, Z) landmark paths with front-view (X) widths. This covers the neck, torso, tail, head, jaw, legs, horns and spars.
- Build the wing membrane as billowed strips between curved spars, placed from 3D landmarks solved from the side and front views.
- Use smooth shading on the organic parts and keep hard shading on the claws and spikes.
- Snap the stud texture per face to whole cells, so every stud stays square and whole on the curved geometry.
- Keep the same gates: under 5k tris, at most 4 bone influences per vertex, 7-view comparison, and animation contact sheets.

## v2 result
- The geometry is now lofted rounded tubes: a 12-sided torso and neck, 8-sided head, jaw, legs and tail, and 6-sided horns and spars. The wing membrane is a billowed double-sided surface. That comes to 3,858 tris.
- I fixed validation framing. Renders now have transparent backgrounds and are cropped to the model's bounding box, so they compare at the same scale as the reference panels. v1's zoomed-out camera had made its silhouettes look squat.
- Proportion passes so far:
  - lengthened the legs (body lifted 1.4u and the feet planted)
  - raised and enlarged the head and neck
  - made the discs smaller and moved them out from under the leg geometry
  - spread and enlarged the wings
  - gave the tail thicker segments with a single rune per side
- Remaining known conflict: the reference TOP/BOTTOM panels show the wings flat, while the other panels show them upright. The model follows the 3/4, front, back and side views.

## v2 rejected → v3
**User feedback:** "doesn't look like the reference, clone the style down to the last detail".

**Diagnosis:** the problem was style. v2's smooth lofted tubes were the wrong construction language. Every surface in the reference is small uniform cubes, each with one square stud. The reference also has stepped silhouettes, spars made of cube chunks, horns and spikes built as tapered cube chains, and runes made of individual glowing cubes.

**v3 pipeline:**
1. Keep the v2 landmark sculpt as a hidden source shape.
2. Voxelize it at the reference cube size (0.6u), using per-part ray parity so the smallest containing part owns each cube (armour, horns and claws keep their own colours).
3. Colour each exposed cube face from its owning part, then apply a 3×3 majority filter to remove speckle.
4. Greedy-merge coplanar same-colour faces, each at most 16 cells, blending bone weights per corner.
5. Build the wings as a stepped studded membrane painted cell by cell, with gold cube-chain spars.
6. Build horns, spikes, claws and fangs as tapered cube chains.
7. Build the runes (chest shield, rune discs, knee plates, tail glyphs) as pixel-art plates with cell-exact UVs.

The result is 4,956 tris. Walk and idle deformation were checked on contact sheets.

## v3 feedback → v3.1 (torso + head)
**User feedback:** "the torso needs to be bigger and the head looks nothing like the reference".
- The torso is now about 25% wider and 15% taller, and the leg stance is wider to match.
- The head was rebuilt as direct studded blocks instead of voxelized tubes:
  - blunt dark snout with a slate top plate, a mid head and a rear skull
  - gold brow and crest strip, gold cheek band, cream cheek plate and a teal accent cube
  - glowing eye and snout slit, a cream tooth line, a small dark lower jaw, and big hanging cream fangs
  - a crown of stepped cube-chain horns: big cream crescents, two gold horns per side, a cream horn swept back, a gold cheek frill and a tall gold forehead crest
- The head is enlarged 1.32× and raised onto a taller neck.

## v3.1 feedback → v4 (horns, less blocky, eyes)
**User feedback:** "make the horns like the reference, then make it less blocky, model an eye canal in the skull and an eyeball with pupils inside".
- **Horns:** the reference horns are ribbed, tapering and curved. The great cream horns are now thick crescents that bow outward and curl in at the tips in the front view, and sweep back in the side view. The gold crown horns, the swept-back cream horn, the cheek frill and the forehead crest all use the same ribbed-segment horn builder.
- **Less blocky:** I removed the voxel pass. The body, neck, tail and legs are smooth-shaded rounded lofts with 10–16 sides. The spars, claws and spikes are ribbed tubes. The wing membrane now has a smooth outline, and its painted cells were extended so the edges stay covered.
- **Eyes:** a boolean (EXACT solver) cuts an elongated eye canal into a closed skull loft. The canal walls are dark. An 8×5 UV-sphere eyeball sits inside with planar UVs onto a painted eye: pale glowing sclera, cyan iris, dark slit pupil and a glint.
- 4,955 tris.

## v4 feedback → v4.1
**User feedback:** "the head is too stretched, the eye canal needs to be wider with a natural concavity, the emblem should be armour around the breast, the horns need a curve like the reference, and the texture is too blocky".
- **Head:** the face is compressed to 74% of its length about the back of the skull.
- **Eye canal:** a wider, shallower ellipsoid cut (14×10 segments) centred just outside the surface, which gives a smooth bowl. The eyeball sits deeper inside it.
- **Breastplate:** a shield-shaped grid, ray-cast onto the chest and neck surface so it hugs the breast. It has a gold rim and the pixel-art rune on its face. Rays that miss the chest take the depth of a neighbouring hit.
- **Horns:** paths are Catmull-Rom smoothed. The great horns arc back and then sweep up, and bow out and then in from the front.
- **Texture:**
  - The stud template has soft bevels, rounded studs, seam shading, a slight top-left key light and fine noise.
  - Studs are smaller (0.36u) and keep their true size.
  - UV phase comes from world coordinates, so studs line up across faces instead of being stretched per face.
- 4,982 tris.

## v4.1 feedback → v4.2
**User feedback:** "texture is still pixelated, and the head looks nothing like a dragon's".
- **Texture:** I rewrote the generator.
  - Swatches get a soft, low-contrast stud relief with low-frequency colour variation, and no per-cell colour steps.
  - The wing membrane is painted per pixel as a smooth gradient: dark leading band, then teal, then a glowing trailing edge.
  - The runes, the rune plates (disc, chest, tail, knee) and the eye are drawn as anti-aliased vector shapes (4× supersampled) with soft glow halos.
- **Head:** a custom-section skull replaces the rounded tube. It is a flat-topped wedge snout with nostril flare and a pinch behind it, a raised brow, wide cheekbones and a tapered back skull.
  - The angry brow ridge angles down toward the snout.
  - The lower jaw hangs open with a dark mouth, and there are fangs plus upper and lower teeth.
  - It also has nostrils, a gold nose ridge and a glowing snout slit.
  - The eye canal is carved into the new skull under the brow.
- 4,980 tris.
