# Stage 1: build geometry, join into one mesh, UV-unwrap, bake a single colour atlas
# (painted studs + lava cracks + flame gradient) and an emissive mask. Saves LavaHorse_stage1.blend.
import sys, os, bpy, math
sys.path.insert(0, os.path.dirname(__file__))
import build_geo

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
TEX = os.path.join(ROOT, 'textures')
RES = 2048


def lin(h):
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c) + (1.0,)


# palette taken from the reference sheet swatches
DARK_BROWN, DARK_RED, ORANGE_RED, ORANGE, YELLOW, PALE = \
    '#341f1f', '#9a1f1d', '#fe4408', '#fda709', '#fddd1d', '#fefc96'


class NB:
    """Tiny node-building helper."""
    def __init__(self, mat):
        self.nt = mat.node_tree
        self.nt.nodes.clear()
        self.out = self.nt.nodes.new('ShaderNodeOutputMaterial')

    def n(self, t, **inputs):
        node = self.nt.nodes.new(t)
        for k, v in inputs.items():
            if k.startswith('_'):
                setattr(node, k[1:], v)
            else:
                self.set(node, k, v)
        return node

    def set(self, node, key, v):
        sock = node.inputs[key] if not isinstance(key, int) else node.inputs[key]
        if hasattr(v, 'bl_idname') or isinstance(v, bpy.types.NodeSocket):
            self.nt.links.new(v if isinstance(v, bpy.types.NodeSocket) else v.outputs[0], sock)
        else:
            sock.default_value = v

    def math(self, op, a, b=0.0, clamp=False):
        m = self.n('ShaderNodeMath', _operation=op, _use_clamp=clamp)
        self.set(m, 0, a); self.set(m, 1, b)
        return m.outputs[0]

    def mix(self, fac, a, b, blend='MIX'):
        m = self.n('ShaderNodeMix', _data_type='RGBA', _blend_type=blend, _clamp_result=False)
        self.set(m, 'Factor', fac)
        self.set(m, 6, a); self.set(m, 7, b)
        return m.outputs[2]

    def smooth(self, v, a, b):
        m = self.n('ShaderNodeMapRange', _interpolation_type='SMOOTHSTEP')
        self.set(m, 'Value', v)
        m.inputs['From Min'].default_value = a
        m.inputs['From Max'].default_value = b
        return m.outputs[0]


def stud_factor(b, strength=1.0):
    uv = b.n('ShaderNodeUVMap', _uv_map='StudUV')
    img = bpy.data.images.load(os.path.join(TEX, 'stud_tile.png'), check_existing=True)
    img.colorspace_settings.name = 'Non-Color'
    tex = b.n('ShaderNodeTexImage', _image=img, _interpolation='Cubic')
    b.set(tex, 'Vector', uv.outputs[0])
    # 0.5 -> 1.0 (neutral); scaled contrast
    m = b.n('ShaderNodeMath', _operation='MULTIPLY_ADD')
    b.set(m, 0, tex.outputs['Color']); m.inputs[1].default_value = 2.0 * strength
    m.inputs[2].default_value = 1.0 - strength
    return m.outputs[0]


def crack_dist(b, scale=0.5):
    """Lava crack network: 2D Voronoi edges in each face's own stud plane (clean lines, no blobs on
    faces that happen to lie along a 3D cell wall), offset per face plane so sides don't repeat."""
    rest = b.n('ShaderNodeAttribute', _attribute_name='rest', _attribute_type='GEOMETRY')
    geo = b.n('ShaderNodeNewGeometry')
    uv = b.n('ShaderNodeUVMap', _uv_map='StudUV')
    plane = b.n('ShaderNodeVectorMath', _operation='DOT_PRODUCT')
    b.set(plane, 0, rest.outputs['Vector']); b.set(plane, 1, geo.outputs['Normal'])
    nsum = b.n('ShaderNodeVectorMath', _operation='DOT_PRODUCT')
    b.set(nsum, 0, geo.outputs['Normal']); nsum.inputs[1].default_value = (3.1, 5.7, 7.3)
    w = b.math('ADD', b.math('MULTIPLY', plane.outputs['Value'], 1.7), nsum.outputs['Value'])
    comb = b.n('ShaderNodeCombineXYZ')
    b.set(comb, 0, w); b.set(comb, 1, b.math('MULTIPLY', w, 1.37))
    p2 = b.n('ShaderNodeVectorMath', _operation='MULTIPLY_ADD')
    b.set(p2, 0, uv.outputs['UV']); p2.inputs[1].default_value = (2.0, 2.0, 0.0)   # StudUV -> world units
    b.set(p2, 2, comb.outputs[0])
    noise = b.n('ShaderNodeTexNoise', Scale=0.9, Detail=2.0)
    b.set(noise, 'Vector', p2.outputs[0])
    off = b.n('ShaderNodeVectorMath', _operation='MULTIPLY_ADD')
    b.set(off, 0, noise.outputs['Color']); off.inputs[1].default_value = (0.25, 0.25, 0.0)
    b.set(off, 2, p2.outputs[0])
    vor = b.n('ShaderNodeTexVoronoi', _voronoi_dimensions='2D', _feature='DISTANCE_TO_EDGE', Scale=scale,
              Randomness=0.85)
    b.set(vor, 'Vector', off.outputs[0])
    # hand-placed seams from the reference: chest centre line and the ring around the barrel
    sep = b.n('ShaderNodeSeparateXYZ'); b.set(sep, 0, rest.outputs['Vector'])
    ax = b.math('ABSOLUTE', sep.outputs['X'])
    # chest "Y": centre line down to z=3.0, then splitting toward both front legs
    zt = b.math('SUBTRACT', 3.0, sep.outputs['Z'])
    below = b.math('GREATER_THAN', zt, 0.0)
    diag = b.math('MULTIPLY', b.math('ABSOLUTE', b.math('SUBTRACT', ax, b.math('MULTIPLY', b.math('MAXIMUM', zt, 0.0), 0.9))), 0.74)
    yline = b.math('ADD', ax, b.math('MULTIPLY', below, b.math('SUBTRACT', diag, ax)))
    chest = b.math('ADD', yline, b.math('MULTIPLY', b.math('GREATER_THAN', sep.outputs['Y'], -2.6), 10.0))
    ring = b.math('ABSOLUTE', b.math('SUBTRACT', sep.outputs['Y'], 0.25))
    outside = b.math('ADD', b.math('LESS_THAN', sep.outputs['Z'], 2.0), b.math('GREATER_THAN', sep.outputs['Z'], 3.95))
    ring = b.math('ADD', ring, b.math('MULTIPLY', outside, 10.0))
    seams = b.math('MULTIPLY', b.math('MINIMUM', chest, ring), scale)
    # the reference head is mostly clean plates: suppress random cracks above/ahead of the throat
    head = b.math('MULTIPLY', b.math('LESS_THAN', sep.outputs['Y'], -3.35), b.math('GREATER_THAN', sep.outputs['Z'], 4.0))
    front = b.math('LESS_THAN', sep.outputs['Y'], -2.75)          # clean chest plate
    vd = b.math('ADD', vor.outputs['Distance'], b.math('MULTIPLY', b.math('MAXIMUM', head, front), 5.0))
    return b.math('MINIMUM', vd, seams), rest


def material_for(cat):
    mat = bpy.data.materials.new('BAKE_' + cat)
    b = NB(mat)
    emissive = 0.0
    if cat == 'lava':
        d, rest = crack_dist(b)
        noise = b.n('ShaderNodeTexNoise', Scale=1.6, Detail=3.0)
        b.set(noise, 'Vector', rest.outputs['Vector'])
        base = b.mix(noise.outputs['Fac'], lin('#a3221a'), lin('#d0361d'))
        halo = b.math('SUBTRACT', 1.0, b.smooth(d, 0.03, 0.15))            # plates glow near cracks
        col = b.mix(b.math('MULTIPLY', halo, 0.6), base, lin('#f2560c'))
        col = b.mix(1.0, col, stud_factor(b, 1.0), 'MULTIPLY')
        core = b.math('SUBTRACT', 1.0, b.smooth(d, 0.03, 0.05))
        hot = b.mix(b.math('SUBTRACT', 1.0, b.smooth(d, 0.0, 0.028)), lin(ORANGE), lin('#ffd84a'))
        col = b.mix(core, col, hot)
        emissive = b.math('MAXIMUM', core, b.math('MULTIPLY', halo, 0.35))
    elif cat == 'flame':
        g = b.n('ShaderNodeAttribute', _attribute_name='grad', _attribute_type='GEOMETRY')
        ramp = b.n('ShaderNodeValToRGB')
        cr = ramp.color_ramp
        cr.elements[0].position = 0.0; cr.elements[0].color = lin(ORANGE_RED)
        cr.elements[1].position = 1.0; cr.elements[1].color = lin('#ffe650')
        for pos, h in ((0.45, '#ff5406'), (0.78, ORANGE), (0.95, YELLOW)):
            e = cr.elements.new(pos); e.color = lin(h)
        b.set(ramp, 'Fac', g.outputs['Fac'])
        col = b.mix(1.0, ramp.outputs['Color'], stud_factor(b, 0.8), 'MULTIPLY')
        emissive = 0.55
    elif cat in ('rock', 'hoof', 'muzzle'):
        rest = b.n('ShaderNodeAttribute', _attribute_name='rest', _attribute_type='GEOMETRY')
        noise = b.n('ShaderNodeTexNoise', Scale=2.2, Detail=2.0)
        b.set(noise, 'Vector', rest.outputs['Vector'])
        a, c = {'rock': ('#3a2422', '#4e3431'), 'hoof': ('#3a2e30', '#4a3a3c'),
                'muzzle': ('#5a1f1a', '#6e2a22')}[cat]
        col = b.mix(noise.outputs['Fac'], lin(a), lin(c))
        col = b.mix(1.0, col, stud_factor(b, 1.35), 'MULTIPLY')
    elif cat == 'eye_white':
        col = lin('#ffffff'); emissive = 0.6
    elif cat == 'eye_black':
        col = lin('#07070a')
    # colour pass -> Emission (so EMIT bake captures the flat albedo); emissive mask stored as custom prop
    em = b.n('ShaderNodeEmission', Strength=1.0)
    b.set(em, 'Color', col)
    b.nt.links.new(em.outputs[0], b.out.inputs['Surface'])
    # a second output tree for the emissive mask bake
    em2 = b.n('ShaderNodeEmission', Strength=1.0)
    if isinstance(emissive, float):
        em2.inputs['Color'].default_value = (emissive, emissive, emissive, 1)
    else:
        b.set(em2, 'Color', emissive)
    mat['mask_node'] = em2.name
    mat['color_node'] = em.name
    return mat


def switch_output(mats, key):
    for m in mats:
        nt = m.node_tree
        out = [n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'][0]
        nt.links.new(nt.nodes[m[key]].outputs[0], out.inputs['Surface'])


def main():
    parts = build_geo.build_all()
    mats = {}
    for ob, cat, bone in parts:
        if cat not in mats:
            mats[cat] = material_for(cat)
        ob.data.materials.append(mats[cat])
    # join
    bpy.ops.object.select_all(action='DESELECT')
    objs = [p[0] for p in parts]
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    horse = bpy.context.view_layer.objects.active
    horse.name = 'LavaHorse'; horse.data.name = 'LavaHorseMesh'
    tris = sum(len(p.vertices) - 2 for p in horse.data.polygons)
    print('TRIS', tris)
    assert tris < 5000
    # UV unwrap into UVMap
    me = horse.data
    me.uv_layers.active = me.uv_layers['UVMap']
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.003, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.pack_islands(margin=0.0025, rotate=True)
    bpy.ops.object.mode_set(mode='OBJECT')
    # bake setup
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = 16
    sc.render.bake.margin = 8
    sc.render.bake.use_clear = True
    results = {}
    for key, fname, cs in (('color_node', 'LavaHorse_Color', 'sRGB'), ('mask_node', 'LavaHorse_Emissive', 'Non-Color')):
        img = bpy.data.images.new(fname, RES, RES, alpha=False)
        img.colorspace_settings.name = cs
        for m in mats.values():
            nt = m.node_tree
            tn = nt.nodes.get('BAKE_TARGET') or nt.nodes.new('ShaderNodeTexImage')
            tn.name = 'BAKE_TARGET'; tn.image = img
            nt.nodes.active = tn
        switch_output(mats.values(), key)
        bpy.ops.object.select_all(action='DESELECT')
        horse.select_set(True)
        bpy.context.view_layer.objects.active = horse
        bpy.ops.object.bake(type='EMIT', margin=8)
        img.filepath_raw = os.path.join(TEX, fname + '.png')
        img.file_format = 'PNG'
        img.save()
        results[key] = img
        if key == 'color_node':
            sm = img.copy(); sm.scale(1024, 1024)
            sm.filepath_raw = os.path.join(TEX, fname + '_1024.png'); sm.file_format = 'PNG'; sm.save()
            bpy.data.images.remove(sm)
        print('BAKED', fname)
    # final single material (Roblox: one mesh, one texture)
    horse.data.materials.clear()
    fm = bpy.data.materials.new('LavaHorse_Mat')
    nt = fm.node_tree
    bsdf = nt.nodes['Principled BSDF']
    ct = nt.nodes.new('ShaderNodeTexImage'); ct.image = results['color_node']; ct.location = (-500, 200)
    mt = nt.nodes.new('ShaderNodeTexImage'); mt.image = results['mask_node']; mt.location = (-500, -200)
    nt.links.new(ct.outputs['Color'], bsdf.inputs['Base Color'])
    mul = nt.nodes.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'
    mul.inputs['Factor'].default_value = 1.0
    nt.links.new(ct.outputs['Color'], mul.inputs[6]); nt.links.new(mt.outputs['Color'], mul.inputs[7])
    nt.links.new(mul.outputs[2], bsdf.inputs['Emission Color'])
    bsdf.inputs['Emission Strength'].default_value = 1.5
    bsdf.inputs['Roughness'].default_value = 0.55
    horse.data.materials.append(fm)
    me.uv_layers.remove(me.uv_layers['StudUV'])
    for a in ('grad', 'rest'):
        if a in me.attributes:
            me.attributes.remove(me.attributes[a])
    for m in mats.values():
        bpy.data.materials.remove(m)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, 'src', 'LavaHorse_stage1.blend'))
    print('STAGE1_OK')


main()
