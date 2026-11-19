import cv2,numpy as np
im=cv2.imread('/tmp/w/ref.png'); H,W=im.shape[:2]
bg=np.array([181,179,179])
d=np.abs(im.astype(int)-bg).sum(2)
fg=(d>30).astype(np.uint8)
fg=cv2.morphologyEx(fg,cv2.MORPH_OPEN,np.ones((3,3),np.uint8))
ff=fg.copy(); m=np.zeros((H+2,W+2),np.uint8); cv2.floodFill(ff,m,(0,0),1); fg=fg|(1-ff)
b,g,r=[im[...,i].astype(int) for i in range(3)]
lum=(r+g+b)//3; sat=im.max(2).astype(int)-im.min(2).astype(int)
light=(lum>165)&(sat<45)
skin=(r>195)&(g>140)&(g<215)&(b>100)&(b<185)&(r-b>35)&(r-g>15)
gold=(r>150)&(r-b>70)&(g>95)&(g<r-10)
def box(x0,x1,y0,y1):
    m=np.zeros((H,W),bool); m[y0:y1,x0:x1]=True; return m
def poly(pts):
    m=np.zeros((H,W),np.uint8); cv2.fillPoly(m,[np.array(pts,np.int32)],1); return m.astype(bool)
F=fg.astype(bool)
# ---------- hair cap (front view)
locks=(light&(box(196,252,352,446)|box(322,380,352,442)))
locks=cv2.morphologyEx(locks.astype(np.uint8),cv2.MORPH_OPEN,np.ones((3,3),np.uint8)).astype(bool)
cap=(F&box(0,560,0,352))|locks
cap=cv2.morphologyEx(cap.astype(np.uint8),cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
n,lab,st,_=cv2.connectedComponentsWithStats(cap); k=1+np.argmax(st[1:,4]); cap=(lab==k)
face=skin&box(215,355,240,352)
face=cv2.morphologyEx(face.astype(np.uint8),cv2.MORPH_CLOSE,np.ones((25,25),np.uint8))
face=cv2.morphologyEx(face,cv2.MORPH_OPEN,np.ones((7,7),np.uint8)).astype(bool)&cap
hull=np.zeros((H,W),np.uint8); pts=cv2.findNonZero(face.astype(np.uint8)); cv2.fillConvexPoly(hull,cv2.convexHull(pts),1)
face=(hull.astype(bool))&cap
# ---------- ponytail (side view)
B=[(737,130),(737,168),(784,238),(784,345),(790,352),(790,610),(905,610),(905,130)]
pony=F&poly(B)&box(560,905,0,610)&~box(560,800,352,610)
pony=cv2.morphologyEx(pony.astype(np.uint8),cv2.MORPH_CLOSE,np.ones((7,7),np.uint8))
pony=cv2.morphologyEx(pony,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(7,7)))
n,lab,st,_=cv2.connectedComponentsWithStats(pony); k=1+np.argmax(st[1:,4]); pony=(lab==k)
# side cap profile (hair+head, left of the ponytail boundary)
capside=F&box(560,905,0,352)&~poly(B)
# ---------- tassel (front)
tas=gold&box(304,368,566,712)
tas=cv2.morphologyEx(tas.astype(np.uint8),cv2.MORPH_CLOSE,np.ones((9,9),np.uint8))
n,lab,st,_=cv2.connectedComponentsWithStats(tas); k=1+np.argmax(st[1:,4]); tas=(lab==k)
# ---------- cleaned tile
clean=im.copy()
def inp(mask,rad=5,dil=3):
    global clean
    mk=cv2.dilate(mask.astype(np.uint8),np.ones((dil,dil),np.uint8))
    clean=cv2.inpaint(clean,mk*255,rad,cv2.INPAINT_TELEA)
inp(locks&box(0,560,352,450),4,7)
inp(tas,5,9)
backhair=poly([(1112,346),(1252,346),(1268,400),(1262,470),(1235,535),(1200,520),(1160,480),(1118,455),(1108,400)])
# keep emblem / spine line pixels (gold/purple) that are visible
ys_,xs_=np.nonzero(backhair)
for y in range(ys_.min(),ys_.max()+1):
    xx=np.nonzero(backhair[y])[0]
    if not len(xx): continue
    a,b_=xx.min(),xx.max(); src=clean[y,a-44:a-4].copy(); til=np.concatenate([src[::-1],src]*4)[:b_-a+1]
    clean[y,a:b_+1]=til
sm=cv2.GaussianBlur(clean,(0,0),2.0); edge=cv2.dilate(backhair.astype(np.uint8),np.ones((9,9),np.uint8)).astype(bool)&~cv2.erode(backhair.astype(np.uint8),np.ones((9,9),np.uint8)).astype(bool)
clean[edge]=sm[edge]
hairish=(lum>150)&(sat<70)
sf=box(606,778,232,353)&F&~hairish
sf=cv2.morphologyEx(sf.astype(np.uint8),cv2.MORPH_OPEN,np.ones((3,3),np.uint8)).astype(bool)
sfd=cv2.dilate(sf.astype(np.uint8),np.ones((9,9),np.uint8)).astype(bool)
sfd=cv2.morphologyEx(sfd.astype(np.uint8),cv2.MORPH_CLOSE,np.ones((15,15),np.uint8)).astype(bool)
for x in range(600,780):
    col=np.nonzero(sfd[:,x])[0]
    if not len(col): continue
    y0=col.min(); y1=col.max()
    for k,y in enumerate(range(y0,y1+1)):
        sy=y0-2-k
        while sy<165: sy+= (y0-2-165)
        clean[y,x]=im[sy,x] if F[sy,x] else clean[y0-2,x]
sidearm=skin&box(650,800,596,640)
inp(cv2.dilate(sidearm.astype(np.uint8),np.ones((7,7),np.uint8)).astype(bool),5,3)
# ---------- bg fill (nearest fg colour)
def fill(img):
    inv=(~F).astype(np.uint8)
    er=cv2.erode(F.astype(np.uint8),np.ones((5,5),np.uint8))  # skip dark outline / halo
    dist,labels=cv2.distanceTransformWithLabels(1-er,cv2.DIST_L2,5,labelType=cv2.DIST_LABEL_PIXEL)
    ys,xs=np.nonzero(er); lut=np.zeros((labels.max()+1,3),np.uint8)
    lut[labels[ys,xs]]=img[ys,xs]
    out=img.copy(); out[er==0]=lut[labels[er==0]]
    return out
atlas=np.vstack([fill(im),fill(clean)])
cv2.imwrite('atlas.png',atlas)
np.savez('masks.npz',fg=F,cap=cap,face=face,pony=pony,capside=capside,tas=tas,locks=locks)
dbg=im.copy()
for mk,c in((cap,(0,255,0)),(face,(0,0,255)),(pony,(255,0,0)),(tas,(0,255,255)),(capside,(255,0,255))):
    cnt,_=cv2.findContours(mk.astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE); cv2.drawContours(dbg,cnt,-1,c,1)
cv2.imwrite('dbg_masks.png',dbg[120:720])
cv2.imwrite('dbg_clean.png',clean)
