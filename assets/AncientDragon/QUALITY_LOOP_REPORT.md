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
