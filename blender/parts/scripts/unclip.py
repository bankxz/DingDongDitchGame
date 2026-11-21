import bpy,bmesh,sys
from mathutils import Vector as V
from mathutils.bvhtree import BVHTree
SRC,OUT=sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=SRC)
dg=bpy.context.evaluated_depsgraph_get()
co=bpy.data.objects['Gear_Torso']; bm=bmesh.new(); bm.from_object(co,dg); bm.transform(co.matrix_world); coat=BVHTree.FromBMesh(bm)
tot=0
for n in ('Gear_RightLeg','Gear_LeftLeg','Gear_Kimono','Gear_HakamaWaist'):
    o=bpy.data.objects[n]; mw=o.matrix_world; mi=mw.inverted(); me=o.data; moved=0
    for v in me.vertices:
        p=mw@v.co
        if p.z<0.45 or p.z>3.1: continue
        c=V((0,-0.05,p.z)); d=V((p.x,p.y+0.05,0))
        if d.length<1e-4: continue
        d.normalize(); dist=(p-c).length
        h=coat.ray_cast(c,d,dist+0.2)   # first coat surface (inner lining) from the axis
        if h[0] is None: continue
        if p.y>0.2 and abs(p.x)<0.6: continue      # in the front opening: nothing to hide behind
        lim=(h[0]-c).length-0.02
        if dist>lim:
            v.co=mi@(c+d*lim); moved+=1
    print(n,'moved',moved); tot+=moved
bpy.ops.wm.save_as_mainfile(filepath=OUT); print('total',tot)
