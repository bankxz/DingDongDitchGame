import cv2,numpy as np
im=cv2.imread('/tmp/w/ref.png'); H,W=im.shape[:2]
b,g,r=[im[...,i].astype(int) for i in range(3)]
lum=(r+g+b)/3; mx=im.max(2).astype(int); mn=im.min(2).astype(int); sat=mx-mn
F=np.load('/tmp/w/masks.npz')['fg']
def box(x0,x1,y0,y1):
    m=np.zeros((H,W),bool); m[y0:y1,x0:x1]=True; return m
def clean(m,k=3,minA=30,op=0):
    m=m.astype(np.uint8)
    if op: m=cv2.morphologyEx(m,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(op,op)))
    m=cv2.morphologyEx(m,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(k,k)))
    n,lab,st,_=cv2.connectedComponentsWithStats(m)
    keep=np.zeros(n,bool); keep[1:]=st[1:,4]>=minA
    return keep[lab]
body=F&(box(0,W,338,H))
excl=box(296,372,560,720)|box(588,642,585,720)|box(0,W,0,338)
cuff=box(0,158,566,612)|box(402,560,566,612)|box(645,815,566,612)|box(905,1065,566,612)|box(1292,W,566,612)
excl|=cuff
gold=(r>135)&(b<0.66*r)&(g>0.58*r)&(g<0.92*r)&(sat>45)
gold=clean(gold&body&~excl,3,25)
glow=(b>190)&(r>140)&(g<190)&(b-g>55)&(lum>150)
glow=clean(glow&body&~excl,3,12)
purple=(b>g+45)&(r>g+15)&(lum<150)&(lum>25)
purpleF=purple&(box(150,410,338,525)|box(0,W,330,380))
purpleF=clean(purpleF&body&~glow,3,40)
cloud=(b>r+4)&(b>g+27)&(sat>=33)&(lum>135)&(lum<215)&~glow
cloud=clean(cloud&body&(box(0,W,726,880)),7,150,op=5)
cg=cv2.morphologyEx((cloud|gold).astype(np.uint8),cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(9,9)))
ff=cg.copy(); mm=np.zeros((H+2,W+2),np.uint8); cv2.floodFill(ff,mm,(0,0),1); holes=(1-ff).astype(bool)&box(0,W,726,880)
cloud=clean((cloud|holes)&body&~gold,5,150)
white=(lum>195)&(sat<40)
white=clean(white&box(226,352,350,520),3,20)
np.savez('/tmp/w/masks3.npz',gold=gold,glow=glow,purple=purpleF,cloud=cloud,white=white)
dbg=(im*0.35).astype(np.uint8)
for m,c in((cloud,(220,160,200)),(purpleF,(160,40,120)),(gold,(40,200,255)),(white,(255,255,255)),(glow,(255,0,255))):
    dbg[m]=c
cv2.imwrite('/tmp/w/dbg_masks3.png',dbg)
