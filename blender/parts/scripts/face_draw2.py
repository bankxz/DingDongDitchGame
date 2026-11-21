from PIL import Image, ImageDraw, ImageFilter, ImageChops
import math, numpy as np
R=1200; SS=3; W=R*SS
SK=(246,208,178)
def P(px,py):
    X=(288.5-px)/123*1.2; Z=3.95+(352-py)/112*1.1
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
layer_paint(base,lambda d:(d.rectangle([0,0,W*0.12,W],fill=255),d.rectangle([W*0.88,0,W,W],fill=255)),(226,172,144),blur=45,alpha=0.8)
for cx in (247,329): layer_paint(base,lambda d,cx=cx:d.ellipse([P(cx-13,312)[0],P(0,309)[1],P(cx+13,312)[0],P(0,320)[1]]),(242,160,148),blur=10,alpha=0.35)
for cx,flip in ((255,1),(320,-1)):
    layer_paint(base,lambda d,cx=cx,f=flip:d.polygon([P(cx-18*f,289),P(cx+16*f,287),P(cx+18*f,292),P(cx-16*f,294)]),(222,166,140),blur=4,alpha=0.55)
layer_paint(base,lambda d:d.polygon([P(286,300),P(289,300),P(291,318),P(285,319)]),(226,170,145),blur=3,alpha=0.6)
layer_paint(base,lambda d:d.ellipse([P(283,317)[0],P(0,316)[1],P(293,317)[0],P(0,320)[1]]),(214,152,128),blur=2,alpha=0.7)
# --- eyes
def eye(cx,f):
    shape=bez([(cx-15*f,299.5),(cx-7*f,292.5),(cx+6*f,291.0),(cx+15*f,293.2),(cx+18*f,297)],30)+bez([(cx+18*f,297),(cx+12*f,300.4),(cx+1*f,301.6),(cx-9*f,301.2),(cx-15*f,299.5)],30)
    m=Image.new('L',(W,W),0); ImageDraw.Draw(m).polygon(shape,fill=255)
    ey=Image.new('RGB',(W,W),(250,246,247)); ed=ImageDraw.Draw(ey)
    ix,iy=P(cx+1.8*f,297.0); r=0.031*W
    # iris radial gradient (light purple bottom -> deep top), glow ring
    for k in range(40,0,-1):
        t=k/40; col=(int(110+70*(1-t)),int(40+60*(1-t)),int(170+60*(1-t)))
        ed.ellipse([ix-r*t,iy-r*1.12*t+r*0.18*(1-t),ix+r*t,iy+r*1.12*t+r*0.18*(1-t)],fill=col)
    ed.ellipse([ix-r*0.38,iy-r*0.42,ix+r*0.38,iy+r*0.42],fill=(30,8,45))
    ed.ellipse([ix-r*0.75,iy-r*0.92,ix-r*0.25,iy-r*0.45],fill=(255,255,255))
    ed.ellipse([ix+r*0.25,iy+r*0.35,ix+r*0.5,iy+r*0.6],fill=(235,215,255))
    sh=Image.new('L',(W,W),0); ImageDraw.Draw(sh).rectangle([0,0,W,P(0,295.2)[1]],fill=150); sh=sh.filter(ImageFilter.GaussianBlur(4*SS))
    ey.paste(Image.new('RGB',(W,W),(120,80,110)),(0,0),sh)
    base.paste(ey,(0,0),m)
    # lid crease, heavy upper lash, outer flick, lower lash
    layer_paint(base,lambda d:stroke(d,[(cx-10*f,290.0),(cx+2*f,287.6),(cx+14*f,289.6)],0.8,0.7,0.3,0.4),(150,96,90),blur=0.6,alpha=0.8)
    layer_paint(base,lambda d:stroke(d,[(cx-16*f,300.2),(cx-7*f,292.0),(cx+7*f,290.4),(cx+19*f,295.6)],2.3,3.5,0.2,0.12),(28,18,34),blur=0.3)
    layer_paint(base,lambda d:stroke(d,[(cx+15*f,293.5),(cx+20*f,294.2),(cx+23*f,297.2)],2.2,0.8,0.0,0.9),(28,18,34),blur=0.3)
    layer_paint(base,lambda d:stroke(d,[(cx+13*f,300.6),(cx+3*f,302.4),(cx-8*f,301.8)],0.7,0.5,0.3,0.5),(95,60,72),blur=0.4,alpha=0.85)
eye(255.5,1); eye(319.5,-1)
# --- brows: thick tapered strokes, angled down toward the centre, with lighter tip strokes
for f,cx in ((1,255),(-1,320)):
    layer_paint(base,lambda d,f=f,cx=cx:stroke(d,[(cx+18*f,288.2),(cx+5*f,283.0),(cx-8*f,280.6),(cx-19*f,283.6)],6.2,3.0,0.12,0.45),(48,34,44),blur=0.4)
    layer_paint(base,lambda d,f=f,cx=cx:stroke(d,[(cx+14*f,286.0),(cx-4*f,281.2),(cx-17*f,282.6)],1.2,0.8,0.2,0.4),(95,70,85),blur=0.3,alpha=0.7)
# --- mouth: firm short line with a soft lower-lip shade
layer_paint(base,lambda d:stroke(d,[(280.5,331.2),(287,330.0),(294.5,330.6)],1.2,1.0,0.3,0.3),(118,66,66),blur=0.4)
layer_paint(base,lambda d:d.ellipse([P(283.5,0)[0],P(0,332.6)[1],P(291.5,0)[0],P(0,335.6)[1]]),(226,160,140),blur=2,alpha=0.6)
# --- scar: soft violet glow + bright core, tapered at both ends, slight angle
layer_paint(base,lambda d:stroke(d,[(323.5,224),(322.4,262),(321.4,300),(320.2,344)],9,7,0.18,0.3),(196,110,238),blur=22,alpha=0.8)
layer_paint(base,lambda d:stroke(d,[(323.5,224),(322.4,262),(321.4,300),(320.2,344)],3.6,2.6,0.2,0.35),(232,170,252),blur=0.8)
layer_paint(base,lambda d:stroke(d,[(323.4,232),(322.4,262),(321.4,300),(320.4,336)],1.2,0.9,0.2,0.35),(255,240,255),blur=0.4)
im=base.resize((R,R),Image.LANCZOS); im.save('/tmp/w/parts/face_art.png'); print('ok')
