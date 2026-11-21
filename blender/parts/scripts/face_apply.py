import bpy,sys,numpy as np
from PIL import Image
SRC,OUT=sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=SRC)
art=np.array(Image.open('/tmp/w/parts/face_art.png').convert('RGB')).astype(np.float32)/255; R=art.shape[0]
hd=bpy.data.objects['Head']; me=hd.data; mw=hd.matrix_world
FW,FH=2048,1024; SK=np.array([245,206,176])/255.0
img=np.zeros((FH,FW,3),np.float32); img[:]=SK
uvd=me.uv_layers[0].data
for p in me.polygons:
    li=list(p.loop_indices)
    for k in range(1,len(li)-1):
        tri=[li[0],li[k],li[k+1]]
        U=np.array([[uvd[i].uv[0]*FW,(1-uvd[i].uv[1])*FH] for i in tri]); Wd=np.array([list(mw@me.vertices[me.loops[i].vertex_index].co) for i in tri])
        x0,y0=np.floor(U.min(0)).astype(int)-1; x1,y1=np.ceil(U.max(0)).astype(int)+1
        gx,gy=np.meshgrid(np.arange(x0,x1+1)+0.5,np.arange(y0,y1+1)+0.5)
        dd=(U[1,1]-U[2,1])*(U[0,0]-U[2,0])+(U[2,0]-U[1,0])*(U[0,1]-U[2,1])
        if abs(dd)<1e-9: continue
        w0=((U[1,1]-U[2,1])*(gx-U[2,0])+(U[2,0]-U[1,0])*(gy-U[2,1]))/dd
        w1=((U[2,1]-U[0,1])*(gx-U[2,0])+(U[0,0]-U[2,0])*(gy-U[2,1]))/dd; w2=1-w0-w1
        ins=(w0>=-0.05)&(w1>=-0.05)&(w2>=-0.05)
        wx=w0*Wd[0,0]+w1*Wd[1,0]+w2*Wd[2,0]; wy=w0*Wd[0,1]+w1*Wd[1,1]+w2*Wd[2,1]; wz=w0*Wd[0,2]+w1*Wd[1,2]+w2*Wd[2,2]
        cx=np.clip(((0.6-wx)/1.2*R).astype(int),0,R-1); cz=np.clip(((5.1-wz)/1.2*R).astype(int),0,R-1)
        yy=np.clip(gy.astype(int),0,FH-1); xx=np.clip(gx.astype(int),0,FW-1)
        front=ins&(wy>0.05)
        img[yy[front],xx[front]]=art[cz[front],cx[front]]
out=Image.fromarray((img*255).astype(np.uint8)); out.save('/tmp/w/parts/tex/Head_Face.png')
fi=bpy.data.images.load('/tmp/w/parts/tex/Head_Face.png'); fi.pack()
hm=bpy.data.materials.new('HeadFacePainted'); hm.use_nodes=True; t=hm.node_tree.nodes.new('ShaderNodeTexImage'); t.image=fi
b=hm.node_tree.nodes['Principled BSDF']; hm.node_tree.links.new(t.outputs['Color'],b.inputs['Base Color']); b.inputs['Roughness'].default_value=0.9
me.materials.clear(); me.materials.append(hm)
sk=bpy.data.materials.new('SkinPainted'); sk.use_nodes=True; sk.diffuse_color=(0.91,0.62,0.43,1); sk.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(0.91,0.62,0.43,1)
for n in ('Left Arm','Right Arm'):
    o=bpy.data.objects[n]; o.data.materials.clear(); o.data.materials.append(sk)
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print('face ok')
