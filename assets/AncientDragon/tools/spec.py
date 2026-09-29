"""Shared spec for the Ancient Dragon: palette, atlas layout, wing 2D shape.

Design units ("u"): 1u = 10px of the LEFT SIDE reference panel.
Design coords: X lateral (+X = dragon's left), L = length from snout (0) to tail (35),
Z = height above ground. Blender: x=X, y=L-L0, z=Z (dragon faces -Y).
"""
ATLAS = 2048
SW = 512            # swatch size in px
CELL_PX = 30        # one stud/cube cell in px
MARGIN = 16         # px margin inside each swatch (bleed guard)
CELLS = (SW - 2 * MARGIN) // CELL_PX   # 16 cells usable per swatch
CELL_U = 0.6        # world size (design units) of one stud cell

PALETTE = {
    'charcoal': (58, 58, 70),
    'gold':     (232, 166, 52),
    'cream':    (224, 198, 150),
    'horn':     (238, 214, 164),
    'glow':     (70, 248, 245),
    'teal':     (26, 84, 96),
    'dark':     (38, 38, 48),
    'belly':    (212, 186, 140),
}
# swatch grid positions (col,row) in 512px swatches, row 0 = top of image
SWATCH = {
    'charcoal': (0, 0), 'gold': (1, 0), 'cream': (2, 0), 'horn': (3, 0),
    'glow': (0, 1), 'teal': (1, 1), 'dark': (2, 1), 'belly': (3, 1),
    # decal regions (whole face mapped into region)
    'rune_chest': (0, 2), 'rune_disc': (1, 2),
    'rune_tail': (0, 3), 'rune_knee': (1, 3),
}
WING_REGION = (1024, 1024, 1024, 1024)   # x, y (top-left, px), w, h
# wing local 2D coords (a = span outward/back, b = up), origin at shoulder root
WING_A0, WING_A1 = -1.0, 20.0
WING_B0, WING_B1 = -7.5, 8.0
WRIST = (2.0, 6.5)
# spar tips (inner -> outer); leading edge spar ends at the last one
TIPS = [(3.6, 0.1), (8.6, -1.0), (13.6, -2.3), (18.6, -4.2)]
LEADING = [WRIST, (6.0, 7.0), (10.5, 5.6), (14.8, 2.6), (17.6, -0.8), TIPS[3]]
# spar polylines (wrist -> tip) with slight curvature control point
SPARS = [
    [WRIST, (3.0, 3.2), TIPS[0]],
    [WRIST, (5.6, 3.0), TIPS[1]],
    [WRIST, (9.8, 2.2), TIPS[2]],
]
# membrane outline (counter-clockwise-ish): root -> wrist -> leading edge -> tips with scallops -> body
def membrane_outline():
    pts = [(0.0, 0.8), WRIST]
    pts += LEADING[1:]
    t = TIPS
    pts += [(16.3, -1.6), t[2], (11.2, -0.1), t[1], (6.1, 0.9), t[0], (0.6, 0.5)]
    return pts
