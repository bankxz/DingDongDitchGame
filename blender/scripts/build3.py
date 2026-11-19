import sys; sys.path.insert(0,'/tmp/w/s3')
import bpy, numpy as np, math, cv2
from kit import *
from base import build_base
from relief import trees_from, project, strip_lines
SRC=sys.argv[-2]; OUT=sys.argv[-1]
bpy.ops.wm.open_mainfile(filepath=SRC)
M={
 'Marble':mat('Marble',(0.93,0.90,0.97),0,0.35),
 'Gold':mat('Gold',(0.90,0.68,0.32),0.9,0.3),
 'Navy':mat('Navy',(0.17,0.15,0.30),0,0.8),
 'NavyDark':mat('NavyDark',(0.08,0.07,0.15),0,0.85),
 'Black':mat('Black',(0.06,0.055,0.07),0,0.7),
 'BlackSole':mat('BlackSole',(0.05,0.05,0.06),0,0.8),
 'Purple':mat('Purple',(0.36,0.18,0.52),0,0.6),
 'Lining':mat('Lining',(0.42,0.20,0.62),0,0.6),
 'Cloud':mat('Cloud',(0.76,0.64,0.88),0,0.4),
 'White':mat('WhiteCloth',(0.95,0.94,0.97),0,0.6),
 'Hair':mat('Hair',(0.94,0.92,0.98),0,0.5),
 'HairShade':mat('HairShade',(0.72,0.69,0.82),0,0.6),
 'Skin':mat('Skin',(0.96,0.80,0.68),0,0.8),
 'Glow':mat('GlowPurple',(0.80,0.42,1.0),0,0.4,emit=3.0),
}
P=build_base(M)
TR=trees_from(P)
MK=np.load('/tmp/w/masks3.npz')
G={k:Part('Glow_'+k.replace(' ',''),k) for k in P}
stats={}
stats['cloud']=project(P,TR,'cloud',['F','B','SL','SR'],M['Cloud'],0.012)
wf=lambda vw,a: (240<a[:,0].mean()<336) or a[:,1].mean()>480
stats['white']=strip_lines(P,TR,'white',['F'],M['White'],0.03,filt=wf,minw=6)
stats['gold']=strip_lines(P,TR,'gold',['F','B','SL','SR'],M['Gold'],0.026,minw=5)
stats['glow']=strip_lines(G,TR,'glow',['F','B','SL','SR'],M['Glow'],0.034,minw=4)
print('relief tris',stats)
# cuff glow rings
for bone in ('Right Arm','Left Arm'):
    cx=P[bone].cx
    G[bone].loft([se(cx,0.5375+0.016,-0.04,0.585+0.016,Zmap(y),10,40) for y in (590,599)],M['Glow'],cap0=M['Glow'],cap1=M['Glow'])
import builtins; builtins.P=P; builtins.G=G; builtins.M=M
exec(open('/tmp/w/s3/hair.py').read()) if len(sys.argv)>3 and sys.argv[-3]=='hair' else None
objs=[p.build() for p in list(P.values())+list(G.values()) if p.f]
# rig: materials only
hd=bpy.data.objects['Head']
fi=bpy.data.images.load('/tmp/w/HeadFace.png'); fi.pack()
hm=bpy.data.materials.new('HeadFace'); hm.use_nodes=True; t=hm.node_tree.nodes.new('ShaderNodeTexImage'); t.image=fi
hm.node_tree.links.new(t.outputs['Color'],hm.node_tree.nodes['Principled BSDF'].inputs['Base Color'])
hd.data.materials.clear(); hd.data.materials.append(hm)
for n,m in(('Left Arm','Skin'),('Right Arm','Skin'),('Torso','Navy'),('Left Leg','Navy'),('Right Leg','Navy')):
    o=bpy.data.objects[n]; o.data.materials.clear(); o.data.materials.append(M[m])
bpy.ops.wm.save_as_mainfile(filepath=OUT)
tot=0
for ob in objs:
    t=sum(len(p.vertices)-2 for p in ob.data.polygons); tot+=t; print(f'{ob.name:18s} tris {t}')
print('TOTAL',tot)
