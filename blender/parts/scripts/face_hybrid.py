import numpy as np, cv2, sys
from PIL import Image, ImageDraw, ImageFilter
sys.argv=['x']
ref=cv2.imread('/tmp/w/ref.png')
X0,Y0,X1,Y1=205,215,372,360
crop=ref[Y0:Y1,X0:X1].copy()
cl=crop.mean(2); b,g,r=[crop[...,i].astype(int) for i in range(3)]; sat=crop.max(2).astype(int)-crop.min(2).astype(int)
# face skin region (sheet px): below the hairline, inside the jaw
yy,xx=np.mgrid[Y0:Y1,X0:X1]
skinish=(r>190)&(r-b>22)&(g>150)
hair=((cl>170)&(sat<60)&~skinish)|((cl>120)&(b>=r-8)&(sat<50)&~skinish&(yy<300))
scar_eye=(xx>300)&(xx<330)
hair&=~((yy>276)&(yy<300)&(xx>237)&(xx<337))      # keep eyes untouched (outer strands still removed)
hair&=~(scar_eye&(b>g+30))
m=cv2.dilate(hair.astype(np.uint8),np.ones((3,3),np.uint8))
clean=cv2.inpaint(crop,m*255,9,cv2.INPAINT_TELEA)
sm=cv2.GaussianBlur(clean,(0,0),1.6)
clean[m>0]=sm[m>0]
# smooth large-scale skin only (keep features): edge-aware
clean=cv2.bilateralFilter(clean,7,18,5)
# ---- map into head texture space, uniform scale
R=1200; SS=3; W=R*SS; K=0.00976*0.86
def sheet_to_world(px,py): return (285.5-px)*K, 4.62+(288-py)*K
def world_to_img(X,Z): return ((0.6-X)/1.2*W,(5.1-Z)/1.2*W)
def P(px,py): return world_to_img(*sheet_to_world(px,py))
ax=W/1.2*K; bx=W/1.2*(0.6-285.5*K)        # img_x = ax*px + bx   (X=(285.5-px)K -> img=(0.6-X)/1.2W)
ay=W/1.2*K; by=W/1.2*(5.1-4.62-288*K)     # img_y = ay*py + by
M=np.float32([[ax,0,ax*X0+bx],[0,ay,ay*Y0+by]])
up=cv2.warpAffine(clean,M,(W,W),flags=cv2.INTER_CUBIC,borderMode=cv2.BORDER_REPLICATE)
SK=np.array([176,206,245],np.float32)
# blend face region into plain skin outside the jaw/hairline
mask=np.zeros(crop.shape[:2],np.float32)
cv2.ellipse(mask,(int(285.5-X0),int(306-Y0)),(int(56),int(46)),0,0,360,1,-1)
mask=cv2.GaussianBlur(mask,(0,0),12)
mw=cv2.warpAffine(mask,M,(W,W),flags=cv2.INTER_LINEAR)[...,None]
skin_mean=np.median(clean[(mask>0.9)&skinish].reshape(-1,3),0)
base=up*mw+skin_mean*(1-mw)
img=Image.fromarray(np.clip(base,0,255).astype(np.uint8)[...,::-1])
# ---- crisp traced linework on top
def bez(pts,n=50):
    pts=[np.array(P(*p)) for p in pts]; out=[]
    for i in range(n+1):
        t=i/n; q=pts[:]
        while len(q)>1: q=[q[j]*(1-t)+q[j+1]*t for j in range(len(q)-1)]
        out.append(q[0])
    return out
def stroke(color,pts,w0,w1,ti=0.2,to=0.3,blur=0.6,alpha=255):
    Pp=bez(pts,60); n=len(Pp); L=[];Rr=[]
    for i,p in enumerate(Pp):
        a=Pp[max(i-1,0)]; c=Pp[min(i+1,n-1)]; t=c-a; t=t/(np.linalg.norm(t)+1e-9); nn=np.array([-t[1],t[0]])
        u=i/(n-1); w=w0+(w1-w0)*u
        if u<ti: w*=0.2+0.8*u/ti
        if u>1-to: w*=max(0.05,(1-u)/to)
        w*=W/1.2*K
        L.append(tuple(p+nn*w/2)); Rr.append(tuple(p-nn*w/2))
    m=Image.new('L',(W,W),0); ImageDraw.Draw(m).polygon(L+Rr[::-1],fill=alpha)
    if blur: m=m.filter(ImageFilter.GaussianBlur(blur*SS))
    img.paste(Image.new('RGB',(W,W),color),(0,0),m)
# ---- crisp linework straight from the sheet: threshold the smooth upscale, then smooth the mask edges (super-resolved shapes)
upc=cv2.warpAffine(crop,M,(W,W),flags=cv2.INTER_CUBIC,borderMode=cv2.BORDER_REPLICATE).astype(np.float32)
ub,ug,ur=upc[...,0],upc[...,1],upc[...,2]; ul=(ub+ug+ur)/3
reg=(mw[...,0]>0.6)
def crisp(maskf,color,sig=1.6,thr=0.5,soft=0.8):
    mm=cv2.GaussianBlur(maskf.astype(np.float32),(0,0),sig*SS)
    a_=np.clip((mm-thr)/0.08+0.5,0,1)
    a_=cv2.GaussianBlur(a_,(0,0),soft*SS)
    im_=Image.fromarray((a_*255).astype(np.uint8))
    img.paste(Image.new('RGB',(W,W),color),(0,0),im_)
def bx(x0,y0,x1,y1):
    a0,b0=P(x0,y0); a1,b1=P(x1,y1); m_=np.zeros((W,W),bool); m_[int(min(b0,b1)):int(max(b0,b1)),int(min(a0,a1)):int(max(a0,a1))]=True; return m_
feat=bx(222,268,280,296)|bx(288,266,347,296)
dark=(ul<92)&feat&~((ub>ug+45)&(ul>55))
crisp(dark,(44,28,44))
mouth=(ul<150)&(ur>ub+12)&reg&(np.arange(W)[:,None]>P(0,322)[1])&(np.arange(W)[:,None]<P(0,334)[1])
crisp(mouth,(120,78,70))
core=(ul>232)&(ub>=ug+6)&bx(305,236,322,348)
crisp(core,(252,232,255),sig=1.2,thr=0.45)
out=img.resize((R,R),Image.LANCZOS); out.save('/tmp/w/parts/face_art.png')
# compare: same framing as the sheet crop
def crop_art():
    x0,y0=P(222,240); x1,y1=P(350,345)
    return out.crop((int(x0/SS),int(y0/SS),int(x1/SS),int(y1/SS)))
a=crop_art().resize((800,656)); rr=Image.open('/tmp/w/ref.png').crop((222,240,350,345)).resize((800,656),Image.LANCZOS)
cmp=Image.new('RGB',(1610,656),(255,255,255)); cmp.paste(rr,(0,0)); cmp.paste(a,(810,0)); cmp.save('/tmp/w/face_prev.png'); print('ok')
