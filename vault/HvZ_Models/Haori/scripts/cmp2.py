# registered comparison: renders are resampled into the sheet's own px mapping (x: 121 px/stud, z: Zmap) so they overlay 1:1
import bpy,sys,math,numpy as np
sys.path.insert(0,'/tmp/w'); import rend
from PIL import Image
BL,TAG=sys.argv[-3],sys.argv[-2]; boxes=eval(sys.argv[-1])
bpy.ops.wm.open_mainfile(filepath=BL)
sk=bpy.data.materials.new('pvSkin'); sk.diffuse_color=(0.96**2.2,0.80**2.2,0.68**2.2,1)
nv=bpy.data.materials.new('pvNavy'); nv.diffuse_color=(0.03,0.025,0.07,1)
for n,m in(('Left Arm',sk),('Right Arm',sk),('Torso',nv),('Left Leg',nv),('Right Leg',nv),('Head',sk)):
    o=bpy.data.objects[n]; o.data.materials.clear(); o.data.materials.append(m)
rend.setup((800,1100))
sc=bpy.context.scene; sh=sc.display.shading
sh.light='STUDIO'; sh.color_type='MATERIAL'; sh.show_cavity=True; sh.cavity_type='BOTH'; sh.background_color=(0.71,0.70,0.70)
ref=np.array(Image.open('/tmp/w/ref.png').convert('RGB'))
PPS=200.0; W,H=1000,1300; C=(0,0,2.9)
sc.render.resolution_x=W; sc.render.resolution_y=H
def Zm(py): return np.where(py<=632,4+(372-py)/130,(958-py)/163)
rows=[]
for vi,(view,x0,y0,x1,y1) in enumerate(boxes):
    az={'F':180,'B':0,'S':270}[view]
    rend.shot(f"/tmp/w/{TAG}_full{view}.png",az,scale=max(W,H)/PPS,center=C)
    R=np.array(Image.open(f'/tmp/w/{TAG}_full{view}.png').convert('RGB'))
    px=np.arange(x0,x1); py=np.arange(y0,y1)
    if view=='F': hw=(280-px)/121.0; col=(W/2-hw*PPS)        # image-left = +x
    elif view=='B': hw=(px-1179.5)/121.0; col=(W/2+hw*PPS)
    else: hw=(722-px)/121.0; col=(W/2-hw*PPS)               # camera at -x: image-left = +y
    z=Zm(py); rowi=(H/2-(z-C[2])*PPS)
    cc=np.clip(col.round().astype(int),0,W-1); rr=np.clip(rowi.round().astype(int),0,H-1)
    out=R[rr[:,None],cc[None,:]]
    a=ref[y0:y1,x0:x1]
    blend=(0.5*a+0.5*out).astype(np.uint8)
    rows.append(np.hstack([a,np.full((y1-y0,6,3),255,np.uint8),out,np.full((y1-y0,6,3),255,np.uint8),blend]))
Wm=max(r.shape[1] for r in rows); img=np.full((sum(r.shape[0]+8 for r in rows),Wm,3),255,np.uint8); y=0
for r in rows: img[y:y+r.shape[0],:r.shape[1]]=r; y+=r.shape[0]+8
im=Image.fromarray(img); s=1600/im.width; im.resize((1600,int(im.height*s))).save(f'/tmp/w/{TAG}_reg.png')
sc.render.resolution_x=700; sc.render.resolution_y=800
for n,az,el in (('q1',210,12),('q2',30,12),('q3',140,25)):
    rend.shot(f'/tmp/w/{TAG}_{n}.png',az,el=el,scale=6.0,center=(0,-0.2,2.4))
m=Image.new('RGB',(2100,800))
for i,n in enumerate(('q1','q2','q3')): m.paste(Image.open(f'/tmp/w/{TAG}_{n}.png'),(700*i,0))
m.resize((1600,610)).save(f'/tmp/w/{TAG}_ang.png')
