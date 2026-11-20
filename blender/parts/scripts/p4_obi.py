import sys; sys.path.insert(0,'/tmp/w/parts'); sys.path.insert(0,'/tmp/w/s3')
import bpy, bmesh
from common import *
from tripre import tri_safe
import numpy as np
SRC,OUT=sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=SRC)
M=mats(); BLK=mat('ObiBlack',(0.09,0.085,0.10),0,0.75); BLK2=mat('ObiBlack2',(0.15,0.14,0.16),0,0.7)
for n in ('Gear_Kimono','Gear_Tassel'):
    o=bpy.data.objects.get(n)
    if o: bpy.data.objects.remove(o)
K=Part('Gear_Kimono','Torso'); G=Part('Gear_Tassel','Torso')
def se(hx,yf,yb,z,n=8,N=48,mod=None):
    cy=(yf+yb)/2; hy=(yf-yb)/2; out=[]
    for i in range(N):
        t=2*pi*i/N; s,c=math.sin(t),math.cos(t)
        x=hx*math.copysign(abs(s)**(2/n),s); y=cy+hy*math.copysign(abs(c)**(2/n),c)
        k=mod(i,t) if mod else 1.0; out.append((x*k,cy+(y-cy)*k,z))
    return out
YK=0.545    # kimono front plane
# ---------- kimono body (under the obi up to the neck)
K.loft([se(1.006,YK,-0.515,z) for z in (2.55,3.2,3.99)],M['Navy'],cap0=M['Navy'],cap1=M['Navy'])
def F(px,py,y=YK,zmax=3.995): return (XF(px),y,min(Zmap(py),zmax))
def plate(poly,y,th,m,part=K):
    vs=[(float(a),float(b)) for a,b in poly]; t=tri_safe(vs,[(i,(i+1)%len(vs)) for i in range(len(vs))],[],2.0)
    if t is None: return
    v,tr=t
    for t3 in tr:
        part.face([F(*v[i],y+th) for i in t3],m); part.face([F(*v[i],y-0.002) for i in t3][::-1],m)
    for i in range(len(vs)):
        a,b=vs[i],vs[(i+1)%len(vs)]; part.face([F(*a,y+th),F(*b,y+th),F(*b,y-0.002),F(*a,y-0.002)],m)
# neck V (skin), overlapping panel (navy, raised), white collar edges
plate([(256,372),(320,372),(284,412)],YK,0.004,M['Skin'])
plate([(318,372),(345,372),(345,520),(236,520),(238,500)],YK,0.016,M['Navy'])           # overlap panel (wearer's left over right)
def band(p0,p1,w,y,th,m=M['White']):
    import numpy as np
    a=np.array(p0,float); b=np.array(p1,float); d=b-a; n=np.array([-d[1],d[0]])/np.linalg.norm(d)*w/2
    plate([a+n,b+n,b-n,a-n],y,th,m)
band((244,368),(285,413),6.5,YK,0.010)                 # under-collar edge
band((318,368),(237,502),7.0,YK+0.016,0.012)           # over-collar edge (on the raised panel)
# ---------- white sash peeking above the obi (right half + sides/back)
for z0,z1 in ((Zmap(526),Zmap(509)),):
    def skip(i,t,ring): x,y,_=ring[i]; return y>0.2 and x>0.10
    R0=se(1.03,YK+0.02,-0.545,z0); R1=se(1.03,YK+0.02,-0.545,z1,mod=lambda i,t: 1.0-0.012*math.cos(t))
    N=len(R0)
    for i in range(N):
        j=(i+1)%N
        if skip(i,0,R0) and skip(j,0,R0): continue
        K.face([R0[i],R0[j],R1[j],R1[i]],M['White'])
# crescent fold on the front right
plate([(268,522),(292,511),(322,506),(343,507),(347,514),(330,523),(298,527)],YK+0.035,0.03,M['White'])
# ---------- obi: three wrapped bands with slight tilts and offsets (black), plus fold creases
ZT,ZB=Zmap(520),Zmap(598)
bands=[(ZB,ZB+(ZT-ZB)*0.40,0.00,0.0),(ZB+(ZT-ZB)*0.33,ZB+(ZT-ZB)*0.72,0.045,0.008),(ZB+(ZT-ZB)*0.64,ZT,-0.035,0.016)]
for (za,zb,tilt,grow) in bands:
    Rm=Matrix.Rotation(tilt,3,'Y'); zc=(za+zb)/2; rings=[]
    for z,k in ((za,0.0),(za+0.02,0.012),(zb-0.02,0.012),(zb,0.0)):
        rr=se(1.008+grow*0.3+k*0.3,0.556+grow*0.3+k*0.3,-0.535-grow*0.3-k*0.3,0,8,72)
        rr=[(p[0],p[1]+(0.055+grow+k*0.5)*math.exp(-(p[0]/0.33)**2) if p[1]>0 else p[1],p[2]) for p in rr]
        rings.append([tuple(Rm@V((p[0],p[1],z-zc))+V((0,0,zc))) for p in rr])
    K.loft(rings,BLK,cap0=BLK,cap1=BLK)
# ---------- knot tab (chunky lump), protruding, then hanging tail behind the tassel
def boxp(x0,x1,z0,z1,y0,y1,m,taper=0.0):
    p=[(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0+taper,y0,z1),(x1-taper,y0,z1),(x1-taper,y1,z1),(x0+taper,y1,z1)]
    for q in ((0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)): K.face([p[i] for i in q],m)
xa,xb=XF(358),XF(323)
# knot: soft rounded fabric tab, wraps over the obi top and hangs down (rounded sections, slight twist)
cx0=(xa+xb)/2; hw0=(xb-xa)/2; rings=[]
SEC=[(508,0.62,0.70,0.03),(512,0.70,0.85,0.04),(520,0.80,0.98,0.05),(535,0.86,1.0,0.05),(552,0.86,0.97,0.04),(570,0.82,0.92,0.03),(588,0.82,0.86,0.02),(600,0.82,0.80,0.01)]
for py,dep,w,tw in SEC:
    z=Zmap(py); hw=hw0*w; cy=(YK+0.02+dep)/2; hy=(dep-(YK+0.02))/2; ring=[]
    for k in range(16):
        t=2*pi*k/16; sx,cyy=math.cos(t),math.sin(t)
        x=cx0+hw*math.copysign(abs(sx)**0.6,sx); y=cy+hy*math.copysign(abs(cyy)**0.8,cyy)
        x+=tw*(y-cy)                                   # slight twist
        ring.append((x,y,z))
    rings.append(ring)
K.loft(rings,BLK2,cap0=BLK2,cap1=BLK2)
# fold ridges across the obi front (diagonal creases), visible between the lapels
for (p0,p1) in (((215,540),(330,560)),((225,575),(330,553)),((215,592),(320,580)),((240,528),(320,540))):
    pts=[];nr=[]
    for t in np.linspace(0,1,14):
        px=p0[0]+(p1[0]-p0[0])*t; py=p0[1]+(p1[1]-p0[1])*t; x=XF(px); z=Zmap(py)
        y=0.556+0.055*math.exp(-(x/0.33)**2)+0.02
        pts.append((x,y,z)); nr.append(V((0,1,0)))
    strip(K,pts,nr,0.022,0.012,BLK2)
# tail: from under the knot down to y 702, widening, slight outward lean
rings=[]
for py,x0,x1,yy in ((596,326,357,0.66),(640,316,362,0.665),(680,306,366,0.672),(704,302,368,0.676)):
    z=Zmap(py); rings.append([(XF(x1),yy,z),(XF(x0),yy,z),(XF(x0),yy+0.03,z),(XF(x1),yy+0.03,z)])
K.loft(rings,BLK,cap0=BLK,cap1=BLK)
# ---------- gold ring + cord + tassel (separate object)
RC=V((XF(338),0.80,Zmap(592)))
for i in range(28):
    pass
NR=28; NW=8; Rr=0.112; rw=0.020; rings=[]
for i in range(NR+1):
    a=2*pi*i/NR; c=RC+V((math.cos(a)*Rr,0,math.sin(a)*Rr)); u=V((math.cos(a),0,math.sin(a)))
    rings.append([tuple(c+u*math.cos(b)*rw+V((0,1,0))*math.sin(b)*rw) for b in [2*pi*k/NW for k in range(NW)]])
G.loft(rings,M['Gold'])
tas=np.load('/tmp/w/masks.npz')['tas']
TC=(XF(337),0.80)
prof=[(Zmap(600),0.012),(Zmap(608),0.016)]
for py in range(612,712,3):
    xs=np.nonzero(tas[py,300:370])[0]
    if len(xs): prof.append((Zmap(py),max(0.016,(xs.max()-xs.min()+1)/2/S)))
zz=np.array([p[0] for p in prof[2:]]); rr=np.array([p[1] for p in prof[2:]])
rr=np.convolve(np.pad(rr,(3,3),mode='edge'),np.ones(7)/7,mode='valid')
prof=prof[:2]+list(zip(zz,rr))
prof.append((prof[-1][0]-0.006,0.02))
NT=24; rings=[]
for z,r in prof:
    pleat=lambda j: 1.0-0.04*(j%2) if z<Zmap(655) else 1.0
    rings.append([(TC[0]+r*pleat(j)*math.cos(2*pi*j/NT),TC[1]+r*pleat(j)*math.sin(2*pi*j/NT),z) for j in range(NT)])
G.loft(rings,M['Gold'],cap0=M['Gold'],cap1=M['Gold'])
for p in (K,G):
    ob=p.build(); print(ob.name,'tris',sum(len(q.vertices)-2 for q in ob.data.polygons))
bpy.ops.wm.save_as_mainfile(filepath=OUT)
