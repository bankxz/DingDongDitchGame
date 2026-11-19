import random, math
from mathutils import Vector as V
random.seed(11)
HM=mat('HairMid',(0.85,0.83,0.93),0,0.55); M['HairMid']=HM
HP=Part('Gear_Head','Head'); P['Head']=HP; GH=Part('Glow_Head','Head'); G['Head']=GH
HC=V((0,-0.03,4.98)); A_,B_,C_=0.73,0.75,0.60
def surf(d):
    d=V(d).normalized()
    if d.z>=0: return HC+V((A_*d.x,B_*d.y,C_*d.z))
    h=V((d.x,d.y,0)); h=h.normalized() if h.length>1e-6 else V((0,1,0))
    return V((A_*h.x,B_*h.y,0))+HC+V((0,0,d.z*0.9))
def outw(p): 
    q=p-V((0,-0.05,min(max(p.z,4.4),5.0))); return q.normalized()
def dirfrom(phi,z):
    # direction pointing at azimuth phi (0=front +y, +=towards +x) reaching height z on the surface
    if z>=HC.z:
        s=min(1,(z-HC.z)/C_); el=math.asin(s)
    else: el=-(HC.z-z)/0.9*1.0; el=max(el,-1.4)
    if z>=HC.z: return V((math.sin(phi)*math.cos(el),math.cos(phi)*math.cos(el),math.sin(el)))
    return V((math.sin(phi),math.cos(phi),(z-HC.z)/0.9))
def zmin(phi):
    a=abs(math.degrees(math.atan2(math.sin(phi),math.cos(phi))))
    return float(np.interp(a,[0,40,62,80,110,150,180],[4.97,4.98,4.92,4.72,4.55,4.42,4.40]))
# ---- scalp base (closed shell)
NA=40; NE=14
outer=[];inner=[]
for j in range(NA):
    phi=2*pi*j/NA; zb=zmin(phi); ring=[]
    zs=list(np.linspace(zb,HC.z,6))[:-1]+[HC.z+C_*math.sin(math.radians(a)) for a in np.linspace(0,88,NE-5)]
    outer.append([surf(dirfrom(phi,z)) for z in zs])
NZ=len(outer[0])
top=HC+V((0,0,C_))
rings=[[tuple(outer[j][i]) for j in range(NA)] for i in range(NZ)]
rin=[[tuple(V(p)-outw(V(p))*0.05) for p in r] for r in rings]
for i in range(NZ-1):
    for j in range(NA):
        k=(j+1)%NA
        HP.face([rings[i][j],rings[i][k],rings[i+1][k],rings[i+1][j]],M['HairShade'])
        HP.face([rin[i][k],rin[i][j],rin[i+1][j],rin[i+1][k]],M['HairShade'])
for j in range(NA):
    k=(j+1)%NA
    HP.face([rings[-1][j],rings[-1][k],tuple(top)],M['HairShade'])
    HP.face([rin[-1][k],rin[-1][j],tuple(top-V((0,0,0.05)))],M['HairShade'])
    HP.face([rings[0][k],rings[0][j],rin[0][j],rin[0][k]],M['HairShade'])
TIE=V((0,-0.70,5.43)); AX=V((0,-0.55,0.84)).normalized()
def sweep_to(d0,dT,n=7,lift=0.03,bulge=0.05):
    pts=[]
    for i in range(n):
        u=i/(n-1); d=(d0*(1-u)+dT*u).normalized()
        p=surf(d); pts.append(p+outw(p)*(lift+bulge*math.sin(pi*u)))
    return pts
dT=(TIE-HC).normalized()
# ---- A: swept-back crown strands
for k in range(34):
    phi=-pi+2*pi*(k+0.5)/34+random.uniform(-0.04,0.04)
    a=abs(math.degrees(math.atan2(math.sin(phi),math.cos(phi))))
    if a>165: continue
    z0=zmin(phi)+0.02
    pts=sweep_to(dirfrom(phi,z0),dT,7,0.025,0.07+0.05*random.random())
    pts[-1]=TIE+AX*0.02; 
    ribbon(HP,[tuple(p) for p in pts],[0.13,0.17,0.15,0.12,0.08],0.05,M['Hair'],outward=outw,n=6)
# ---- B: short centre strands (V part) + face-framing locks at the face edges
for sx in(1,-1):
    for (tx,tz,w) in [(0.10,4.95,0.09),(0.24,4.93,0.11),(0.36,4.96,0.11)]:
        st=V((sx*0.04,0.40,5.48)); mid=V((sx*(0.05+tx*0.6),0.76,5.16)); tip=V((sx*tx,0.75,tz))
        ribbon(HP,[tuple(st),tuple(mid),tuple(tip)],[0.09,w*1.2,0.006],0.05,M['Hair'],outward=lambda p:V((0,1,0.2)).normalized(),n=6)
    for (pts,w) in [([(0.40,0.56,5.18),(0.55,0.70,4.86),(0.60,0.71,4.50),(0.62,0.69,4.18)],0.10),
                    ([(0.50,0.48,5.12),(0.64,0.62,4.82),(0.69,0.62,4.42),(0.71,0.58,4.05)],0.09),
                    ([(0.30,0.60,5.22),(0.48,0.74,4.95),(0.53,0.74,4.70),(0.55,0.72,4.55)],0.08)]:
        pp=[(sx*x,y,z) for x,y,z in pts]
        ribbon(HP,pp,[0.08,w*1.2,w,0.006],0.045,M['Hair'],outward=lambda p:V((0,1,0)),n=6)
# ---- C: long locks over the chest
for sx in(1,-1):
    for (bx,tx,tz,w) in [(0.56,0.45,3.50,0.07),(0.62,0.56,3.42,0.08),(0.66,0.68,3.60,0.065)]:
        pth=[V((sx*bx,0.40,5.02)),V((sx*(bx+0.05),0.64,4.70)),V((sx*(bx+0.06),0.71,4.25)),V((sx*(tx+0.04),0.76,3.90)),V((sx*tx,0.78,tz))]
        ribbon(HP,[tuple(p) for p in pth],[0.06,w*1.3,w*1.2,w,0.005],0.04,M['Hair'],outward=lambda p:V((0,1,0)),n=5)
# ---- D: swept side wings: long tapered strands radiating from the crown sides
for sx in(1,-1):
    for k,(phi0,tx,ty,tz,w) in enumerate([(0.50,0.98,0.30,4.78,0.20),(0.65,1.04,0.14,4.62,0.22),(0.80,1.02,-0.04,4.96,0.20),(0.95,0.98,-0.20,4.45,0.20),(1.15,0.94,-0.36,4.78,0.19),(1.35,0.86,-0.56,4.50,0.18),(1.60,0.72,-0.80,4.62,0.18),(1.85,0.52,-0.92,4.78,0.17),(0.72,0.90,0.30,4.42,0.15),(1.05,0.88,-0.15,5.12,0.15)]):
        b=surf(dirfrom(sx*phi0,5.30)); tip=V((sx*tx,ty,tz))
        mid=(b+tip)/2; mid=mid+outw(mid)*0.13+V((0,0,0.05))
        ribbon(HP,[tuple(b-outw(b)*0.02),tuple(mid),tuple(tip)],[0.12,w,0.004],0.055,M['Hair'] if k%2 else HM,outward=outw,n=7)
# ---- E: back strands hanging to the nape
for k,xx in enumerate([-0.55,-0.35,-0.15,0.15,0.35,0.55]):
    b=surf(V((xx,-0.75,0.3))); 
    pth=[b,surf(V((xx*1.05,-0.9,-0.2)))+V((0,-0.05,0)),V((xx*1.08,-0.74,4.25+0.05*(k%2)))]
    ribbon(HP,[tuple(p) for p in pth],[0.15,0.15,0.006],0.05,M['Hair'],outward=outw,n=6)
# ---- F: gold tie (banded cylinder)
def lathe_axis(c,ax,prof,N,m):
    ax=ax.normalized(); u=ax.cross(V((1,0,0))).normalized(); v=ax.cross(u)
    rings=[[tuple(c+ax*h+(u*math.cos(2*pi*j/N)+v*math.sin(2*pi*j/N))*r) for j in range(N)] for h,r in prof]
    HP.loft(rings,m,cap0=m,cap1=m)
lathe_axis(TIE,AX,[(-0.10,0.13),(-0.09,0.165),(-0.06,0.17),(0.06,0.155),(0.09,0.15),(0.10,0.12)],24,M['Gold'])
# ---- G: ponytail
C1=TIE+AX*0.10
core=[C1,V((0.04,-1.02,5.72)),V((0.10,-1.32,5.38)),V((0.18,-1.38,4.70)),V((0.22,-1.32,4.0)),V((0.20,-1.18,3.4)),V((0.16,-1.10,2.9))]
ribbon(HP,[tuple(p) for p in core],[0.12,0.22,0.34,0.40,0.38,0.28,0.04],0.30,M['HairMid'] if 'HairMid' in M else M['Hair'],outward=lambda p:V((0,-1,0.3)).normalized(),n=6,sides=8)
for k in range(84):
    sp=random.uniform(-1,1); u=random.random()
    wv=random.uniform(0,2*pi); amp=random.uniform(0.05,0.12); L=random.uniform(0,1)
    ang=random.uniform(0,2*pi); r0=V((math.cos(ang),math.sin(ang)*0.6,0))*0.08
    pts=[C1+r0,
         V((0.04+sp*0.10,-0.97-0.18*u,5.72+random.uniform(-0.04,0.04))),
         V((0.10+sp*0.28,-1.10-0.48*u,5.38)),
         V((0.18+sp*0.46+amp*math.sin(wv),-0.93-0.95*u,4.70)),
         V((0.22+sp*0.50+amp*math.sin(wv+1.7),-0.90-0.85*u,4.00)),
         V((0.20+sp*0.46+amp*math.sin(wv+3.2),-0.88-0.60*u,3.40+L*0.3)),
         V((0.16+sp*0.40+amp*1.5*math.sin(wv+4.5),-0.88-0.45*u,2.70+L*0.5))]
    w=random.uniform(0.13,0.21)
    ribbon(HP,[tuple(p) for p in pts],[0.05,w*0.9,w*1.1,w,w*0.85,w*0.55,0.004],0.06,M['Hair'] if k%3 else HM,outward=lambda p:V((0,-1,0.25)).normalized(),n=5)
# ---- scar glow (on the head cylinder surface)
def onhead(x,z,o): return (x,math.sqrt(max(0.01,0.36-x*x))+o,z)
x0,z0=XF(316),Zmap(258); x1,z1=XF(320),Zmap(347); w=0.024
pa=[onhead(x0+w,z0,-0.008),onhead(x0-w,z0,-0.008),onhead(x1-w*0.3,z1,-0.008),onhead(x1+w*0.3,z1,-0.008)]
pb=[(p[0],p[1]+0.024,p[2]) for p in pa]
GH.face(pa[::-1],M['Glow']); GH.face(pb,M['Glow'])
for i in range(4): GH.face([pa[i],pa[(i+1)%4],pb[(i+1)%4],pb[i]],M['Glow'])
