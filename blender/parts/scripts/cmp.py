# registered side-by-side: reference crop | model render (same px scale) | 3/4 view
import bpy,sys,math
sys.path.insert(0,'/tmp/w'); import rend
from PIL import Image
BL,TAG=sys.argv[-3],sys.argv[-2]; boxes=eval(sys.argv[-1])   # list of (view, x0,y0,x1,y1 ref px)
bpy.ops.wm.open_mainfile(filepath=BL)
sk=bpy.data.materials.new('pvSkin'); sk.diffuse_color=(0.96**2.2,0.80**2.2,0.68**2.2,1)
nv=bpy.data.materials.new('pvNavy'); nv.diffuse_color=(0.03,0.025,0.07,1)
for n,m in(('Left Arm',sk),('Right Arm',sk),('Torso',nv),('Left Leg',nv),('Right Leg',nv),('Head',sk)):
    o=bpy.data.objects[n]; o.data.materials.clear(); o.data.materials.append(m)
rend.setup((400,400))
sc=bpy.context.scene; sh=sc.display.shading
sh.light='STUDIO'; sh.color_type='MATERIAL'; sh.show_cavity=True; sh.cavity_type='BOTH'; sh.background_color=(0.71,0.70,0.70)
ref=Image.open('/tmp/w/ref.png')
rows=[]
for i,(view,x0,y0,x1,y1) in enumerate(boxes):
    Wpx=x1-x0; Hpx=y1-y0
    def wz(py): return 4+(372-py)/130
    zc=(wz(y0)+wz(y1))/2
    if view=='F': xc=(280-(x0+x1)/2)/121; c=(xc,0,zc); az=180
    elif view=='B': xc=((x0+x1)/2-1179.5)/121; c=(xc,0,zc); az=0
    else: yc=(722-(x0+x1)/2)/121; c=(0,yc,zc); az=270
    sc.render.resolution_x=int(Wpx*130/121); sc.render.resolution_y=Hpx
    hs=Hpx/130; ws=Wpx/121
    sc.render.pixel_aspect_x=1; sc.render.pixel_aspect_y=1
    rend.shot(f'/tmp/w/{TAG}_r{i}.png',az,scale=max(hs,ws),center=c)
    r=Image.open(f'/tmp/w/{TAG}_r{i}.png').resize((Wpx,Hpx))
    a=ref.crop((x0,y0,x1,y1))
    k=3
    row=Image.new('RGB',(Wpx*2*k+10,Hpx*k),(255,255,255)); row.paste(a.resize((Wpx*k,Hpx*k)),(0,0)); row.paste(r.resize((Wpx*k,Hpx*k)),(Wpx*k+10,0))
    rows.append(row)
sc.render.resolution_x=500; sc.render.resolution_y=500
rend.shot(f'/tmp/w/{TAG}_q.png',215,el=15,scale=3.2,center=(1.5,0,3.1))
rend.shot(f'/tmp/w/{TAG}_q2.png',35,el=15,scale=3.2,center=(-1.5,0,3.1))
W=max(r.width for r in rows)+1000; H=max(sum(r.height for r in rows),1000)
out=Image.new('RGB',(W,H),(255,255,255)); y=0
for r in rows: out.paste(r,(0,y)); y+=r.height
out.paste(Image.open(f'/tmp/w/{TAG}_q.png'),(W-1000,0)); out.paste(Image.open(f'/tmp/w/{TAG}_q2.png'),(W-500,0))
s=1600/out.width; out.resize((1600,int(out.height*s))).save(f'/tmp/w/{TAG}_check.png')
