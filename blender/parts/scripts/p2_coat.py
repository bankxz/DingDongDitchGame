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
FOLDS=[(pi,0.14,-0.10),(pi-0.42,0.22,0.06),(pi+0.42,0.22,0.06),(pi-0.80,0.16,-0.05),(pi+0.80,0.16,-0.05),
       (1.45,0.16,-0.08),(2*pi-1.45,0.16,-0.08),(1.15,0.18,0.05),(2*pi-1.15,0.18,0.05),(1.78,0.18,0.05),(2*pi-1.78,0.18,0.05),
       (0.80,0.24,0.055),(2*pi-0.80,0.24,0.055),(0.50,0.14,-0.03),(2*pi-0.50,0.14,-0.03)]                                  # front panel ridges
def fold_off(ts,z):
    f=np.clip((Zmap(612)-z)/(Zmap(612)-Zmap(852)),0,1)**1.1
    o=np.zeros_like(ts)
    for t0,w,a in FOLDS:
        d=np.angle(np.exp(1j*(ts-t0))); o+=a*np.exp(-(d/w)**2)
    return o*f
def arc_param(r,ts,off=0.0):
    cy=(r['yf']+r['yb'])/2; hy=(r['yf']-r['yb'])/2-off; hx=r['hx']-off; n=r['n']
    ts=np.asarray(ts,float); s,c=np.sin(ts),np.cos(ts)
    x=hx*np.sign(s)*np.abs(s)**(2/n); y=cy+hy*np.sign(c)*np.abs(c)**(2/n)
    o=fold_off(ts,r['z']); dx=x; dy=y-cy; L=np.hypot(dx,dy)+1e-9
    return x+o*dx/L, y+o*dy/L
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
    # ================= traced gold trim + cloud plates, laid onto the coat surface
    import pickle
    from mathutils.bvhtree import BVHTree
    D=pickle.load(open('/tmp/w/parts/coat_trims.pkl','rb'))
    tree=BVHTree.FromPolygons([V(v) for v in T.v],[ids for ids,_ in T.f])
    def ray(view,px,py):
        z=Zmap(py)
        if view=='F': return V((XF(px),20,z)),V((0,-1,0))
        if view=='B': return V(((px-1179.5)/121,-20,z)),V((0,1,0))
        if view=='SL': return V((-20,(722-px)/121,z)),V((1,0,0))
        return V((20,(722-px)/121,z)),V((-1,0,0))
    def hit(view,px,py):
        o,d=ray(view,px,py); h=tree.ray_cast(o,d,60)
        if h[0] is None: return None
        n=h[1].copy()
        if n.dot(d)>0: n=-n
        if n.dot(-d)<0.25: return None
        return h[0],n
    nst=0
    def in_motif(vw,poly):
        if vw!='B': return False
        x=poly[:,0].mean(); y=poly[:,1].mean()
        return (1085<x<1275 and y<768) or (1148<x<1212 and y<846)
    for vw,poly,wpx in D['lines']:
        if in_motif(vw,poly): continue
        views=['SL','SR'] if vw=='S' else [vw]
        pts=[poly[0]]
        for a_,b_ in zip(poly[:-1],poly[1:]):
            dd=np.linalg.norm(b_-a_); k=max(1,int(dd/2.0))
            for q in range(1,k+1): pts.append(a_+(b_-a_)*q/k)
        hw=max(wpx,4.0)/2/121
        for view in views:
            run=[];rn=[]
            for px,py in pts:
                h=hit(view,px,py)
                if h is None:
                    if len(run)>1: strip(T,run,rn,hw,0.02,M['Gold']); nst+=1
                    run=[];rn=[]; continue
                run.append(tuple(h[0])); rn.append(h[1])
            if len(run)>1: strip(T,run,rn,hw,0.02,M['Gold']); nst+=1
    CL=mat('Cloud',(0.78,0.66,0.90),0,0.4)
    npl=0
    for vw,vs,tr in D['cloud_tris']:
        views=['SL','SR'] if vw=='S' else [vw]
        for view in views:
            hs=[hit(view,px,py) for px,py in vs]
            kept=[t3 for t3 in tr if all(hs[i] is not None for i in t3)]
            ec={}
            for t3 in kept:
                for a_,b_ in ((t3[0],t3[1]),(t3[1],t3[2]),(t3[2],t3[0])): k=(min(a_,b_),max(a_,b_)); ec[k]=ec.get(k,0)+1
            for t3 in kept:
                top=[tuple(hs[i][0]+hs[i][1]*0.008) for i in t3]; bot=[tuple(hs[i][0]-hs[i][1]*0.004) for i in t3]
                T.face(top,CL); T.face(bot[::-1],CL)
                for a_,b_ in ((t3[0],t3[1]),(t3[1],t3[2]),(t3[2],t3[0])):
                    if ec[(min(a_,b_),max(a_,b_))]==1:
                        T.face([tuple(hs[a_][0]+hs[a_][1]*0.008),tuple(hs[b_][0]+hs[b_][1]*0.008),tuple(hs[b_][0]-hs[b_][1]*0.004),tuple(hs[a_][0]-hs[a_][1]*0.004)],CL)
                npl+=1
    # ---- back centre motif, measured (back-view px), symmetric about x=1180
    def mir(pl): return [(2*1180-x,y) for x,y in pl]
    MOT=[([(1140,388),(1140,705),(1095,736),(1090,766)],5.5),
         ([(1172,392),(1172,532)],5.0),([(1172,605),(1172,731),(1160,746),(1160,800),(1170,815),(1170,842)],5.5),
         ([(1131,571),(1180,522),(1229,571)],6.0),([(1131,571),(1172,609)],6.0),
         ([(1151,573),(1180,546),(1209,573)],5.0),([(1151,573),(1172,594)],5.0)]
    G=Part('Glow_Torso','Torso')
    def lay(pl,hw,part,mat_,h=0.02):
        pts=[pl[0]]
        for a_,b_ in zip(pl[:-1],pl[1:]):
            a_=np.array(a_,float); b_=np.array(b_,float); k=max(1,int(np.linalg.norm(b_-a_)/2))
            for q in range(1,k+1): pts.append(a_+(b_-a_)*q/k)
        run=[];rn=[]
        for px,py in pts:
            hh=hit('B',px,py)
            if hh is None: continue
            run.append(tuple(hh[0])); rn.append(hh[1])
        if len(run)>1: strip(part,run,rn,hw,h,mat_)
    for pl,w in MOT:
        lay(pl,w/2/121,T,M['Gold']); 
        if pl[0][0]!=1180: lay(mir(pl) if pl!=MOT[3][0] and pl!=MOT[5][0] else pl,w/2/121,T,M['Gold'])
    for pl in ([(1180,490),(1180,786)],): lay(pl,2.4/121,G,M['Glow'],0.026)
    # glow plates: diamond core and lower lozenge (raised discs projected)
    def plate(poly_px,part,mat_,lift):
        c=np.mean(poly_px,0); ring=[]
        for px,py in poly_px:
            hh=hit('B',px,py); 
            if hh is None: return
            ring.append(hh)
        hc=hit('B',*c)
        if hc is None: return
        top=[tuple(h_[0]+h_[1]*lift) for h_ in ring]; ct=tuple(hc[0]+hc[1]*lift)
        bot=[tuple(h_[0]-h_[1]*0.004) for h_ in ring]
        for i in range(len(ring)):
            j=(i+1)%len(ring); part.face([top[i],top[j],ct],mat_); part.face([top[j],top[i],bot[i],bot[j]],mat_)
        part.face(bot[::-1],mat_)
    plate([(1180,552),(1203,573),(1180,592),(1157,573)],G,M['Glow'],0.012)
    plate([(1180,742),(1196,750),(1196,800),(1180,812),(1164,800),(1164,750)],G,M['Glow'],0.008)
    G.build()
    print('trim strips',nst,'cloud tris',npl)
    return T
ob=build().build()
print('coat tris',sum(len(p.vertices)-2 for p in ob.data.polygons))
bpy.ops.wm.save_as_mainfile(filepath=OUT)
