import sys; sys.path.insert(0,'/tmp/w/parts')
import bpy, random
from common import *
SRC,OUT=sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=SRC)
M=mats(); HR=mat('HairL',(0.96,0.94,0.99),0,0.45); HS=mat('HairShade',(0.87,0.85,0.95),0,0.5); HD=mat('HairDeep',(0.78,0.76,0.89),0,0.55)
for n in ('Gear_Hair',):
    o=bpy.data.objects.get(n)
    if o: bpy.data.objects.remove(o)
H=Part('Gear_Hair','Head'); random.seed(3)
HC=V((0,0.0,4.5))
def spline(P,n=10):
    P=[V(p) for p in P]; P=[P[0]*2-P[1]]+P+[P[-1]*2-P[-2]]; out=[]
    for i in range(1,len(P)-2):
        for k in range(n):
            t=k/n; p0,p1,p2,p3=P[i-1],P[i],P[i+1],P[i+2]
            out.append(0.5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t*t+(-p0+3*p1-3*p2+p3)*t**3))
    out.append(P[-2]); return out
def outw_head(p):
    c=V((0,-0.02,min(max(p.z,4.3),5.2))); d=p-c
    return d.normalized() if d.length>1e-6 else V((0,0,1))
def clump(ctrl,w0,w1,th,m,up=outw_head,n=10,sides=8,wtip=0.0,bulge=None,clampback=False):
    P=spline(ctrl,n); L=len(P); rings=[]
    if clampback: P=[V((p.x,min(p.y,-0.66),p.z)) if p.z<4.25 else p for p in P]
    for i,p in enumerate(P):
        u=i/(L-1)
        t=(P[min(i+1,L-1)]-P[max(i-1,0)]).normalized()
        nn=up(p); nn=(nn-t*nn.dot(t))
        if nn.length<1e-6: nn=V((0,0,1))-t*t.z
        nn.normalize(); b=t.cross(nn).normalized()
        # width profile: root w0, swell, then taper to a point
        w=(w0+(w1-w0)*min(1,u/0.3))*(1-u)**0.9*(1.0 if u<0.3 else 1.0)+wtip
        w=max(w,0.004); tt=th*max(0.25,(1-u))
        ring=[]
        for j in range(sides):
            a=2*pi*j/sides; ca,sa=math.cos(a),math.sin(a)
            x=w*math.copysign(abs(ca)**0.7,ca); y=tt*sa*(1.0 if sa>0 else 0.45)
            ring.append(tuple(p+b*x+nn*y))
        rings.append(ring)
    H.loft(rings,m,cap0=m,cap1=m)
# ---------------- scalp shell (closes gaps between clumps)
def R(z): return 0.665 if z<5.1 else 0.665*math.sqrt(max(0.0,1-((z-5.1)/0.55)**2))
def hairline(th):   # z of the shell bottom by angle (0 = front)
    a=abs((math.degrees(th)+180)%360-180)
    return float(np.interp(a,[0,30,55,90,130,180],[5.05,5.0,4.85,4.62,4.38,4.28]))
def S(th,z,lift=0.0):
    r=R(z)+lift; return V((r*math.sin(th),r*math.cos(th)-0.02,z))
NA=48; rings=[]
for k in range(13):
    f=k/12; ring=[]
    for j in range(NA):
        th=2*pi*j/NA; z0=hairline(th); z=z0+(5.64-z0)*f
        ring.append(tuple(S(th,z)))
    rings.append(ring)
H.loft(rings,HS,cap1=HS)
TIE=V((0,-0.42,5.52)); TAX=V((0,-0.62,0.78)).normalized()
def lock(ctrl,w,th,m,up=outw_head,n=12,tipw=0.0):
    """UGC-style chunky lock: lens section, thick, widest at 30%, sharp tip"""
    P=spline(ctrl,n); L=len(P); rings=[]
    for i,p in enumerate(P):
        u=i/(L-1)
        t=(P[min(i+1,L-1)]-P[max(i-1,0)]).normalized()
        nn=up(p); nn=(nn-t*nn.dot(t))
        if nn.length<1e-6: nn=V((0,0,1))-t*t.z
        nn.normalize(); b=t.cross(nn).normalized()
        prof=(1-u)**0.75/0.7**0.75*0.95 if u>0.3 else (0.70+0.25*u/0.3)
        ww=max(0.006,w*prof+tipw*(1-u)); tt=max(0.004,th*prof)
        ring=[]
        for j in range(12):
            a=2*pi*j/12; ca,sa=math.cos(a),math.sin(a)
            ring.append(tuple(p+b*ww*math.copysign(abs(ca)**0.8,ca)+nn*tt*math.copysign(abs(sa)**1.0,sa)*(1.0 if sa>0 else 0.55)))
        rings.append(ring)
    H.loft(rings,m,cap0=m,cap1=m)
# --- swept-back top: 9 big locks, wide at the hairline, converging into the tie
for k in range(9):
    a=-72+144*k/8; th=math.radians(a); z0=hairline(th)+0.03
    pts=[S(th,z0+0.08,-0.04),S(th,z0+0.02,0.035),S(th,z0+0.12,0.07)]+[S(th*(1-f*0.75),z0+(5.62-z0)*f,0.06+0.06*math.sin(pi*f)) for f in (0.35,0.6,0.85)]+[TIE+TAX*0.04]
    lock(pts,0.21,0.10,(HR,HS)[k%2])
# --- centre-parted bangs: 2 big swept locks per side, V at the centre
for sx in (1,-1):
    for (tth,tz,w) in ((14,4.93,0.24),(40,4.82,0.24)):
        th=math.radians(sx*tth)
        root=S(math.radians(sx*3),5.55,0.10); mid=S(th*0.55,5.3,0.20); tip=S(th,tz,0.06)
        lock([root,mid,mid.lerp(tip,0.55)+outw_head(mid)*0.03,tip],w,0.11,HR)
# --- side wings: 4 chunky spikes per side, sweeping out and down
for sx in (1,-1):
    for k,(rth,rz,tx,ty,tz,w) in enumerate(((62,5.25,1.06,0.12,4.98,0.22),(78,5.12,1.13,-0.02,4.74,0.23),(94,5.02,1.06,-0.18,4.52,0.22),(110,5.08,0.95,-0.36,4.62,0.20))):
        root=S(math.radians(sx*rth),rz,0.03); tip=V((sx*tx,ty,tz)); r0=S(math.radians(sx*(rth-8)),rz+0.15,-0.03)
        mid=root.lerp(tip,0.45)+outw_head(root)*0.10+V((0,0,0.07))
        lock([r0,root,mid,mid.lerp(tip,0.55),tip],w,0.10,(HR,HS)[k%2],up=lambda p: (V((0,1,0))*0.5+outw_head(p)).normalized())
# --- long face-framing locks: 2 chunky locks per side over the chest
for sx in (1,-1):
    for (rth,bx,tz,w) in ((46,0.48,3.62,0.16),(60,0.64,3.55,0.17)):
        root=S(math.radians(sx*rth),4.98,0.04)
        pts=[root,V((sx*(bx+0.08),0.64,4.55)),V((sx*(bx+0.06),0.72,4.15)),V((sx*bx,0.76,3.9)),V((sx*(bx-0.04),0.78,tz))]
        lock(pts,w,0.08,HR,up=lambda p: V((0,1,0.15)).normalized())
# --- back of the head: 5 big locks to the nape
for k in range(5):
    a=180-56+112*k/4; th=math.radians(a); sx=math.sin(th)
    lock([S(th,5.2,0.04),S(th,4.6,0.08),V((sx*0.70,-0.72-0.04*abs(math.cos(th)),4.02+0.06*(k%2)))],0.24,0.10,(HS,HR)[k%2])
# --- gold tie
u=TAX.cross(V((1,0,0))).normalized(); v=TAX.cross(u)
prof=[(-0.11,0.12),(-0.10,0.15),(-0.07,0.155),(-0.04,0.15),(-0.035,0.142),(0.03,0.142),(0.035,0.15),(0.07,0.148),(0.10,0.13),(0.11,0.10)]
H.loft([[tuple(TIE+TAX*h+(u*math.cos(2*pi*j/24)+v*math.sin(2*pi*j/24))*r) for j in range(24)] for h,r in prof],M['Gold'],cap0=M['Gold'],cap1=M['Gold'])
# --- ponytail: solid core + 12 big clumps around it + 4 peeling locks (UGC style)
PATH=[(TIE.y,TIE.z),(-0.62,5.76),(-0.86,5.84),(-0.98,5.52),(-0.98,5.00),(-0.96,4.50),(-0.95,3.90),(-0.92,3.40),(-0.84,3.00),(-0.74,2.62)]
WID=[0.10,0.16,0.28,0.45,0.60,0.66,0.60,0.48,0.30,0.08]
DEP=[0.08,0.16,0.28,0.38,0.43,0.43,0.38,0.28,0.16,0.05]
cp=spline([V((0,y,z)) for y,z in PATH],8)
def ip(arr,i): f=i/(len(cp)-1)*(len(arr)-1); k=min(int(f),len(arr)-2); t=f-k; return arr[k]*(1-t)+arr[k+1]*t
rings=[]
for i,p in enumerate(cp):
    t=(cp[min(i+1,len(cp)-1)]-cp[max(i-1,0)]).normalized(); side=V((1,0,0)); nrm=t.cross(side).normalized()
    w=ip(WID,i)*0.78; d=ip(DEP,i)*0.78
    rr=[p+side*w*math.cos(2*pi*j/20)+nrm*d*math.sin(2*pi*j/20) for j in range(20)]
    rings.append([tuple(V((q.x,min(q.y,-0.68),q.z))) if q.z<4.25 else tuple(q) for q in rr])
H.loft(rings,HS,cap0=HS,cap1=HS)
def pclump(ang,L,wv,mm,flare=0.0,wave=0.05):
    s_,d_=math.cos(ang),math.sin(ang); n_end=max(4,int(round(len(PATH)*L))); pts=[]
    for i in range(n_end):
        y,z=PATH[i]; f=i/(len(PATH)-1)
        x=s_*WID[i]*0.9*(1+flare*f*f)+wave*math.sin(ang*3+i*1.2)*f
        q=V((x,y+d_*DEP[i]*0.9,z))
        if q.z<4.25: q.y=min(q.y,-0.70)
        pts.append(q)
    pts[0]=TIE+TAX*0.06
    up=lambda p: (V((p.x,0,0))*1.5+V((0,-1,0.2))).normalized()
    lock(pts,wv,0.11,mm,up=up,n=8)
for k in range(12):
    pclump(2*pi*k/12+0.13,[1.0,0.85,0.95,0.8][k%4],0.30,(HR,HS,HR)[k%3])
for k,(ang,fl) in enumerate(((0.2,0.45),(pi-0.2,0.45),(0.9,0.3),(pi-0.9,0.3))):
    pclump(ang,0.8,0.20,HR,flare=fl,wave=0.08)
ob=H.build()
for p in ob.data.polygons: p.use_smooth=True
try: ob.data.set_sharp_from_angle(angle=math.radians(80))
except Exception: pass
print('hair tris',sum(len(q.vertices)-2 for q in ob.data.polygons))
bpy.ops.wm.save_as_mainfile(filepath=OUT)
