import sys; sys.path.insert(0,'/tmp/w/parts')
import bpy, bmesh
from common import *
from mathutils.bvhtree import BVHTree
SRC,OUT=sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=SRC)
M=mats(); HK=mat('Hakama',(0.20,0.18,0.36),0,0.8); HKD=mat('HakamaDark',(0.11,0.10,0.21),0,0.85)
BT=mat('Boot',(0.10,0.10,0.15),0,0.6)
for n in ('Gear_LeftLeg','Gear_RightLeg','Gear_HakamaWaist'):
    o=bpy.data.objects.get(n)
    if o: bpy.data.objects.remove(o)
I_=lambda tab,y: float(np.interp(y,[a for a,b in tab],[b for a,b in tab]))
# measured profile per leg (studs): outer x, front y, back y, by sheet row
XO=[(600,1.0),(640,1.03),(700,1.09),(760,1.15),(820,1.22),(870,1.29),(905,1.31)]
YF=[(600,0.545),(640,0.56),(700,0.64),(760,0.73),(820,0.82),(870,0.91),(905,0.95)]
YB=[(600,-0.53),(700,-0.55),(800,-0.575),(905,-0.60)]
ROWS=[600,620,640,670,700,730,760,790,820,845,870,890,900,905]
N=156; TH=0.03
def section(y,sx,off=0.0):
    xo=I_(XO,y)-off; xi=0.012+off; yf=I_(YF,y)-off; yb=I_(YB,y)+off
    cx=sx*(xi+xo)/2; hx=(xo-xi)/2; cy=(yf+yb)/2; hy=(yf-yb)/2
    g=min(1,max(0,(y-610)/(905-610)))**0.8       # pleats deepen toward the hem
    pts=[]
    for k in range(N):
        t=2*pi*k/N; s,c=math.sin(t),math.cos(t)
        n=5.0
        x=hx*math.copysign(abs(s)**(2/n),s); yy=hy*math.copysign(abs(c)**(2/n),c)
        # box pleats: 9 per leg around, crease = sharp inward V, panels flat
        ph=(k/N*13)%1.0; crease=max(0,1-abs(ph-0.5)/0.14)
        r=1.0-(0.035*crease)*g/max(hx,hy)
        pts.append((cx+x*r,cy+yy*r,Zmap(y)))
    return pts
def leg(bone,sx):
    P=Part('Gear_'+bone.replace(' ',''),bone)
    O=[section(y,sx) for y in ROWS]; In=[section(y,sx,TH) for y in ROWS]
    for i in range(len(ROWS)-1):
        for k in range(N):
            j=(k+1)%N
            q=[O[i][k],O[i][j],O[i+1][j],O[i+1][k]]
            ph=((k+0.5)/N*13)%1.0; m=HKD if abs(ph-0.5)<0.10 else HK
            P.face(q,m); P.face([In[i][j],In[i][k],In[i+1][k],In[i+1][j]],HKD)
    # rolled hem lip (rounded bottom edge)
    for k in range(N):
        j=(k+1)%N; a,b=O[-1][k],O[-1][j]; c,d=In[-1][j],In[-1][k]
        mid=lambda p,q: ((p[0]+q[0])/2,(p[1]+q[1])/2,p[2]-0.012)
        P.face([a,b,mid(b,c),mid(a,d)],HK); P.face([mid(a,d),mid(b,c),c,d],HKD)
    for k in range(N):
        j=(k+1)%N; P.face([O[0][j],O[0][k],In[0][k],In[0][j]],HK)
    # boot: rounded box, measured (x 0.06..1.16, y -0.53..0.875, z 0..0.307), bevel 0.045
    x0,x1=0.06,1.16; yb_,yf_=-0.53,0.875; zt=Zmap(908); r=0.06
    if sx<0: x0,x1=-x1,-x0
    cx=(x0+x1)/2; hx=(x1-x0)/2; cy=(yf_+yb_)/2; hy=(yf_-yb_)/2
    def rr(z,inset):
        return [(p[0],p[1],z) for p in rrect(cx,cy,hx-inset,hy-inset,max(0.02,r-inset),0,4)]
    rings=[rr(0.0,0.035),rr(0.012,0.0),rr(zt-0.03,0.0),rr(zt-0.008,0.012),rr(zt,0.04)]
    P.loft(rings,BT,cap0=BT,cap1=BT)
    # gold band: four raised strips (inset from the corners), z 0.06..0.11
    zb=(Zmap(948)+Zmap(940))/2
    def face_strip(a,b,n):
        strip(P,[tuple(V(a).lerp(V(b),t)) for t in np.linspace(0,1,6)],[V(n)]*6,0.026,0.014,M['Gold'])
    ins=0.09
    face_strip((x0+ins,yf_,zb),(x1-ins,yf_,zb),(0,1,0)); face_strip((x0+ins,yb_,zb),(x1-ins,yb_,zb),(0,-1,0))
    face_strip((x1,yb_+ins,zb),(x1,yf_-ins,zb),(1,0,0)); face_strip((x0,yb_+ins,zb),(x0,yf_-ins,zb),(-1,0,0))
    return P
parts=[leg('Right Leg',1),leg('Left Leg',-1)]
# hakama waist band (torso): from obi bottom to hip, joins both legs
W=Part('Gear_HakamaWaist','Torso')
def wring(z,off=0.0):
    return [(p[0],p[1],z) for p in rrect(0,0.0,1.005-off,0.545-off,0.12,0,5)]
W.loft([wring(Zmap(598)),wring(2.0),wring(Zmap(612))],HK,cap0=HK,cap1=HK)
# white hakama tie end peeking out on the front right (sheet x~225, y 602-650)
tree=BVHTree.FromPolygons([V(v) for v in parts[0].v],[ids for ids,_ in parts[0].f])
pts=[];nr=[]
for t in np.linspace(0,1,8):
    px=232-10*t; py=604+44*t; o=V((XF(px),5,Zmap(py))); h=tree.ray_cast(o,V((0,-1,0)),10)
    if h[0] is not None: pts.append(tuple(h[0])); nr.append(h[1] if h[1].y>0 else -h[1])
if len(pts)>1: strip(parts[0],pts,nr,0.022,0.014,M['White'])
for p in parts+[W]:
    ob=p.build(); print(ob.name,'tris',sum(len(q.vertices)-2 for q in ob.data.polygons))
bpy.ops.wm.save_as_mainfile(filepath=OUT)
