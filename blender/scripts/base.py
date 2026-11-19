import math, numpy as np, cv2
from mathutils import Vector as V, Matrix
from kit import *
def build_base(M):
    P={}
    fgm=np.load('/tmp/w/masks.npz')['fg']
    def frow(y):
        xs=np.nonzero(fgm[y,0:560])[0]; return XF(xs.max()),XF(xs.min())
    # ================= COAT
    T=Part('Gear_Torso','Torso'); P['Torso']=T
    OPL=[(373,250),(500,250),(560,232),(632,213),(650,200),(700,187),(750,175),(800,163),(858,150)]
    OPR=[(373,323),(500,326),(560,345),(632,362),(650,366),(700,376),(750,386),(800,396),(858,407)]
    YB=[(373,-0.66),(420,-0.58),(600,-0.57),(632,-0.66),(650,-0.79),(700,-0.87),(750,-0.97),(800,-1.11),(852,-1.23),(858,-1.2)]
    YFt=[(373,0.61),(632,0.61),(858,0.67)]
    NN=[(373,8),(632,8),(645,6),(700,5),(750,4.5),(800,4),(858,3.5)]
    rows=[]
    for y in [373,380,400,430,460,500,540,580,610,632,642,655,675,700,725,750,775,800,822,840,852,857,859]:
        if y<=632: x0,x1=-1.05,1.05
        else:
            yy=min(y,852); x0,x1=frow(yy)
            if y>=857: x0+=0.02*(y-855); x1-=0.02*(y-855)
        rows.append((y,x0,x1,interp(YB,y),interp(YFt,y),XF(interp(OPL,y)),XF(interp(OPR,y)),interp(NN,y)))
    def ring(r,th,N,scale=1.0,z=None):
        y,x0,x1,yb,yf,ol,orr,n=r; cx=(x0+x1)/2; hx=(x1-x0)/2*scale-th; cy=(yb+yf)/2; hy=(yf-yb)/2*scale-th
        tl=math.asin(min(0.999,max(0.0,(ol-cx)/hx))**(n/2)); tr=math.asin(min(0.999,max(0.0,(cx-orr)/hx))**(n/2))
        return se(cx,hx,cy,hy,Zmap(y) if z is None else z,n,N,tl,2*pi-tr,True)
    NC=49; TH=0.05
    O=[ring(r,0,NC) for r in rows]; I=[ring(r,TH,NC) for r in rows]
    for i in range(len(rows)-1):
        for j in range(NC-1):
            T.face([O[i][j],O[i][j+1],O[i+1][j+1],O[i+1][j]],M['Marble'])
            T.face([I[i][j+1],I[i][j],I[i+1][j],I[i+1][j+1]],M['Lining'])
        for e in (0,NC-1):
            T.face([O[i][e],I[i][e],I[i+1][e],O[i+1][e]],M['Gold'])
    for j in range(NC-1):
        T.face([O[-1][j],I[-1][j],I[-1][j+1],O[-1][j+1]],M['Gold'])
    # shoulder top + standing collar
    r0=rows[0]; z0=Zmap(373)
    B0=ring(r0,0,NC,0.90,z0); B1=ring(r0,0,NC,0.86,z0)
    def coll_top(j,sc):
        p=ring(r0,0,NC,sc,z0)[j]; t=j/(NC-1); f=min(t,1-t)/0.12
        return (p[0],p[1],z0+0.23*min(1.0,0.15+0.85*f))
    T0=[coll_top(j,0.94) for j in range(NC)]; T1=[coll_top(j,0.905) for j in range(NC)]
    for j in range(NC-1):
        T.face([O[0][j+1],O[0][j],B0[j],B0[j+1]],M['Marble'])
        T.face([B0[j+1],B0[j],T0[j],T0[j+1]],M['Purple'])
        T.face([T0[j+1],T0[j],T1[j],T1[j+1]],M['Gold'])
        T.face([T1[j+1],T1[j],B1[j],B1[j+1]],M['Purple'])
        T.face([B1[j+1],B1[j],I[0][j],I[0][j+1]],M['Lining'])
    for e in (0,NC-1):
        T.face([O[0][e],B0[e],T0[e],T1[e],B1[e],I[0][e]],M['Gold'])
    # gold rim tube on collar top
    for j in range(NC-1):
        a=V(T0[j]);b=V(T0[j+1]); c=V(T1[j]); d=V(T1[j+1])
        T.face([tuple(a+V((0,0,0.02))),tuple(b+V((0,0,0.02))),tuple(d+V((0,0,0.02))),tuple(c+V((0,0,0.02)))],M['Gold'])
        T.face([T0[j],T0[j+1],tuple(b+V((0,0,0.02))),tuple(a+V((0,0,0.02)))],M['Gold'])
        T.face([T1[j+1],T1[j],tuple(c+V((0,0,0.02))),tuple(d+V((0,0,0.02)))],M['Gold'])
    T.coat_rows=rows
    # explicit raised gold trims: front opening edges (outer face) and hem band
    def edge_trim(e,inward,width=0.085,h=0.022):
        rings=[]
        for i in range(len(rows)):
            p=V(O[i][e]); q=V(O[i][e+inward]); dvec=(q-p).normalized()
            nrm_=(V(O[i][e])-V(I[i][e])).normalized()
            a=p-dvec*0.012; b=p+dvec*width
            rings.append([tuple(a-nrm_*0.004),tuple(b-nrm_*0.004),tuple(b+nrm_*h*0.7),tuple(p+dvec*width*0.75+nrm_*h),tuple(a+dvec*width*0.2+nrm_*h),tuple(a+nrm_*h*0.7)])
        T.loft(rings,M['Gold'],cap0=M['Gold'],cap1=M['Gold'])
    edge_trim(0,1); edge_trim(NC-1,-1)
    # purple lapel facings (raised slightly) + outer gold line, tapering out by y 566
    FW=[(373,0.235),(500,0.235),(566,0.0),(900,0.0)]
    for e,inward in ((0,1),(NC-1,-1)):
        fr=[];gr=[]
        for i,r in enumerate(rows):
            w=interp(FW,r[0]); p=V(O[i][e]); nrm_=(V(O[i][e])-V(I[i][e])).normalized()
            # walk along ring by arc length w
            acc=0; k=e; q=p
            while acc<w+0.085 and 0<=k+inward<NC:
                seg=V(O[i][k+inward])-V(O[i][k]); L=seg.length
                if acc+L>=w+0.085: q=V(O[i][k])+seg*((w+0.085-acc)/L); acc=w+0.085; break
                acc+=L; k+=inward; q=V(O[i][k])
            dvec=(q-p).normalized() if (q-p).length>1e-6 else V((0,0,0))
            a=p+dvec*0.06; b2=p+dvec*(0.085+w)
            fr.append([tuple(a-nrm_*0.004),tuple(b2-nrm_*0.004),tuple(b2+nrm_*0.012),tuple(a+nrm_*0.012)])
            gr.append((b2,dvec,nrm_))
        sel=[i for i,r in enumerate(rows) if r[0]<=566]
        T.loft([fr[i] for i in sel],M['Purple'],cap0=M['Purple'],cap1=M['Purple'])
        rings=[]
        for i,r in enumerate(rows):
            b2,dvec,nrm_=gr[i]; hw=0.04
            rings.append([tuple(b2-dvec*hw-nrm_*0.004),tuple(b2+dvec*hw-nrm_*0.004),tuple(b2+dvec*hw+nrm_*0.016),tuple(b2+dvec*hw*0.6+nrm_*0.024),tuple(b2-dvec*hw*0.6+nrm_*0.024),tuple(b2-dvec*hw+nrm_*0.016)])
        T.loft([rings[i] for i in range(len(rows)) if rows[i][0]<=600],M['Gold'],cap0=M['Gold'],cap1=M['Gold'])
    rings=[]
    zt=0.11
    for j in range(NC):
        p=V(O[-1][j]); q=V(O[-2][j]); up=(q-p).normalized(); 
        nrm_=(V(O[-1][j])-V(I[-1][j])).normalized()
        a=p-up*0.008; b=p+up*zt
        rings.append([tuple(a-nrm_*0.004),tuple(b-nrm_*0.004),tuple(b+nrm_*0.016),tuple(p+up*zt*0.8+nrm_*0.024),tuple(a+up*0.02+nrm_*0.024),tuple(a+nrm_*0.016)])
    T.loft(rings,M['Gold'],cap0=M['Gold'],cap1=M['Gold'])
    # ================= INNER BODY (kimono)
    yb_,yf_=-0.45,0.545; cyb=(yb_+yf_)/2; hyb=(yf_-yb_)/2
    T.loft([se(0,0.94,cyb,hyb,z,8,24) for z in (2.0,3.0,4.0)],M['Navy'],cap0=M['Navy'],cap1=M['Navy'])
    # neck skin V
    zt=3.99
    T.face([(XF(258),0.549,zt),(XF(283),0.549,Zmap(412)),(XF(318),0.549,zt)],M['Skin'])
    T.face([(XF(258),0.546,zt),(XF(318),0.546,zt),(XF(283),0.546,Zmap(412))],M['Skin'])
    # ================= OBI (three wrapped bands, slight tilts)
    for k,(za,zb,tilt) in enumerate([(2.28,2.64,0.0),(2.56,2.92,0.05),(2.84,3.12,-0.045)]):
        R=Matrix.Rotation(tilt,3,'X')@Matrix.Rotation(tilt*0.6,3,'Y')
        rings=[]
        for z in (za,(za+zb)/2,zb):
            pts=se(0,0.965+0.006*k,cyb,hyb+0.012+0.004*k,0,6,32)
            zc=(za+zb)/2
            rings.append([tuple(R@V((p[0],p[1]-cyb,z-zc))+V((0,cyb,zc))) for p in pts])
        T.loft(rings,M['Black'],cap0=M['Black'],cap1=M['Black'])
    # knot tab, ring, tail, tassel
    x0,x1=XF(345),XF(320)
    T.box(((x0+x1)/2,0.595,(Zmap(585)+Zmap(487))/2),(abs(x1-x0),0.07,Zmap(487)-Zmap(585)),M['Black'],R=Matrix.Rotation(-0.06,3,'Y'))
    rc=V((XF(332),0.64,Zmap(590)))
    rings=[]
    for i in range(16):
        a=2*pi*i/16; c=rc+V((math.cos(a)*0.085,0,math.sin(a)*0.085))
        rings.append([tuple(c+V((math.cos(a)*math.cos(b)*0.018,math.sin(b)*0.018,math.sin(a)*math.cos(b)*0.018))) for b in [2*pi*k/8 for k in range(8)]])
    T.loft(rings+[rings[0]],M['Gold'])
    # tail cloth hanging behind tassel
    xl,xr=XF(355),XF(300); rings=[]
    for z in np.linspace(2.36,1.34,8):
        yf=0.56 if z>2.0 else interp([(Ymap(2.0),0.56),(700,0.665),(800,0.83)],Ymap(z))+0.02
        rings.append([(xr,yf,z),(xl,yf,z),(xl,yf+0.035,z),(xr,yf+0.035,z)])
    T.loft(rings,M['Black'],cap0=M['Black'],cap1=M['Black'])
    # tassel lathe from front mask widths
    tas=np.load('/tmp/w/masks.npz')['tas']; ys=np.nonzero(tas.any(1))[0]
    tc=(XF(332),0.70); prof=[]
    for y in range(ys.min(),ys.max()+1,4):
        xs=np.nonzero(tas[y])[0]
        if len(xs): prof.append((Zmap(y),max(0.012,(xs.max()-xs.min()+1)/2/S)))
    prof=[(Zmap(ys.min())+0.01,0.005)]+prof+[(Zmap(ys.max())-0.005,0.02)]
    NT=24; rings=[]
    zs_skirt=Zmap(ys.min())-0.28
    for z,r in prof:
        rings.append([(tc[0]+r*(0.92 if (j%2 and z<zs_skirt) else 1.0)*math.cos(2*pi*j/NT),tc[1]+r*(0.92 if (j%2 and z<zs_skirt) else 1.0)*math.sin(2*pi*j/NT),z) for j in range(NT)])
    T.loft(rings,M['Gold'],cap0=M['Gold'],cap1=M['Gold'])
    # hakama top (pleated)
    pl=lambda i,t: 1.0-0.03*(i%2)
    T.loft([se(0,0.955,cyb,hyb+0.005,z,6,48,mod=pl) for z in (2.0,2.15,2.3)],M['Navy'],cap0=M['Navy'],cap1=M['Navy'])
    # ================= SLEEVES
    for bone,sx in (('Right Arm',1),('Left Arm',-1)):
        A=Part('Gear_'+bone.replace(' ',''),bone); P[bone]=A
        cx=sx*1.5125; hx=0.5375; cy=-0.04; hy=0.585; n=10; N=40
        zb=Zmap(603)
        zs=[zb,zb+0.06,2.6,3.0,3.4,3.8,3.97]
        out=[se(cx,hx,cy,hy,z,n,N) for z in zs]+[se(cx,hx*0.94,cy,hy*0.94,4.04,n,N),se(cx,hx*0.82,cy,hy*0.82,4.065,n,N)]
        inn=[se(cx,hx-0.035,cy,hy-0.035,z,n,N) for z in (zb,3.9)]
        A.loft(out,M['Marble'],cap1=M['Marble'])
        A.loft(inn,M['Lining'],cap1=M['Lining'])
        for j in range(N):
            k=(j+1)%N; A.face([out[0][k],out[0][j],inn[0][j],inn[0][k]],M['Gold'])
        # cuff bands (raised)
        for (ya,yb2,m,o) in ((573,590,'Gold',0.022),(599,603.5,'Gold',0.022)):
            A.loft([se(cx,hx+o,cy,hy+o,Zmap(y),n,N) for y in (ya,yb2)],M[m],cap0=M[m],cap1=M[m])
        A.cx=cx
    # ================= LEGS
    for bone,sx in (('Right Leg',1),('Left Leg',-1)):
        L=Part('Gear_'+bone.replace(' ',''),bone); P[bone]=L
        rows=[(632,1.03,0.545),(660,1.05,0.58),(700,1.09,0.635),(750,1.145,0.72),(800,1.20,0.80),(840,1.26,0.87),(870,1.31,0.92),(905,1.31,0.95)]
        rings=[]
        for y,xo,yf in rows:
            cxl=sx*xo/2; hxl=xo/2; cyl=(yf-0.555)/2; hyl=(yf+0.555)/2
            rings.append(se(cxl,hxl,cyl,hyl,Zmap(y),5 if y>640 else 7,48,mod=lambda i,t: 1.0-0.035*(i%2)))
        L.loft(rings,M['Navy'],cap0=M['Navy'],cap1=M['NavyDark'])
        # boots
        bx0,bx1=0.05,1.17; byf,byb=0.875,-0.465
        bc=(sx*(bx0+bx1)/2,(byf+byb)/2); bh=((bx1-bx0)/2,(byf-byb)/2)
        L.loft([se(bc[0],bh[0],bc[1],bh[1],z,9,32) for z in (0.0,0.02,Zmap(907))]+[se(bc[0],bh[0]*0.97,bc[1],bh[1]*0.97,Zmap(905),9,32)],M['Black'],cap0=M['Black'],cap1=M['Black'])
        L.loft([se(bc[0],bh[0]+0.02,bc[1],bh[1]+0.02,z,9,32) for z in (0.0,0.035)],M['BlackSole'],cap0=M['BlackSole'],cap1=M['BlackSole'])
    return P
