from PIL import Image, ImageDraw, ImageFilter, ImageChops
import math, numpy as np
R=1200; SS=3; W=R*SS
SK=(246,208,178)
def P(px,py):
    X=(285.5-px)/123*1.2*0.72; Z=4.08+(352-py)/112*0.96
    return ((0.6-X)/1.2*W, (5.1-Z)/1.2*W)
base=Image.new('RGB',(W,W),SK)
def layer_paint(img,fn,color,blur=0,alpha=1.0):
    m=Image.new('L',(W,W),0); fn(ImageDraw.Draw(m))
    if blur: m=m.filter(ImageFilter.GaussianBlur(blur*SS))
    if alpha<1: m=m.point(lambda v:int(v*alpha))
    img.paste(Image.new('RGB',(W,W),color),(0,0),m)
def bez(pts,n=40):
    pts=[np.array(P(*p)) for p in pts]; out=[]
    for i in range(n+1):
        t=i/n; q=pts[:]
        while len(q)>1: q=[q[j]*(1-t)+q[j+1]*t for j in range(len(q)-1)]
        out.append(tuple(q[0]))
    return out
def stroke(d,pts,w0,w1,taper_in=0.25,taper_out=0.35):
    P_=bez(pts,60); n=len(P_)
    L=[];Rr=[]
    for i,p in enumerate(P_):
        a=np.array(P_[max(i-1,0)]); b=np.array(P_[min(i+1,n-1)]); t=b-a; t=t/ (np.linalg.norm(t)+1e-9); nn=np.array([-t[1],t[0]])
        u=i/(n-1); w=w0+(w1-w0)*u
        if u<taper_in: w*=0.25+0.75*(u/taper_in)
        if u>1-taper_out: w*=max(0.05,(1-u)/taper_out)
        w*=SS*9.75
        L.append(tuple(np.array(p)+nn*w/2)); Rr.append(tuple(np.array(p)-nn*w/2))
    d.polygon(L+Rr[::-1],fill=255)
# --- skin shading: side falloff, cheek warmth, under-brow and nose shadow

for cx in (250,320): layer_paint(base,lambda d,cx=cx:d.ellipse([P(cx-13,312)[0],P(0,309)[1],P(cx+13,312)[0],P(0,320)[1]]),(242,160,148),blur=10,alpha=0.35)
layer_paint(base,lambda d:d.polygon([P(286,300),P(289,300),P(291,318),P(285,319)]),(226,170,145),blur=3,alpha=0.6)
layer_paint(base,lambda d:d.ellipse([P(283,317)[0],P(0,316)[1],P(293,317)[0],P(0,320)[1]]),(214,152,128),blur=2,alpha=0.7)
# --- traced eyes (sheet px read from the 6x crop)
def eye(lash,white_low,iris_c,ir,flick,glowing=False):
    shape=bez(lash,30)+bez(white_low,30)
    m=Image.new('L',(W,W),0); ImageDraw.Draw(m).polygon(shape,fill=255)
    ey=Image.new('RGB',(W,W),(244,232,236)); ed=ImageDraw.Draw(ey)
    ix,iy=P(*iris_c); r=ir*9.75*SS
    for k in range(40,0,-1):
        t=k/40
        col=(int(150+80*(1-t)),int(80+90*(1-t)),int(200+45*(1-t))) if glowing else (int(105+70*(1-t)),int(45+55*(1-t)),int(150+60*(1-t)))
        ed.ellipse([ix-r*t,iy-r*1.1*t+r*0.2*(1-t),ix+r*t,iy+r*1.1*t+r*0.2*(1-t)],fill=col)
    if not glowing: ed.ellipse([ix-r*0.36,iy-r*0.4,ix+r*0.36,iy+r*0.4],fill=(45,15,60))
    ed.ellipse([ix-r*0.7,iy-r*0.8,ix-r*0.25,iy-r*0.38],fill=(255,255,255))
    sh=Image.new('L',(W,W),0); ImageDraw.Draw(sh).polygon(bez(lash,30)+[(p[0],p[1]+0.022*W) for p in bez(lash,30)[::-1]],fill=150); sh=sh.filter(ImageFilter.GaussianBlur(5*SS))
    ey.paste(Image.new('RGB',(W,W),(150,105,135)),(0,0),sh)
    base.paste(ey,(0,0),m)
    layer_paint(base,lambda d:stroke(d,lash,2.0,3.2,0.15,0.1),(40,26,44),blur=0.3)
    layer_paint(base,lambda d:stroke(d,flick,2.0,0.6,0.0,0.85),(40,26,44),blur=0.3)
    layer_paint(base,lambda d:stroke(d,white_low,0.7,0.5,0.25,0.3),(120,80,95),blur=0.4,alpha=0.8)
# char-right eye (image left): outer corner at x 231, inner at 270
eye([(230.5,284.5),(238,281.6),(252,281.8),(263,284.2),(270.5,289.0)],[(270.5,289.0),(262,291.4),(248,292.2),(238,291.0),(230.5,284.5)],(255.5,288.8),5.8,[(232,284.2),(227.5,282.4),(224.5,283.6)])
# char-left eye (image right, under the scar)
eye([(338.5,283.8),(331,281.2),(317,281.0),(306,283.0),(292.5,286.6)],[(292.5,286.6),(300,290.6),(314,292.0),(326,290.8),(338.5,283.8)],(313.5,288.8),5.8,[(337,283.4),(341.5,281.8),(344.5,283.0)],glowing=True)
# brows: thick, angled down to the centre (traced)
layer_paint(base,lambda d:stroke(d,[(239,274.6),(250,275.8),(262,279.4),(275,285.4)],4.4,5.6,0.15,0.18),(52,36,50),blur=0.4)
layer_paint(base,lambda d:stroke(d,[(339.5,273.8),(329,274.0),(316,277.0),(292.5,285.0)],4.4,5.6,0.15,0.18),(52,36,50),blur=0.4)
layer_paint(base,lambda d:stroke(d,[(243,274.0),(255,275.6),(266,279.4)],0.7,0.6,0.3,0.4),(110,82,96),blur=0.3,alpha=0.7)
layer_paint(base,lambda d:stroke(d,[(335,273.4),(322,274.6),(305,279.6)],0.7,0.6,0.3,0.4),(110,82,96),blur=0.3,alpha=0.7)
# mouth: slight frown (traced) + lower lip shade
layer_paint(base,lambda d:stroke(d,[(270,329.4),(277,326.8),(284,326.2),(291,326.8),(298.5,329.4)],1.0,1.0,0.2,0.2),(122,78,70),blur=0.4)
layer_paint(base,lambda d:d.ellipse([P(279,0)[0],P(0,332.6)[1],P(288,0)[0],P(0,335.2)[1]]),(222,160,142),blur=3,alpha=0.55)
# scar (traced): x~313, from y 242 to 343, brightest across the eye
layer_paint(base,lambda d:stroke(d,[(314.2,242),(313.6,270),(313.4,292),(312.6,343)],10,8,0.2,0.35),(200,100,240),blur=26,alpha=0.95)
layer_paint(base,lambda d:d.ellipse([P(305,0)[0],P(0,284)[1],P(322,0)[0],P(0,297)[1]]),(240,160,252),blur=16,alpha=0.9)
layer_paint(base,lambda d:stroke(d,[(296,287.5),(313.5,288.6),(332,287.0)],2.2,2.2,0.4,0.4),(250,210,255),blur=4,alpha=0.85)
layer_paint(base,lambda d:stroke(d,[(314.2,242),(313.6,270),(313.4,292),(312.6,343)],2.6,2.0,0.2,0.4),(238,180,252),blur=0.8)
layer_paint(base,lambda d:stroke(d,[(314.1,247),(313.6,270),(313.4,292),(312.8,336)],0.9,0.7,0.2,0.35),(255,244,255),blur=0.4)
im=base.resize((R,R),Image.LANCZOS); im.save('/tmp/w/parts/face_art.png'); print('ok')
