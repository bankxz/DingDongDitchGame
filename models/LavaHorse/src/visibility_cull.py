# Render-based visibility culling: delete only faces that are never seen.
# Every face gets a unique ID colour; the posed, rigged mesh is rendered (flat emission, no AA,
# raw float EXR) from a sphere of orthographic viewpoints in several animation poses. Faces that
# never cover a single pixel are removed. Faces that only show mid-animation are kept.
import bpy, math, os, tempfile
from mathutils import Vector


def _fib_sphere(n):
    pts = []
    g = math.pi * (3 - math.sqrt(5))
    for i in range(n):
        z = 1 - 2 * (i + 0.5) / n
        r = math.sqrt(1 - z * z)
        pts.append(Vector((math.cos(g * i) * r, math.sin(g * i) * r, z)))
    return pts


def cull_invisible_faces(horse, rig, poses, n_views=32, res=1024):
    """poses: list of (action or None, frame). Returns number of triangles removed."""
    sc = bpy.context.scene
    me = horse.data
    # face-ID colour attribute (1-based, 24 bit)
    attr = me.attributes.new('face_id', 'FLOAT_COLOR', 'FACE')
    for p in me.polygons:
        i = p.index + 1
        attr.data[p.index].color = ((i & 255) / 255.0, ((i >> 8) & 255) / 255.0, ((i >> 16) & 255) / 255.0, 1)
    idmat = bpy.data.materials.new('FACE_ID')
    nt = idmat.node_tree
    nt.nodes.clear()
    a = nt.nodes.new('ShaderNodeAttribute'); a.attribute_name = 'face_id'; a.attribute_type = 'GEOMETRY'
    em = nt.nodes.new('ShaderNodeEmission')
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(a.outputs['Color'], em.inputs['Color']); nt.links.new(em.outputs[0], out.inputs['Surface'])
    saved_mats = list(me.materials)
    me.materials.clear(); me.materials.append(idmat)
    hidden = []
    for o in sc.objects:
        if o not in (horse, rig) and o.type in ('MESH', 'LIGHT') and not o.hide_render:
            o.hide_render = True; hidden.append(o)
    st = dict(engine=sc.render.engine, res=(sc.render.resolution_x, sc.render.resolution_y),
              vt=sc.view_settings.view_transform, film=sc.render.film_transparent, cam=sc.camera,
              fmt=sc.render.image_settings.file_format, world=sc.world)
    sc.render.engine = 'CYCLES'
    sc.cycles.samples = 1
    sc.cycles.use_denoising = False
    sc.cycles.pixel_filter_type = 'BOX'
    sc.cycles.filter_width = 0.01
    sc.cycles.max_bounces = 0
    sc.render.resolution_x = sc.render.resolution_y = res
    sc.render.film_transparent = True
    sc.view_settings.view_transform = 'Raw'
    sc.render.image_settings.file_format = 'OPEN_EXR'
    sc.render.image_settings.color_depth = '32'
    cd = bpy.data.cameras.new('VIS'); cd.type = 'ORTHO'; cd.ortho_scale = 14.0
    cam = bpy.data.objects.new('VIS', cd); sc.collection.objects.link(cam); sc.camera = cam
    centre = Vector((0, 0.4, 4.0))
    seen = set()
    tmp = os.path.join(tempfile.gettempdir(), 'lh_vis.exr')
    ad = rig.animation_data
    for action, frame in poses:
        ad.action = action
        sc.frame_set(frame)
        for d in _fib_sphere(n_views):
            cam.location = centre + d * 30
            cam.rotation_euler = (-d).to_track_quat('-Z', 'Z' if abs(d.z) < 0.99 else 'Y').to_euler()
            sc.render.filepath = tmp
            bpy.ops.render.render(write_still=True)
            img = bpy.data.images.load(tmp, check_existing=False)
            px = img.pixels[:]
            for k in range(0, len(px), 4):
                if px[k + 3] < 0.5:
                    continue
                i = int(round(px[k] * 255)) + (int(round(px[k + 1] * 255)) << 8) + (int(round(px[k + 2] * 255)) << 16)
                if i:
                    seen.add(i - 1)
            bpy.data.images.remove(img)
    # restore scene
    me.materials.clear()
    for m in saved_mats:
        me.materials.append(m)
    bpy.data.materials.remove(idmat)
    me.attributes.remove(me.attributes['face_id'])
    bpy.data.objects.remove(cam); bpy.data.cameras.remove(cd)
    for o in hidden:
        o.hide_render = False
    sc.render.engine = st['engine']; sc.render.resolution_x, sc.render.resolution_y = st['res']
    sc.view_settings.view_transform = st['vt']; sc.render.film_transparent = st['film']
    sc.camera = st['cam']; sc.render.image_settings.file_format = st['fmt']
    ad.action = None; sc.frame_set(0)
    # delete never-seen faces
    import bmesh
    bm = bmesh.new(); bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    doomed = [f for f in bm.faces if f.index not in seen]
    tris = sum(len(f.verts) - 2 for f in doomed)
    bmesh.ops.delete(bm, geom=doomed, context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bm.to_mesh(me); me.update(); bm.free()
    return tris
