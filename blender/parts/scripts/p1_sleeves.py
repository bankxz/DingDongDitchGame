import sys; sys.path.insert(0,'/tmp/w/parts')
import bpy
from common import *
SRC,OUT=sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=SRC)
M=mats()
# --- measured from the sheet (front view right sleeve, px): outer edge 39 (->33 at cuff), inner edge 148 (->150), top 372, cuff 570-588 gold, 588-600 purple
ZT=Zmap(372); ZC0=Zmap(570); ZC1=Zmap(588); ZP=Zmap(600)
HX_T,HX_B=0.535,0.565   # half width top/bottom (bell)
HY_T,HY_B=0.540,0.560
CY=-0.03; R=0.06; TH=0.035
def sleeve(bone,sx):
    P=Part('Gear_'+bone.replace(' ',''),bone); G=Part('Glow_'+bone.replace(' ',''),bone)
    cx=sx*1.51
    def ring(z,inset=0.0,extra=0.0):
        f=(ZT-z)/(ZT-ZP); hx=HX_T+(HX_B-HX_T)*f+extra-inset; hy=HY_T+(HY_B-HY_T)*f+extra-inset
        return rrect(cx+sx*0.006*f,CY,hx,hy,max(0.02,R-inset),z)
    # outer shell with rounded shoulder (fillet r=0.06)
    zs=[ZP,ZC1,ZC0,3.0,3.5,ZT-R]
    rings=[ring(z) for z in zs]
    for k in range(1,4):
        a=math.radians(90*k/4); rings.append(ring(ZT-R+R*math.sin(a),inset=R*(1-math.cos(a))))
    rings.append(ring(ZT,inset=R*0.999))
    P.loft(rings,M['Marble'],cap1=M['Marble'])
    inner=[ring(z,inset=TH) for z in (ZP,3.92)]
    P.loft(inner,M['Lining'],cap1=M['Lining'])
    o0=rings[0]; i0=inner[0]
    for j in range(len(o0)):
        k=(j+1)%len(o0); P.face([o0[k],o0[j],i0[j],i0[k]],M['Lining'])
    # cuff: gold band (chamfered) + diamond facets, purple glow band below
    zm=(ZC0+ZC1)/2
    cb=[ring(ZC1,extra=0.012),ring(ZC1+0.014,extra=0.028),ring(zm,extra=0.036),ring(ZC0-0.014,extra=0.028),ring(ZC0,extra=0.012)]
    P.loft(cb,M['Gold'],cap0=M['Gold'],cap1=M['Gold'])
    G.loft([ring(ZP,extra=0.016),ring(ZP+0.012,extra=0.032),ring(ZC1-0.004,extra=0.032),ring(ZC1+0.004,extra=0.02)],M['Glow'],cap0=M['Glow'],cap1=M['Glow'])
    # --- gold lines on front & back faces: polylines in sheet px for the RIGHT sleeve front (outer edge x39, inner 148)
    LINES=[[(57,377),(58,488)],[(36,455),(59,489)],[(61,426),(107,408),(134,377)],[(61,451),(120,426),(147,390)]]
    def face_pt(px,py,face_sign):
        z=Zmap(py); u=(148-px)/(148-39)     # 0 inner .. 1 outer
        f=(ZT-z)/(ZT-ZP); hx=HX_T+(HX_B-HX_T)*f; hy=HY_T+(HY_B-HY_T)*f
        x=cx+sx*(-hx+2*hx*u); y=CY+face_sign*hy
        return (x,y,z)
    for fs in (1,-1):
        n=V((0,fs,0))
        for L in LINES:
            strip(P,[face_pt(px,py,fs) for px,py in L],n,0.036,0.02,M['Gold'])
    # outer side face: double band at y 455-470 + vertical strip near back edge (side view, left arm: front x668 back x787)
    def side_pt(px,py):
        z=Zmap(py); u=(px-668)/(787-668)     # 0 front .. 1 back
        f=(ZT-z)/(ZT-ZP); hx=HX_T+(HX_B-HX_T)*f; hy=HY_T+(HY_B-HY_T)*f
        return (cx+sx*hx,CY+hy-2*hy*u,z)
    n=V((sx,0,0))
    for py in (458.5,467.5):
        strip(P,[side_pt(670,py),side_pt(785,py)],n,0.028,0.018,M['Gold'])
    strip(P,[side_pt(782,402),side_pt(782,455)],n,0.03,0.02,M['Gold'])
    return P,G
objs=[]
for bone,sx in (('Right Arm',1),('Left Arm',-1)):
    P,G=sleeve(bone,sx); objs+=[P.build(),G.build()]
for o in objs: print(o.name,'tris',sum(len(p.vertices)-2 for p in o.data.polygons))
bpy.ops.wm.save_as_mainfile(filepath=OUT)
