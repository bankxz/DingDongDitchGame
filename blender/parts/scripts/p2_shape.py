import sys; sys.path.insert(0,'/tmp/w/parts')
import bpy
from common import *
SRC,OUT=sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=SRC)
for n in ('Gear_Torso','Glow_Torso'):
    o=bpy.data.objects.get(n)
    if o: bpy.data.objects.remove(o)
M=mats()
I=lambda tab,y: float(np.interp(y,[a for a,b in tab],[b for a,b in tab]))
# ---- measured from the sheet (px rows -> studs) ----
OPL=[(372,250),(500,250),(540,240),(566,226),(612,201),(660,193),(708,183),(756,171),(804,158),(852,147)]
OPR=[(372,323),(500,326),(540,338),(566,352),(612,373),(660,380),(708,389),(756,399),(804,411),(852,413)]
HX=[(372,1.06),(600,1.06),(612,1.12),(630,1.37),(660,1.45),(700,1.555),(750,1.695),(800,1.84),(840,1.965),(852,2.0)]
YB=[(372,-0.57),(560,-0.60),(612,-0.70),(648,-0.785),(696,-0.88),(744,-0.98),(792,-1.08),(828,-1.19),(852,-1.23)]
YF=[(372,0.565),(560,0.60),(620,0.61),(852,0.61)]
F=lambda y: float(np.clip((y-612)/(700-612),0,1))**0.8          # flare/fold strength
G=lambda y: float(np.clip((y-640)/(852-640),0,1))                # folds deepen toward the hem
HEM=lambda yy: 858-18*np.exp(-((yy+0.56)/0.09)**2)+(-7*np.clip((-yy-0.56)/0.66,0,1))   # front 858, seam notch 840, back 851
ROWS=[372,400,450,500,560,600,606,612,618,624,630]+list(range(638,852,8))+[852]
TH=0.035
def chaikin(P,it=2,keep=()):
    for _ in range(it):
        Q=[P[0]]
        for i in range(len(P)-1):
            a,b=np.array(P[i]),np.array(P[i+1]); Q+=[tuple(0.75*a+0.25*b),tuple(0.25*a+0.75*b)]
        Q.append(P[-1]); P=Q
    return P
def resample(P,n):
    P=np.array(P); L=np.r_[0,np.cumsum(np.linalg.norm(np.diff(P,axis=0),axis=1))]
    s=np.linspace(0,L[-1],n); return np.c_[np.interp(s,L,P[:,0]),np.interp(s,L,P[:,1])]
NN=[(372,8),(600,7),(625,4.0),(660,2.9),(760,2.6),(852,2.5)]
def base_pt(y,t,hx,yf,yb,n):
    cy=(yf+yb)/2; hy=(yf-yb)/2
    st,ct=math.sin(t),math.cos(t)
    return (hx*math.copysign(abs(st)**(2/n),st), cy+hy*math.copysign(abs(ct)**(2/n),ct))
def t_for(y,hx,yf,yb,n,cond):
    best=None
    for k in range(1,2000):
        t=pi*k/2000; p=base_pt(y,t,hx,yf,yb,n); c=cond(p)
        if best is None or c<best[0]: best=(c,t)
    return best[1]
def half_outline(y,sx,N=220):
    """outline for one side (+x mirrored by sx) from the front opening round to the back centre, built from fold lobes"""
    f=F(y); g=G(y); n=I(NN,y)
    AS,AB=0.07*f,0.05*f                       # lobe crest heights (side, back)
    hx=I(HX,y)-AS; yf=I(YF,y); yb=I(YB,y)+AB
    xo=abs(XF(I(OPL,y))) if sx>0 else abs(XF(I(OPR,y)))
    t0=t_for(y,hx,yf,yb,n,lambda p: abs(p[0]-xo)+(0 if p[1]>0 else 9))
    # valley positions (measured): front crease, side creases (+0.08,-0.21), seam -0.56, back strip crease, back fold x~0.74
    vs=[t0,
        t_for(y,hx,yf,yb,n,lambda p: abs(p[0]-(hx-0.15))+(0 if p[1]>0.2 else 9)),
        t_for(y,hx,yf,yb,n,lambda p: abs(p[1]-0.08)+(0 if p[0]>0.5 else 9)),
        t_for(y,hx,yf,yb,n,lambda p: abs(p[1]+0.21)+(0 if p[0]>0.5 else 9)),
        t_for(y,hx,yf,yb,n,lambda p: abs(p[1]+0.56)+(0 if p[0]>0.5 else 9)),
        t_for(y,hx,yf,yb,n,lambda p: abs(p[0]-(hx-0.30))+(0 if p[1]<-0.4 else 9)),
        t_for(y,hx,yf,yb,n,lambda p: abs(p[0]-0.74)+(0 if p[1]<-0.4 else 9)),
        pi]
    vs=sorted(vs)
    amps=[0.035,0.06,0.045,0.05,0.06,0.045,0.05]   # crest per lobe (front, front-side, side, side-back, back-side, back, back-centre)
    deps=[0.0,0.035,0.05,0.045,0.07,0.04,0.045,0.06] # valley depth per valley point
    pts=[];zoff=[];seam_k=None
    ts=np.linspace(vs[0],pi,N)
    for t in ts:
        j=min(np.searchsorted(vs,t,side='right')-1,len(vs)-2); u=(t-vs[j])/(vs[j+1]-vs[j]+1e-9)
        sn=math.sin(pi*u)**0.75
        dep=deps[j]*(1-u)+deps[j+1]*u
        off=(amps[j]*sn-dep*(1-sn))*(0.35+0.65*g)*(1 if f>0 else 0)
        x,yy=base_pt(y,t,hx,yf,yb,n); cy=(yf+yb)/2
        nx,ny=x,(yy-cy); L=math.hypot(nx,ny)+1e-9
        pts.append((x+off*nx/L,yy+off*ny/L)); zoff.append(1-sn)
    seam_t=vs[4]
    return pts,zoff,ts,seam_t
NF=64; NB=40
def build():
    T=Part('Gear_Torso','Torso')
    Rf={1:[],-1:[]}; Rb={1:[],-1:[]}
    ZO={1:[],-1:[]}
    for y in ROWS:
        z=Zmap(y)
        for sx in (1,-1):
            pts,zo,ts,seam_t=half_outline(y,sx)
            ks=int(np.argmin(np.abs(ts-seam_t)))
            fr=resample(pts[:ks+3],NF); bk=resample(pts[ks-2:],NB)
            zf=np.interp(np.linspace(0,1,NF),np.linspace(0,1,ks+3),zo[:ks+3]); zb=np.interp(np.linspace(0,1,NB),np.linspace(0,1,len(zo)-ks+2),zo[ks-2:])
            Rf[sx].append([(sx*p[0],p[1],z) for p in fr]); Rb[sx].append([(sx*p[0]*0.995,p[1]+0.008,z) for p in bk])
            ZO[sx].append((zf,zb))
    # hem heights per point (only bottom row moves); vent opening at back centre
    def hem_adjust(R,last,zo=None):
        out=[]
        for kk,p in enumerate(R[last]):
            ax=abs(p[0])
            if p[1]>-0.5:   # front panel
                yy=866-8*np.clip((ax-1.75)/0.25,0,1)
            else:           # back panel
                yy=862-6*np.clip((ax-1.7)/0.3,0,1)
            yy-=16*np.exp(-((p[1]+0.56)/0.09)**2)        # side-seam notch
            if zo is not None: yy+=14*zo[kk]               # fold valleys hang lower: scalloped hem
            xs=p[0]-np.sign(p[0])*0.10*np.clip((ax-1.6)/0.4,0,1)
            out.append((xs,p[1],Zmap(yy)))
        R[last]=out
    last=len(ROWS)-1
    for sx in (1,-1):
        hem_adjust(Rf[sx],last,ZO[sx][last][0]); hem_adjust(Rb[sx],last,ZO[sx][last][1])
        # vent: split from y=790 down, centre points pulled apart
        for i,y in enumerate(ROWS):
            if y>=790:
                v=0.04*(y-790)/(852-790)
                p=Rb[sx][i][-1]; Rb[sx][i][-1]=(p[0]+sx*v,p[1],p[2])
                p=Rb[sx][i][-2]; Rb[sx][i][-2]=(p[0]+sx*v*0.5,p[1],p[2])
    def inner(R):
        out=[]
        for i,ring in enumerate(R):
            q=[]
            for k,p in enumerate(ring):
                a=V(ring[max(k-1,0)]); b=V(ring[min(k+1,len(ring)-1)]); t=(b-a); t.z=0; t.normalize()
                n=V((t.y,-t.x,0))
                c=V((0,-0.05,p[2]))
                if n.dot(V(p)-c)<0: n=-n
                q.append(tuple(V(p)-n*TH))
            out.append(q)
        return out
    def roll(ring,inn,r=0.035,steps=5):
        """rolled-out hem lip: outer surface curls outward and up, showing the lining"""
        rings=[]
        for s_ in range(1,steps+1):
            a=math.radians(125*s_/steps); rr=[]
            for p,q in zip(ring,inn):
                n=V(p)-V(q); n.z=0; n.normalize(); c=V(p)+n*r
                rr.append(tuple(c-n*r*math.cos(a)-V((0,0,1))*r*math.sin(a)))
            rings.append(rr)
        return rings
    def shell(R,closed_end_flags):
        Ri=inner(R)
        for i in range(len(R)-1):
            for k in range(len(R[0])-1):
                T.face([R[i][k],R[i][k+1],R[i+1][k+1],R[i+1][k]],M['Marble'])
                T.face([Ri[i][k+1],Ri[i][k],Ri[i+1][k],Ri[i+1][k+1]],M['Lining'])
        for e,mt in closed_end_flags:
            for i in range(len(R)-1):
                T.face([R[i][e],Ri[i][e],Ri[i+1][e],R[i+1][e]],mt)
        rl=roll(R[-1],Ri[-1])
        prev=R[-1]
        for j,rr in enumerate(rl):
            mt=M['Marble'] if j<3 else M['Lining']
            for k in range(len(rr)-1): T.face([prev[k],prev[k+1],rr[k+1],rr[k]],mt)
            prev=rr
        for k in range(len(prev)-1): T.face([prev[k],prev[k+1],Ri[-1][k+1],Ri[-1][k]],M['Lining'])
        # top cap
        for k in range(len(R[0])-1): T.face([R[0][k+1],R[0][k],Ri[0][k],Ri[0][k+1]],M['Marble'])
        return Ri
    for sx in (1,-1):
        shell(Rf[sx],[(0,M['Marble']),(NF-1,M['Marble'])])
        shell(Rb[sx],[(0,M['Marble']),(NB-1,M['Marble'])])
    # shoulder band: from coat top to neck (collar sits here in part 3)
    for sx in (1,-1):
        for R,n_ in ((Rf[sx],NF),(Rb[sx],NB)):
            top=R[0]
            for k in range(n_-1):
                a,b=top[k],top[k+1]
                na=(a[0]*0.58,a[1]*0.85,a[2]+0.035); nb=(b[0]*0.58,b[1]*0.85,b[2]+0.035)
                T.face([b,a,na,nb],M['Marble'])
    return T
ob=build().build()
for p in ob.data.polygons: p.use_smooth=True
try: ob.data.set_sharp_from_angle(angle=math.radians(50))
except Exception as e: print('sharp',e)
print('coat tris',sum(len(p.vertices)-2 for p in ob.data.polygons))
bpy.ops.wm.save_as_mainfile(filepath=OUT)
