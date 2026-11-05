"""Z-fighting detector: finds visible coplanar overlapping faces between DIFFERENT objects.

Two faces flicker / render black when they lie in the same plane, face the same way and overlap.
(Faces in the same plane facing OPPOSITE ways are just touching contact and are hidden.)
For every asset .blend this evaluates all meshes (modifiers applied), buckets faces by plane
(normal + offset, rounded) and tests polygon overlap with shapely.

Run:  python zfight_check.py [blend names...]      (default: every blend in assets/lobby/blend)
Prints one line per offending object pair with the overlap area and a sample location.
"""
import sys, os, glob, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from mathutils import Vector
from shapely.geometry import Polygon
import lobbylib as L

AREA_MIN = 2e-3          # ignore slivers smaller than this (studs^2)
GROUND_Z = 0.05          # faces facing down below this are resting on the floor
SPLIT_UNITS = ("02_", "06_", "07_")   # blends that hold several separate units side by side / overlaid
NRM_Q, D_Q = 1e-3, 2e-3  # plane rounding tolerances


def plane_key(n, d):
    return (round(n.x / NRM_Q), round(n.y / NRM_Q), round(n.z / NRM_Q), round(d / D_Q))


def basis(n):
    a = Vector((1, 0, 0)) if abs(n.x) < 0.9 else Vector((0, 1, 0))
    u = n.cross(a).normalized()
    return u, n.cross(u)


def hidden(dg, origin, n):
    """Hidden if something sits right in front, or if the point is INSIDE another closed solid
    (the first surface the outward ray meets faces away from it, i.e. the ray is exiting a volume)."""
    sc = bpy.context.scene
    ok, loc, nrm, *_ = sc.ray_cast(dg, origin, n, distance=1000.0)
    if not ok:
        return False
    if (loc - origin).length < 0.06:
        return True
    if nrm.dot(n) > 0:
        return True
    for d in (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))):   # second opinion, other axis
        if abs(d.dot(n)) > 0.9:
            continue
        ok2, loc2, nrm2, *_ = sc.ray_cast(dg, origin, d, distance=1000.0)
        return bool(ok2 and nrm2.dot(d) > 0 and ok)
    return False


def check(blend):
    bpy.ops.wm.open_mainfile(filepath=blend)
    dg = bpy.context.evaluated_depsgraph_get()
    unit_of = {}
    if os.path.basename(blend).startswith(SPLIT_UNITS):
        root = next(c for c in bpy.data.collections if c.name.startswith("ASSET_"))
        for ch in root.children:
            for o in ch.all_objects:
                unit_of[o.name] = ch.name
    buckets = {}
    for ob in bpy.data.objects:
        if ob.type != "MESH" or ob.hide_render or ob.name.startswith(("RIG_", "CAM_")):
            continue
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ob.matrix_world
        nm = mw.to_3x3().inverted().transposed()
        for p in me.polygons:
            if p.area < 1e-5:
                continue
            n = (nm @ p.normal).normalized()
            pts = [mw @ me.vertices[i].co for i in p.vertices]
            d = n.dot(pts[0])
            buckets.setdefault((unit_of.get(ob.name, ""),) + plane_key(n, d), []).append((ob.name, n, pts))
        ev.to_mesh_clear()
    hits = {}
    for key, faces in buckets.items():
        names = {f[0] for f in faces}
        if len(names) < 2:
            continue
        n = faces[0][1]
        u, v = basis(n)
        polys = []
        n = faces[0][1]
        for name, _, pts in faces:
            try:
                pg = Polygon([(p.dot(u), p.dot(v)) for p in pts]).buffer(0)
            except Exception:
                continue
            if not pg.is_empty:
                polys.append((name, pg, pts[0]))
        for i in range(len(polys)):
            for j in range(i + 1, len(polys)):
                a, b = polys[i], polys[j]
                if a[0] == b[0]:
                    continue
                if not a[1].bounds or not b[1].bounds:
                    continue
                ax0, ay0, ax1, ay1 = a[1].bounds
                bx0, by0, bx1, by1 = b[1].bounds
                if ax1 < bx0 or bx1 < ax0 or ay1 < by0 or by1 < ay0:
                    continue
                inter = a[1].intersection(b[1])
                area = inter.area
                if area > AREA_MIN:
                    # visibility: is anything sitting right in front of the overlap? (then it is hidden)
                    c2 = inter.representative_point()
                    d = n.dot(a[2])
                    p3 = u * c2.x + v * c2.y + n * d
                    if n.z < -0.9 and p3.z < GROUND_Z:
                        continue                      # underside resting on the floor: never seen
                    if hidden(dg, p3 + n * 0.003, n):
                        continue
                    k = tuple(sorted((a[0], b[0])))
                    h = hits.setdefault(k, [0.0, a[2]])
                    h[0] += area
    return hits


def main():
    names = [a for a in sys.argv[1:] if a.endswith(".blend")]
    files = [os.path.join(L.BLEND, n) for n in names] if names else sorted(glob.glob(os.path.join(L.BLEND, "0*.blend")))
    total = 0
    for f in files:
        hits = check(f)
        total += len(hits)
        print(f"== {os.path.basename(f)}: {len(hits)} z-fighting object pairs")
        for (a, b), (area, p) in sorted(hits.items(), key=lambda kv: -kv[1][0])[:60]:
            print(f"   {area:7.3f}  {a}  <->  {b}   @ ({p.x:.2f}, {p.y:.2f}, {p.z:.2f})")
    print("TOTAL", total)


if __name__ == "__main__":
    main()
