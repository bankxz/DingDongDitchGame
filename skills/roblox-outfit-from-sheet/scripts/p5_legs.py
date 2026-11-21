import sys; sys.path.insert(0,'/tmp/w/parts')
import bpy, bmesh
from common import *
from mathutils.bvhtree import BVHTree
SRC,OUT=sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=SRC)
M=mats(); HK=mat('Hakama',(0.20,0.18,0.36),0,0.8); HKD=mat('HakamaDark',(0.11,0.10,0.21),0,0.85)
BT=mat('Boot',(0.17,0.16,0.25),0,0.55); BTL=mat('BootEdge',(0.30,0.29,0.40),0,0.45); BTD=mat('BootPanel',(0.13,0.12,0.20),0,0.6)
for n in ('Gear_LeftLeg','Gear_RightLeg','Gear_HakamaWaist'):
    o=bpy.data.objects.get(n)
    if o: bpy.data.objects.remove(o)
I_=lambda tab,y: float(np.interp(y,[a for a,b in tab],[b for a,b in tab]))
# measured profile per leg (studs): outer x, front y, back y, by sheet row
XO=[(600,1.0),(640,1.02),(700,1.06),(760,1.10),(820,1.14),(870,1.18),(905,1.20)]
YF=[(600,0.545),(640,0.565),(700,0.60),(760,0.635),(820,0.67),(870,0.705),(905,0.725)]
YB=[(600,-0.53),(640,-0.55),(700,-0.585),(760,-0.62),(820,-0.655),(870,-0.69),(905,-0.71)]
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
    # boot (measured from the sheet): navy-black block, chamfered vertical edges, chamfered sole edge, soft top,
    # continuous gold band wrapping all the way round at z 0.061-0.110
    x0,x1=0.006,1.03; yb_,yf_=-0.53,0.53; zt=Zmap(908); C=0.055
    if sx<0: x0,x1=-x1,-x0
    cx=(x0+x1)/2; hx=(x1-x0)/2; cy=(yf_+yb_)/2; hy=(yf_-yb_)/2
    def oc(z,inset=0.0,c=0.04): return [(p[0],p[1],z) for p in rrect(cx,cy,hx-inset,hy-inset,max(0.01,c-inset),0,4)]
    zb0,zb1=Zmap(948),Zmap(940)
    zb0,zb1=Zmap(950),Zmap(939)
    rings=[oc(0.0,0.03),oc(0.008,0.012),oc(0.022,0.0),oc(zb0-0.004,0.0),oc(zb0,0.008),oc(zb1,0.008),oc(zb1+0.004,0.0),
           oc(zt-0.03,0.0),oc(zt-0.01,0.012),oc(zt,0.04)]
    for i in range(len(rings)-1):
        n=len(rings[i])
        for k in range(n):
            j=(k+1)%n
            m=BTL if i in (0,7) else BT
            P.face([rings[i][k],rings[i][j],rings[i+1][j],rings[i+1][k]],m)
    P.face(rings[0][::-1],BT); P.face(rings[-1],BT)
    # gold band: raised bevelled ring in the recess, continuous round the chamfered corners
    zm=(zb0+zb1)/2; hh=(zb1-zb0)/2
    GR=[oc(zb0+0.002,0.006),oc(zb0+0.012,-0.010),oc(zb1-0.012,-0.010),oc(zb1-0.002,0.006)]
    for i in range(3):
        n=len(GR[i])
        for k in range(n):
            j=(k+1)%n; P.face([GR[i][k],GR[i][j],GR[i+1][j],GR[i+1][k]],M['Gold'])
    # subtle sole seam: thin dark groove line above the sole chamfer
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
