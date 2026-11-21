# per-row outer silhouette extremes and per-column hem bottom: reference vs registered model render
import numpy as np,sys
from PIL import Image
TAG=sys.argv[1]
ref=np.array(Image.open('/tmp/w/ref.png').convert('RGB')).astype(int)
F=np.load('/tmp/w/masks.npz')['fg']
W,H,PPS,C=1000,1300,200.0,(0,0,2.9)
def Zm(py): return np.where(py<=632,4+(372-py)/130,(958-py)/163)
for view,x0,x1 in (('F',0,560),('S',560,905),('B',905,1448)):
    R=np.array(Image.open(f'/tmp/w/{TAG}_full{view}.png').convert('RGB')).astype(int)
    bg=np.abs(R-R[3,3]).sum(2)>18
    px=np.arange(x0,x1)
    if view=='F': col=W/2-(280-px)/121*PPS
    elif view=='B': col=W/2+(px-1179.5)/121*PPS
    else: col=W/2-(722-px)/121*PPS
    cc=np.clip(col.round().astype(int),0,W-1)
    print(view)
    for y in range(640,861,20):
        rr=int(np.clip(round(H/2-(Zm(y)-C[2])*PPS),0,H-1))
        m=bg[rr,cc]; r=F[y,x0:x1]
        mi=np.nonzero(m)[0]; ri=np.nonzero(r)[0]
        if len(mi) and len(ri): print(f'  y{y}: ref {ri.min()+x0}-{ri.max()+x0}  model {mi.min()+x0}-{mi.max()+x0}  d {mi.min()-ri.min():+d}/{mi.max()-ri.max():+d}')
    # hem bottom per column
    s=[]
    for x in range(x0+30,x1-30,40):
        c=int(cc[x-x0]); colm=np.nonzero(bg[:,c])[0]
        rf=np.nonzero(F[600:900,x])[0]
        if len(colm) and len(rf):
            zb=C[2]-(colm.max()-H/2)/PPS; yb=958-zb*163
            s.append(f'{x}:{600+rf.max()}/{yb:.0f}')
    print('  hem ref/model',' '.join(s))
