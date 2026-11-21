import numpy as np, cv2, math
CIRC=[(0.0,0.24,0.22),(0.265,0.13,0.135),(-0.265,0.12,0.125)]
RES=600
def raster(inset=0.0):
    W=int(1.2*RES); H=int(0.6*RES); img=np.zeros((H,W),np.uint8)
    for cu,cw,r in CIRC: cv2.circle(img,(int((cu+0.6)*RES),int((0.55-cw)*RES)),int((r-inset)*RES),1,-1,cv2.LINE_8)
    img[int(0.55*RES):]=0
    return img
def uw(px,py): return px/RES-0.6, 0.55-py/RES
def resample(a,step=0.01):
    a=np.asarray(a,float); L=np.r_[0,np.cumsum(np.linalg.norm(np.diff(a,axis=0),axis=1))]
    s=np.arange(0,L[-1],step); s=np.r_[s,L[-1]]
    return np.c_[np.interp(s,L,a[:,0]),np.interp(s,L,a[:,1])]
def outline():
    # analytic union-of-circles top boundary, left foot -> right foot
    us=np.linspace(-0.39,0.40,400); ws=[]
    for u in us:
        w=0
        for cu,cw,r in CIRC:
            d=r*r-(u-cu)**2
            if d>0: w=max(w,cw+math.sqrt(d))
        ws.append(w)
    a=np.c_[us,ws]; a=a[a[:,1]>0.004]
    # smooth the cusps slightly (still reads as separate bumps)
    k=5; sm=np.convolve(np.pad(a[:,1],(k,k),mode='edge'),np.ones(2*k+1)/(2*k+1),mode='valid'); a[:,1]=np.minimum(a[:,1],sm+0.004)
    return resample(a,0.008)
def plates():
    img=raster(0.0); img=cv2.erode(img,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(int(0.064*RES),int(0.064*RES))))
    cv2.rectangle(img,(int((0.6-0.33)*RES),int((0.55-0.13)*RES)),(int((0.6+0.35)*RES),int((0.55-0.02)*RES)),1,-1)
    img[int((0.55-0.02)*RES):]=0
    img=cv2.morphologyEx(img,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(25,25)))
    cs,_=cv2.findContours(img,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE); out=[]
    for c in cs:
        if cv2.contourArea(c)<200: continue
        c=cv2.approxPolyDP(c,1.5,True)[:,0,:]; out.append(np.array([uw(x,y) for x,y in c]))
    return out
def spiral(cu,cw,r0,turns,start,ccw=False,n=80):
    out=[]
    for i in range(n):
        f=i/(n-1); a=start+(1 if ccw else -1)*turns*2*math.pi*f; r=r0*(1-0.85*f)
        out.append((cu+r*math.cos(a),cw+r*math.sin(a)))
    return resample(out,0.008)
def arc(cu,cw,r,a0,a1): return resample([(cu+r*math.cos(a),cw+r*math.sin(a)) for a in np.linspace(a0,a1,60)],0.008)
def strokes():
    return [(outline(),0.022),
            (arc(0.0,0.24,0.165,math.radians(30),math.radians(150)),0.011),
            (spiral(-0.265,0.12,0.088,1.25,math.pi,ccw=False),0.016),
            (spiral(0.265,0.13,0.085,1.05,0.0,ccw=True),0.014)]
if __name__=='__main__':
    img=np.full((420,820,3),235,np.uint8); S=600; ox,oy=410,360
    tp=lambda a: np.array([(ox+u*S,oy-w*S) for u,w in a]).astype(np.int32).reshape(-1,1,2)
    cv2.fillPoly(img,[tp(p) for p in plates()],(225,175,225))
    for a,w in strokes(): cv2.polylines(img,[tp(a)],False,(40,160,220),max(2,int(w*2*S)),cv2.LINE_AA)
    cv2.line(img,(0,oy+10),(820,oy+10),(40,160,220),26)
    cv2.imwrite('/tmp/w/motif.png',img)
