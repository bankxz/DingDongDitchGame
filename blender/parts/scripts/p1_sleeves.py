import sys; sys.path.insert(0,'/tmp/w/parts')
import bpy, pickle
from common import *
SRC,OUT=sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=SRC)
M=mats()
E=pickle.load(open('/tmp/w/parts/sleeve_lines.pkl','rb'))['edges']
ZT=Zmap(372)+0.045; ZC0=Zmap(570); ZC1=Zmap(588); ZP=Zmap(600)
HX0,HY0=0.535,0.540; CY0=-0.03; R=0.065; TH=0.035
F0=E['F'][377]; S0=E['S'][377]
def prof(z):
    """measured curved profile: half sizes + centre offset at height z (sheet rows; below 566 hold)"""
    py=int(round(min(max(372+(4-z)*130,377),566)))
    fi,fo=E['F'][py]; si,so=E['S'][py]
    wf=(fi-fo)/(F0[0]-F0[1]); ws=(so-si)/(S0[1]-S0[0])
    cshift=((fi+fo)-(F0[0]+F0[1]))/2*(2*HX0/(F0[0]-F0[1]))       # +ve = towards torso
    cys=((si+so)-(S0[0]+S0[1]))/2*(2*HY0/(S0[1]-S0[0]))          # +ve = towards back
    return HX0*wf,HY0*ws,cshift,-cys
BF,BS=0.045,0.025   # face bulge: front/back, sides (soft fabric, not flat planes)
SEG=8; NF=10
def ring_pts(sx,z,extra=0.0,inset=0.0,seg=SEG):
    hx,hy,cs,cyo=prof(z); hx+=extra-inset; hy+=extra-inset; r=max(0.02,R-inset)
    cx=sx*(1.51-cs); cy=CY0+cyo
    fx=hx-r; fy=hy-r
    def arc(ccx,ccy,a0,a1):
        return [(ccx+r*math.cos(math.radians(a0+(a1-a0)*k/seg)),ccy+r*math.sin(math.radians(a0+(a1-a0)*k/seg))) for k in range(seg+1)]
    def flat(p0,p1,axis,sign,b):
        out=[]
        for k in range(1,NF+1):
            t=k/(NF+1); x=p0[0]+(p1[0]-p0[0])*t; y=p0[1]+(p1[1]-p0[1])*t
            w=1-(2*t-1)**2
            if axis=='y': y+=sign*b*w
            else: x+=sign*b*w
            out.append((x,y))
        return out
    so=sx
    xo=cx+so*fx; xi=cx-so*fx; yf=cy+fy; yb=cy-fy
    if sx>0:
        A0=arc(xo,yf,90,0); A1=arc(xo,yb,0,-90); A2=arc(xi,yb,-90,-180); A3=arc(xi,yf,180,90)
    else:
        A0=arc(xo,yf,90,180); A1=arc(xo,yb,180,270); A2=arc(xi,yb,270,360); A3=arc(xi,yf,0,90)
    pts=A0+flat(A0[-1],A1[0],'x',so,BS)+A1+flat(A1[-1],A2[0],'y',-1,BF)+A2+flat(A2[-1],A3[0],'x',-so,BS*0.6)+A3+flat(A3[-1],A0[0],'y',1,BF)
    return [(p[0],p[1],z) for p in pts], (cx,cy,hx,hy,r)
def surf(sx,face,u,z,lift=0.0):
    hx,hy,cs,cyo=prof(z); cx=sx*(1.51-cs); cy=CY0+cyo
    pts,_=ring_pts(sx,z,seg=12); P=np.array([p[:2] for p in pts]); n=len(P); blk=13+NF
    mids=[i*blk+6 for i in range(4)]        # arc midpoints: front-outer, back-outer, back-inner, front-inner
    seq=np.vstack([P,P]); L=np.r_[0,np.cumsum(np.linalg.norm(np.diff(seq,axis=0),axis=1))]
    spans={0:(mids[3],mids[0]+n),1:(mids[0],mids[1]),2:(mids[1],mids[2]),3:(mids[2],mids[3])}
    i0,i1=spans[face]; a=L[i0]; b=L[i1]
    s=a+(b-a)*u
    while s<0: s+=L[n]
    while s>=2*L[n]-1e-9: s-=L[n]
    k=np.searchsorted(L,s)-1; k=min(max(k,0),len(seq)-2); f=(s-L[k])/(L[k+1]-L[k]+1e-12)
    p=seq[k]+(seq[k+1]-seq[k])*f; t=seq[k+1]-seq[k]; t=t/np.linalg.norm(t)
    nn=np.array([t[1],-t[0]])
    if np.dot(nn,p-np.array([cx,cy]))<0: nn=-nn
    N=V((nn[0],nn[1],0.0))
    return V((p[0],p[1],z))+N*lift, N
def fpx(py,px,view):
    i,o=E[view][int(min(max(round(py),377),566))]
    return (px-i)/(o-i)
def path(sx,segs,step=0.02):
    """segs: list of (face,u,z) control points; densify along straight lines in (face-param,z) space -> 3D pts,normals"""
    # convert to a continuous perimeter coordinate T=face+u
    out=[];nrm=[]
    ctrl=[(f+u,z) for f,u,z in segs]
    for (t0,z0),(t1,z1) in zip(ctrl[:-1],ctrl[1:]):
        nseg=max(2,int(max(abs(t1-t0)*1.1,abs(z1-z0))/step))
        for k in range(nseg+(1 if (t1,z1)==ctrl[-1] else 0)):
            t=t0+(t1-t0)*k/nseg; z=z0+(z1-z0)*k/nseg
            face=int(math.floor(t))%4; u=t-math.floor(t)
            p,n=surf(sx,face,u,z); out.append(tuple(p)); nrm.append(n)
    return out,nrm
def sleeve(bone,sx):
    P=Part('Gear_'+bone.replace(' ',''),bone); G=Part('Glow_'+bone.replace(' ',''),bone)
    zs=[ZP,ZC1,ZC0]+list(np.linspace(Zmap(566),ZT-R,14))
    rings=[ring_pts(sx,z)[0] for z in zs]
    for k in range(1,5):
        a=math.radians(90*k/5); rings.append(ring_pts(sx,ZT-R+R*math.sin(a),inset=R*(1-math.cos(a)))[0])
    rings.append(ring_pts(sx,ZT,inset=R*0.999)[0])
    P.loft(rings,M['Marble'],cap1=M['Marble'])
    inner=[ring_pts(sx,z,inset=TH)[0] for z in (ZP,Zmap(566),3.3,4.008)]
    P.loft(inner,M['Lining'],cap1=M['Lining'])
    for j in range(len(rings[0])):
        k=(j+1)%len(rings[0]); P.face([rings[0][k],rings[0][j],inner[0][j],inner[0][k]],M['Lining'])
    zm=(ZC0+ZC1)/2
    P.loft([ring_pts(sx,ZC1,extra=0.012)[0],ring_pts(sx,ZC1+0.014,extra=0.028)[0],ring_pts(sx,zm,extra=0.036)[0],ring_pts(sx,ZC0-0.014,extra=0.028)[0],ring_pts(sx,ZC0,extra=0.012)[0]],M['Gold'],cap0=M['Gold'],cap1=M['Gold'])
    G.loft([ring_pts(sx,ZP,extra=0.016)[0],ring_pts(sx,ZP+0.012,extra=0.032)[0],ring_pts(sx,ZC1-0.004,extra=0.032)[0],ring_pts(sx,ZC1+0.004,extra=0.02)[0]],M['Glow'],cap0=M['Glow'],cap1=M['Glow'])
    Z=lambda py: Zmap(py)
    HW=0.036; HH=0.02
    for face,mirror in ((0,False),(2,True)):
        # front pattern measured on the right sleeve front (px); back face uses the same pattern measured from the outer edge
        def U(px,py):
            u=fpx(py,px,'F')               # 0 inner .. 1 outer on the front
            return (1-u) if mirror else u  # back face runs outer->inner
        def pt(px,py): return (face,U(px,py),Z(py))
        bar=[(face,U(57,377),ZT-R+0.004),pt(58,430),pt(60,487)]
        p,n=path(sx,bar); strip(P,p,n,HW*1.05,HH,M['Gold'])
        # tail: from bar foot to the outer edge, then wraps round the corner onto the side face (joins the double band)
        if not mirror: tail=[pt(60,489),(0,0.97,Z(462)),(1,0.10,Z(463))]
        else: tail=[pt(60,489),(2,0.03,Z(462)),(1,0.90,Z(463))]
        p,n=path(sx,tail); strip(P,p,n,HW*1.05,HH,M['Gold'])
        # line A: up to the top edge then over the shoulder fillet
        A=[pt(62,428),pt(108,407),(face,U(133,377),ZT-R+0.004)]
        p,n=path(sx,A); strip(P,p,n,HW*0.85,HH,M['Gold'])
        # line B: to the inner edge, then wraps onto the inner face
        if not mirror: B=[pt(62,452),pt(121,425),(0,0.0,Z(390)),(-1,0.85,Z(386))]
        else: B=[pt(62,452),pt(121,425),(2,1.0,Z(390)),(3,0.15,Z(386))]
        p,n=path(sx,B); strip(P,p,n,HW*0.85,HH,M['Gold'])
    # --- trim over the top of the arm: front end -> up the shoulder fillet -> across the top -> down to the back end
    def over_top(u_front):
        pf,nf=surf(sx,0,u_front,ZT-R); pb,nb=surf(sx,2,1-u_front,ZT-R)
        up=V((0,0,1)); pts=[];nr=[]
        for k in range(0,7):
            a=math.radians(90*k/6); pts.append(tuple(pf-nf*R*(1-math.cos(a))+up*R*math.sin(a))); nr.append((nf*math.cos(a)+up*math.sin(a)).normalized())
        a0=V(pts[-1]); b0=pb-nb*R+up*R
        for k in range(1,8):
            t=k/8; pts.append(tuple(a0.lerp(b0,t))); nr.append(up)
        for k in range(6,-1,-1):
            a=math.radians(90*k/6); pts.append(tuple(pb-nb*R*(1-math.cos(a))+up*R*math.sin(a))); nr.append((nb*math.cos(a)+up*math.sin(a)).normalized())
        return pts,nr
    for px_,hw in ((57,HW*1.05),(133,HW*0.85)):
        pts,nr=over_top(fpx(377,px_,'F')); strip(P,pts,nr,hw,HH,M['Gold'])
    # line B: join front and back ends along the inner face
    p,n=path(sx,[(-1,0.85,Z(386)),(-1,0.15,Z(386))]); strip(P,p,n,HW*0.85,HH,M['Gold'])
    # side face: double band (front corner -> back corner) and vertical strip near the back edge
    for py in (458.5,467.5):
        p,n=path(sx,[(1,0.06,Z(py)),(1,0.94,Z(py))]); strip(P,p,n,0.028,0.018,M['Gold'])
    p,n=path(sx,[(1,(782-668)/119,Z(402)),(1,(782-668)/119,Z(457))]); strip(P,p,n,0.03,0.02,M['Gold'])
    return P,G
objs=[]
for bone,sx in (('Right Arm',1),('Left Arm',-1)):
    P,G=sleeve(bone,sx); objs+=[P.build(),G.build()]
for o in objs: print(o.name,'tris',sum(len(p.vertices)-2 for p in o.data.polygons))
bpy.ops.wm.save_as_mainfile(filepath=OUT)
