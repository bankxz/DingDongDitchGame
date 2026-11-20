import numpy as np, cv2, pickle, sys
sys.path.insert(0,'/tmp/w/s3')
from tripre import tri_safe
im=cv2.imread('/tmp/w/ref.png'); H,W=im.shape[:2]; K=3
up=cv2.resize(im,(W*K,H*K),interpolation=cv2.INTER_CUBIC)
hsv=cv2.cvtColor(up,cv2.COLOR_BGR2HSV).astype(int); h,s,v=hsv[...,0],hsv[...,1],hsv[...,2]
b,g,r=[up[...,i].astype(int) for i in range(3)]; lum=(r+g+b)/3
def box(x0,x1,y0,y1): m=np.zeros((H*K,W*K),bool); m[y0*K:y1*K,x0*K:x1*K]=True; return m
def fill_holes(m,maxa):
    m8=m.astype(np.uint8); inv=1-m8
    n,lab,st,_=cv2.connectedComponentsWithStats(inv,connectivity=4)
    small=np.zeros(n,bool); small[1:]=st[1:,4]<maxa
    return m|small[lab]
def clean(m,ck,mina,maxhole):
    m=cv2.morphologyEx(m.astype(np.uint8),cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(ck,ck))).astype(bool)
    m=fill_holes(m,maxhole)
    m=cv2.morphologyEx(m.astype(np.uint8),cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(3,3))).astype(bool)
    n,lab,st,_=cv2.connectedComponentsWithStats(m.astype(np.uint8)); keep=np.zeros(n,bool); keep[1:]=st[1:,4]>=mina
    return keep[lab]
gold=((h>=7)&(h<=33)&(s>=45)&(v>=85)) | ((h>=7)&(h<=33)&(s>=25)&(v>=200))
# coat regions (sheet px)
reg=(box(0,560,566,900)&~box(296,372,560,720)) | box(150,420,372,566) | box(600,905,612,900) | box(905,1448,612,900) | box(1060,1300,380,612)
reg&=~(box(0,160,360,606)|box(400,560,360,606)|box(640,815,360,604)|box(915,1065,360,606)|box(1295,1448,360,606))
reg&=~box(586,640,560,760)
reg&=~box(250,326,372,566)   # kimono/obi between the edges                       # tassel/obi seen in side view
reg&=~(box(20,165,566,645)|box(395,545,566,645)|box(640,800,566,645)|box(915,1070,566,645)|box(1290,1440,566,645))   # hands/cuffs
reg&=~box(1085,1275,380,838)                     # back motif: measured separately
# exclude the hem band (modelled from geometry): 16 px above the coat bottom per column
lumS=im.mean(2); Fm=np.load('/tmp/w/masks.npz')['fg']
hemx=np.zeros((H,W),bool)
for x in range(W):
    ys=np.nonzero(Fm[640:900,x]&(lumS[640:900,x]>105))[0]
    if len(ys): hemx[640+ys.max()-17:640+ys.max()+3,x]=True
reg&=~cv2.resize(hemx.astype(np.uint8),(W*K,H*K),interpolation=cv2.INTER_NEAREST).astype(bool)
G=clean(gold&reg,5,250,90)
lav=(b>r+4)&(b>g+25)&(lum>128)&(lum<218)
Gd=cv2.dilate(G.astype(np.uint8),np.ones((3,3),np.uint8)).astype(bool)
l2=(lav&reg&box(0,1448,700,900)&~Gd).astype(np.uint8)
l2=cv2.morphologyEx(l2,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(17,17)))
l2=cv2.morphologyEx(l2,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(9,9))).astype(bool)
cloud=l2&~Gd
cloud=clean(cloud,5,1500,400)
Gn=cv2.dilate(G.astype(np.uint8),np.ones((13,13),np.uint8)).astype(bool)
n,lab,st,_=cv2.connectedComponentsWithStats(cloud.astype(np.uint8))
keep=np.zeros(n,bool)
for i in range(1,n):
    m=(lab==i).astype(np.uint8); edge=(m-cv2.erode(m,np.ones((3,3),np.uint8))).astype(bool)
    yc=np.nonzero(m)[0].mean()/K; keep[i]=(Gn[edge].mean()>0.18) and yc>748 and st[i,4]<140000
cloud=keep[lab]
# side view: enclosed cells inside the scroll outlines that are mostly lavender
Gd2=cv2.dilate(G.astype(np.uint8),np.ones((5,5),np.uint8)).astype(bool)
fgK=cv2.resize(np.load('/tmp/w/masks.npz')['fg'].astype(np.uint8),(W*K,H*K),interpolation=cv2.INTER_NEAREST).astype(bool)
free=(fgK&box(640,880,740,860)&~Gd2).astype(np.uint8)
n,lab,st,_=cv2.connectedComponentsWithStats(free,connectivity=4)
for i in range(1,n):
    if 800<st[i,4]<40000:
        m=lab==i
        if lav[m].mean()>0.45: cloud|=m
def polys(m,view_box):
    x0,x1=view_box; sub=np.zeros_like(m); sub[:,x0*K:x1*K]=m[:,x0*K:x1*K]
    cs,hier=cv2.findContours(sub.astype(np.uint8),cv2.RETR_CCOMP,cv2.CHAIN_APPROX_NONE)
    out=[]
    if hier is None: return out
    hier=hier[0]
    for i,c in enumerate(cs):
        if hier[i][3]!=-1 or cv2.contourArea(c)<60: continue
        rings=[c]; j=hier[i][2]
        while j!=-1:
            if cv2.contourArea(cs[j])>=40: rings.append(cs[j])
            j=hier[j][0]
        vs=[];segs=[];holes=[]
        for ri,cc in enumerate(rings):
            a=cv2.approxPolyDP(cc,1.6,True)[:,0,:].astype(float)/K
            if len(a)<3: continue
            base=len(vs); vs+=list(map(tuple,a)); segs+=[(base+k,base+(k+1)%len(a)) for k in range(len(a))]
            if ri>0:
                hm=np.zeros(sub.shape,np.uint8); cv2.drawContours(hm,[cc],-1,1,-1)
                dt=cv2.distanceTransform(hm,cv2.DIST_L2,3); yy,xx=np.unravel_index(np.argmax(dt),dt.shape)
                if dt[yy,xx]>=1: holes.append(((xx+0.5)/K,(yy+0.5)/K))
        t=tri_safe(vs,segs,holes,4.0)
        if t is None or len(t[1])==0: continue
        out.append(t)
    return out
def smooth(m,sg): return cv2.GaussianBlur(m.astype(np.float32),(0,0),sg)>0.5
G=smooth(G,2.2); cloud=smooth(cloud,3.0)&~cv2.dilate(G.astype(np.uint8),np.ones((3,3),np.uint8)).astype(bool)
res={}
for name,m in (('gold',G),('cloud',cloud)):
    res[name]=[]
    for vw,bx in (('F',(0,560)),('S',(560,905)),('B',(905,1448))):
        for t in polys(m,bx): res[name].append((vw,t[0],t[1]))
pickle.dump(res,open('/tmp/w/parts/trim_polys.pkl','wb'))
dbg=(cv2.resize(im,(W*K,H*K))*0.4).astype(np.uint8); dbg[cloud]=(210,150,210); dbg[G]=(0,215,255)
cv2.imwrite('/tmp/w/parts/dbg_trim.png',cv2.resize(dbg[560*K:880*K],(W,320)))
print({k:len(v) for k,v in res.items()})
