import sys; sys.path.insert(0,'/tmp/w/parts')
import bpy
from common import *
SRC,OUT=sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=SRC)
M=mats()
I=lambda tab,y: float(np.interp(y,[a for a,b in tab],[b for a,b in tab]))
# ---------------- measured tables (sheet px -> studs) ----------------
# front opening edges (coat fabric edge, px)
OPL=[(372,250),(500,250),(540,240),(566,226),(612,201),(660,193),(708,183),(756,171),(804,158),(852,145),(870,145)]
OPR=[(372,323),(500,326),(540,338),(566,352),(612,373),(660,380),(708,389),(756,399),(804,411),(852,415),(870,415)]
# half width (avg of front & back silhouettes), studs
HXt=[(372,1.055),(520,1.06),(636,1.385),(684,1.49),(732,1.60),(780,1.71),(828,1.86),(852,1.97)]
# side profile: front & back edges (studs, +y front)
YFt=[(372,0.565),(600,0.60),(708,0.678),(756,0.645),(816,0.570),(852,0.545)]
YBt=[(372,-0.565),(560,-0.60),(612,-0.70),(636,-0.76),(708,-0.91),(780,-1.07),(840,-1.22),(852,-1.24)]
NN=[(372,8),(560,8),(640,5),(720,4),(852,3.2)]
SEAM=[(630,1.08),(740,1.30),(850,1.53)]          # side seam |x| on the back half (back view)
ZH=Zmap(852)
ROWS=[372,390,420,460,500,540,580,612,630,650,680,710,740,770,800,820,840,852]
def row(y):
    return dict(z=Zmap(y),hx=I(HXt,y),yf=I(YFt,y),yb=I(YBt,y),n=I(NN,y),xl=XF(I(OPL,y)),xr=XF(I(OPR,y)))
def dense(r,N=720,off=0.0):
    cy=(r['yf']+r['yb'])/2; hy=(r['yf']-r['yb'])/2-off; hx=r['hx']-off; n=r['n']
    t=np.linspace(0,2*pi,N,endpoint=False); s,c=np.sin(t),np.cos(t)
    x=hx*np.sign(s)*np.abs(s)**(2/n); y=cy+hy*np.sign(c)*np.abs(c)**(2/n)
    return x,y,t
def arc_param(r,ts,off=0.0):
    cy=(r['yf']+r['yb'])/2; hy=(r['yf']-r['yb'])/2-off; hx=r['hx']-off; n=r['n']
    s,c=np.sin(ts),np.cos(ts)
    return hx*np.sign(s)*np.abs(s)**(2/n), cy+hy*np.sign(c)*np.abs(c)**(2/n)
def t_at_x(r,xv,front=True):
    x,y,t=dense(r); cy=(r['yf']+r['yb'])/2
    m=(y>=cy) if front else (y<cy)
    idx=np.nonzero(m)[0]; k=idx[np.argmin(np.abs(x[idx]-xv))]; return t[k]
# angle convention: t=0 front centre, increases toward +x (right side of character), t=pi back centre
def t_open_right(r): return t_at_x(r,r['xr'] if r['xr']>0 else 0.0)         # +x side? note xl>0 (char right = +x)
def build():
    T=Part('Gear_Torso','Torso')
    TH=0.045
    R=[row(y) for y in ROWS]
    # opening angles: right (+x) edge uses xl (sheet-left = +x), left (-x) edge uses xr
    def ang_open(r):
        a=t_at_x(r,r['xl']); b=t_at_x(r,r['xr'])
        a=a if a<pi else a-2*pi
        b=b if b>pi else b+2*pi
        return max(a,0.02),min(b,2*pi-0.02)
    K=96
    rings_o=[];rings_i=[];tt=[]
    for r in R:
        a,b=ang_open(r); ts=np.linspace(a,b,K); tt.append(ts)
        xo,yo=arc_param(r,ts); xi,yi=arc_param(r,ts,TH)
        rings_o.append([(xo[k],yo[k],r['z']) for k in range(K)]); rings_i.append([(xi[k],yi[k],r['z']) for k in range(K)])
    # back hem lower: drop the bottom rows toward the back
    def zdrop(i,k):
        if ROWS[i]<800: return 0.0
        w=(ROWS[i]-800)/52.0; tb=abs(((tt[i][k]-pi)+pi)%(2*pi)-pi)  # 0 at back centre
        return -0.07*w*max(0,1-tb/2.2)
    for i in range(len(R)):
        for k in range(K):
            d=zdrop(i,k); rings_o[i][k]=(rings_o[i][k][0],rings_o[i][k][1],rings_o[i][k][2]+d); rings_i[i][k]=(rings_i[i][k][0],rings_i[i][k][1],rings_i[i][k][2]+d)
    # which ring faces belong to the back panel (below the seam start) -> skip in the main shell, built separately
    def in_back(i,k):
        if ROWS[i]<630: return False
        xs=I(SEAM,ROWS[i]); x,y,z=rings_o[i][k]; cy=(R[i]['yf']+R[i]['yb'])/2
        return y<cy and abs(x)<xs
    for i in range(len(R)-1):
        for k in range(K-1):
            if in_back(i+1,k) and in_back(i+1,k+1) and ROWS[i]>=630: continue
            T.face([rings_o[i][k],rings_o[i][k+1],rings_o[i+1][k+1],rings_o[i+1][k]],M['Marble'])
            T.face([rings_i[i][k+1],rings_i[i][k],rings_i[i+1][k],rings_i[i+1][k+1]],M['Lining'])
    # ---- back panel: between the seams, slightly inside the front panels, overlapping under them
    VENT0=790; NB=61; CK=30
    def back_ring(i,off):
        r=R[i]; xs=I(SEAM,ROWS[i])+0.08
        ta=t_at_x(r,xs,front=False); tb=t_at_x(r,-xs,front=False)
        ts=np.linspace(ta,tb,NB); x,y=arc_param(r,ts,off)
        return [(x[k],y[k],r['z']+zdrop_b(i,ts[k])) for k in range(NB)],ts
    def zdrop_b(i,t):
        if ROWS[i]<800: return 0.0
        w=(ROWS[i]-800)/52.0; tb=abs(((t-pi)+pi)%(2*pi)-pi); return -0.07*w*max(0,1-tb/2.2)
    bi=[i for i in range(len(R)) if ROWS[i]>=630]
    BO=[back_ring(i,0.012)[0] for i in bi]; BI=[back_ring(i,0.012+TH)[0] for i in bi]
    def halves(ring,i):
        v=0.0 if ROWS[i]<=VENT0 else 0.035*(ROWS[i]-VENT0)/(852-VENT0)
        L=[ring[k] for k in range(CK+1)]; Rr=[ring[k] for k in range(CK,NB)]
        # centre edge pulls apart (V opening toward the hem); positive x side is k<CK (t from +x around back)
        def sh(p,dx): return (p[0]+dx,p[1],p[2])
        L[-1]=sh(L[-1],v); L[-2]=sh(L[-2],v*0.5)
        Rr[0]=sh(Rr[0],-v); Rr[1]=sh(Rr[1],-v*0.5)
        return L,Rr
    HO=[halves(BO[a],bi[a]) for a in range(len(bi))]; HI=[halves(BI[a],bi[a]) for a in range(len(bi))]
    for side in (0,1):
        for a in range(len(bi)-1):
            ro0,ro1=HO[a][side],HO[a+1][side]; ri0,ri1=HI[a][side],HI[a+1][side]; n=len(ro0)
            for k in range(n-1):
                T.face([ro0[k],ro0[k+1],ro1[k+1],ro1[k]],M['Marble'])
                T.face([ri0[k+1],ri0[k],ri1[k],ri1[k+1]],M['Lining'])
            se=0 if side==0 else n-1      # seam edge
            ce=n-1 if side==0 else 0      # vent edge
            T.face([ro0[se],ri0[se],ri1[se],ro1[se]],M['Marble'])
            if ROWS[bi[a+1]]>VENT0:
                T.face([ro0[ce],ri0[ce],ri1[ce],ro1[ce]],M['Marble'])
    # vent underlap (behind the vent)
    ui=[i for i in range(len(R)) if ROWS[i]>=770]
    U_o=[];U_i=[]
    for i in ui:
        r=R[i]; ta=t_at_x(r,0.16,False); tb=t_at_x(r,-0.16,False); ts=np.linspace(ta,tb,9)
        x,y=arc_param(r,ts,0.012+TH+0.012); x2,y2=arc_param(r,ts,0.012+TH+0.012+0.03)
        U_o.append([(x[k],y[k],r['z']+zdrop_b(i,ts[k])) for k in range(9)]); U_i.append([(x2[k],y2[k],r['z']+zdrop_b(i,ts[k])) for k in range(9)])
    T.loft(U_o,M['Marble'],closed=False); T.loft(U_i[::-1],M['Lining'],closed=False)
    # top of the coat (shoulder band to neck ring, the collar sits on it in part 3)
    r0=R[0]; ts=tt[0]; nx,ny=arc_param(dict(r0,hx=0.62,yf=0.50,yb=-0.55,n=4),ts)
    for k in range(K-1):
        T.face([rings_o[0][k+1],rings_o[0][k],(nx[k],ny[k],r0['z']+0.03),(nx[k+1],ny[k+1],r0['z']+0.03)],M['Marble'])
        T.face([(nx[k],ny[k],r0['z']+0.03),rings_i[0][k],rings_i[0][k+1],(nx[k+1],ny[k+1],r0['z']+0.03)],M['Lining'])
    # front opening edges + seam edges of the front panels (rims)
    for i in range(len(R)-1):
        for e in (0,K-1):
            T.face([rings_o[i][e],rings_i[i][e],rings_i[i+1][e],rings_o[i+1][e]],M['Gold'])
        if ROWS[i]>=630:
            for k in range(K-1):
                if in_back(i+1,k)!=in_back(i+1,k+1):
                    kk=k if not in_back(i+1,k) else k+1
                    T.face([rings_o[i][kk],rings_i[i][kk],rings_i[i+1][kk],rings_o[i+1][kk]],M['Marble'])
    # rolled hem: curl the bottom inward (shows lining)
    last=len(R)-1
    def curl(ring_o,ring_i,inw,dz):
        out=[]
        for (a,b) in zip(ring_o,ring_i):
            v=V(b)-V(a); v.z=0
            v=v.normalized() if v.length>1e-9 else V((0,0,0))
            out.append(tuple(V(a)+v*inw+V((0,0,dz))))
        return out
    for k in range(K-1):
        if in_back(last,k) and in_back(last,k+1): continue
        c1=curl(rings_o[last],rings_i[last],0.03,-0.04); c2=curl(rings_o[last],rings_i[last],0.10,-0.055)
        T.face([rings_o[last][k],rings_o[last][k+1],c1[k+1],c1[k]],M['Marble'])
        T.face([c1[k],c1[k+1],c2[k+1],c2[k]],M['Lining'])
        T.face([c2[k],c2[k+1],rings_i[last][k+1],rings_i[last][k]],M['Lining'])
    lb=len(BO)-1
    for side in (0,1):
        ro=HO[lb][side]; ri=HI[lb][side]; n=len(ro)
        c1=curl(ro,ri,0.03,-0.04); c2=curl(ro,ri,0.10,-0.055)
        for k in range(n-1):
            T.face([ro[k],ro[k+1],c1[k+1],c1[k]],M['Marble'])
            T.face([c1[k],c1[k+1],c2[k+1],c2[k]],M['Lining'])
            T.face([c2[k],c2[k+1],ri[k+1],ri[k]],M['Lining'])
    # ---- gold binding: front edges (raised strip on outer face, wraps the edge) and hem band
    for e,inward in ((0,1),(K-1,-1)):
        pts=[];nr=[]
        for i in range(len(R)):
            p=V(rings_o[i][e]); q=V(rings_o[i][e+inward*3]); d=(q-p).normalized()
            n=(V(rings_o[i][e])-V(rings_i[i][e])); n.z=0; n.normalize()
            pts.append(tuple(p+d*0.035)); nr.append(n)
        strip(T,pts,nr,0.05,0.02,M['Gold'])
    def hem_band(ring,ringi,ks,skip=None):
        pts=[];nr=[]
        for k in ks:
            if skip is not None and k==skip: 
                if len(pts)>1: strip(T,pts,nr,0.05,0.018,M['Gold'])
                pts=[];nr=[]; continue
            p=V(ring[k]); n=V(ring[k])-V(ringi[k]); n.z=0; n.normalize()
            pts.append(tuple(p+V((0,0,0.055)))); nr.append(n)
        if len(pts)>1: strip(T,pts,nr,0.05,0.018,M['Gold'])
    # front panels hem band (each side separately, stopping at the seam)
    ks=[k for k in range(K) if not in_back(last,k)]
    groups=[];cur=[]
    for k in ks:
        if cur and k!=cur[-1]+1: groups.append(cur); cur=[]
        cur.append(k)
    if cur: groups.append(cur)
    for g_ in groups: hem_band(rings_o[last],rings_i[last],g_)
    for side in (0,1): hem_band(HO[lb][side],HI[lb][side],list(range(len(HO[lb][side]))))
    return T
ob=build().build()
print('coat tris',sum(len(p.vertices)-2 for p in ob.data.polygons))
bpy.ops.wm.save_as_mainfile(filepath=OUT)
