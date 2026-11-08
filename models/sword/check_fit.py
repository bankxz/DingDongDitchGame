import bpy, cv2, numpy as np, math, json
S='/tmp/claude-0/-home-user-DingDongDitchGame/25723ca7-107e-59a5-b2ba-96635f274c48/scratchpad/'
bpy.ops.wm.open_mainfile(filepath='/home/user/DingDongDitchGame/models/sword/sword_model.blend')
sc=bpy.context.scene
sc.render.engine='CYCLES'; sc.cycles.device='CPU'; sc.cycles.samples=4; sc.cycles.use_denoising=False
sc.world=bpy.data.worlds.new('w'); sc.world.color=(1,1,1); sc.world.use_nodes=False
blk=bpy.data.materials.new('blk'); blk.use_nodes=True
blk.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(0,0,0,1)
blk.node_tree.nodes['Principled BSDF'].inputs['Specular IOR Level'].default_value=0
for o in bpy.data.objects:
    if o.type=='MESH': o.data.materials.clear(); o.data.materials.append(blk)
H=850; SC=1.2/850
cam=bpy.data.objects.new('cam',bpy.data.cameras.new('cam')); bpy.context.collection.objects.link(cam)
cam.data.type='ORTHO'; cam.data.ortho_scale=H*SC; sc.camera=cam
sc.render.resolution_x=sc.render.resolution_y=H
zc=-((11+861)/2-500)*SC
views={'front':((0,-3,zc),(math.pi/2,0,0)),'side':((3,0,zc),(math.pi/2,0,math.pi/2))}
m=cv2.imread(S+'ref/3.png',0)<235
# absolute centres in ref coordinates
rows=np.arange(11,862)
def cen(x0,x1):
    c=[(np.where(m[y,x0:x1])[0].max()+np.where(m[y,x0:x1])[0].min())/2+x0 for y in rows if m[y,x0:x1].any()]
    return np.median(c)
refs={'front':(m[11:861,40:239],139.5-40),'side':(m[11:861,951:1033],cen(951,1033)-951+0.5)}
LIM=646; res={}
for k,(loc,rot) in views.items():
    cam.location=loc; cam.rotation_euler=rot
    sc.render.filepath=S+f'render_{k}.png'; bpy.ops.render.render(write_still=True)
    r=cv2.imread(S+f'render_{k}.png',0)<20
    rr,c0=refs[k]; w=rr.shape[1]
    x0=int(round(425-c0)); sub=r[:,x0:x0+w]
    a=sub[:LIM]; b=rr[:LIM]
    res[k]=dict(iou_body=round(float((a&b).sum()/(a|b).sum()),3))
    for name,(p,q) in {'blade':(0,440),'guard':(440,550),'grip':(550,615),'cap':(615,646)}.items():
        res[k][name]=round(float((sub[p:q]&rr[p:q]).sum()/(sub[p:q]|rr[p:q]).sum()),3)
    ov=np.zeros((850,w,3),np.uint8); ov[...,2]=sub*255; ov[...,1]=rr*255
    cv2.imwrite(S+f'overlay_{k}.png',ov)
print('FIT2',json.dumps(res))
