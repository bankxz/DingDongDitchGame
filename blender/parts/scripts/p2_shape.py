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
ROWS=[372,400,450,500,560,600,612,620,630,645,660,680,700,725,750,775,800,820,840,852]
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
def front_poly(y,sx):
    """front panel cross-section (+x side when sx=1): opening -> front crease -> side folds -> seam"""
    hx=I(HX,y); yf=I(YF,y); yb=I(YB,y); f=F(y); g=G(y)
    xo=XF(I(OPL,y)) if sx>0 else -XF(I(OPR,y))
    xo=abs(xo)
    df=0.15*f; ys=-0.56 if f>0 else yb+0.05     # seam depth
    pts=[(xo,yf),((xo+hx-df)/2,yf+0.025*f),(hx-df,yf),
         (hx-0.015*f,0.33),(hx,0.08),(hx-0.05*g-0.01*f,-0.07),(hx,-0.21),(hx-0.02*f,-0.40),(hx-0.05*f,ys)]
    if f==0:   # torso-tight: rounded rectangle quarter (front-right corner -> side -> back-right corner)
        pts=[(xo,yf),(hx-0.06,yf),(hx,yf-0.06),(hx,yb+0.06),(hx-0.06,yb),(0.0,yb)]
        return pts,False
    return pts,True
def back_poly(y):
    hx=I(HX,y); yb=I(YB,y); f=F(y); g=G(y)
    return [(hx-0.07*f,-0.53),(hx-0.10*f,(yb-0.53)/2),(hx-0.30*f,yb),(0.5*(hx-0.30*f),yb-0.02*f),(0.0,yb)]
NF=40; NB=24
def build():
    T=Part('Gear_Torso','Torso')
    Rf={1:[],-1:[]}; Rb={1:[],-1:[]}
    for y in ROWS:
        z=Zmap(y)
        for sx in (1,-1):
            P,fl=front_poly(y,sx)
            if not fl:
                Q=resample(chaikin(P,2),NF+NB-1); fr=Q[:NF]; bk=Q[NF-1:]
            else:
                fr=resample(chaikin(P,2),NF); bk=resample(chaikin(back_poly(y),2),NB)
            Rf[sx].append([(sx*p[0],p[1],z) for p in fr]); Rb[sx].append([(sx*p[0],p[1],z) for p in bk])
    # hem heights per point (only bottom row moves); vent opening at back centre
    def hem_adjust(R,last):
        out=[]
        for p in R[last]:
            ax=abs(p[0])
            if p[1]>-0.5:   # front panel
                yy=866-8*np.clip((ax-1.75)/0.25,0,1)
            else:           # back panel
                yy=862-6*np.clip((ax-1.7)/0.3,0,1)
            yy-=16*np.exp(-((p[1]+0.56)/0.09)**2)        # side-seam notch
            xs=p[0]-np.sign(p[0])*0.10*np.clip((ax-1.6)/0.4,0,1)
            out.append((xs,p[1],Zmap(yy)))
        R[last]=out
    last=len(ROWS)-1
    for sx in (1,-1):
        hem_adjust(Rf[sx],last); hem_adjust(Rb[sx],last)
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
print('coat tris',sum(len(p.vertices)-2 for p in ob.data.polygons))
bpy.ops.wm.save_as_mainfile(filepath=OUT)
