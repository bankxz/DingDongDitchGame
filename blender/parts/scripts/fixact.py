import bpy,sys
bpy.ops.wm.open_mainfile(filepath=sys.argv[-1])
for m in bpy.data.materials:
    if m.name.startswith('Low_') and m.use_nodes:
        for n in m.node_tree.nodes:
            if n.type=='TEX_IMAGE' and n.image and n.image.name.endswith('_Color'): m.node_tree.nodes.active=n
bpy.ops.wm.save_mainfile()
