# trace gold lines on the sleeves from the sheet -> polylines in normalised sleeve coords (u across face, py)
import numpy as np, cv2, pickle, sys
sys.path.insert(0,'/tmp/w/s3')
im=cv2.imread('/tmp/w/ref.png'); H,W=im.shape[:2]
b,g,r=[im[...,i].astype(int) for i in range(3)]; lum=im.mean(2); sat=im.max(2).astype(int)-im.min(2).astype(int)
gold=(r>135)&(b<0.70*r)&(g>0.55*r)&(g<0.93*r)&(sat>40)
F=np.load('/tmp/w/masks.npz')['fg']
from skimage.morphology import skeletonize
def edges_rows(kind):
    rows={}
    for y in range(377,572):
        if kind=='F':  o=np.nonzero(F[y,0:100])[0].min(); i=140+int(np.argmin(lum[y,140:162])); rows[y]=(i,o)       # u=0 inner, 1 outer
        if kind=='B':  o=905+np.nonzero(F[y,905:1000])[0].min(); i=1040+int(np.argmin(lum[y,1040:1064])); rows[y]=(i,o)
        if kind=='S':  rows[y]=(668-(y>500)*(y-500)*6/68, 787+(y>500)*(y-500)*5/68)    # u=0 front, 1 back
    ys=np.array(sorted(rows)); a=np.array([rows[y] for y in ys],float)
    # robust smooth fit (cubic) of each edge vs row -> no lumps
    fit=[]
    for j in range(2):
        c=np.polyfit(ys,a[:,j],3)
        for _ in range(3):
            res=a[:,j]-np.polyval(c,ys); ok=np.abs(res)<2.0*np.std(res)+0.5; c=np.polyfit(ys[ok],a[ok,j],3)
        fit.append(c)
    out={}
    for y in range(370,572):
        yy=min(max(y,377),571); out[y]=(float(np.polyval(fit[0],yy)),float(np.polyval(fit[1],yy)))
    return out
E={k:edges_rows(k) for k in 'FBS'}
def trace(box,kind,ymax=566):
    x0,y0,x1,y1=box
    m=np.zeros((H,W),np.uint8); m[y0:min(y1,ymax),x0:x1]=gold[y0:min(y1,ymax),x0:x1]
    m=cv2.morphologyEx(m,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(5,5)))
    n,lab,st,_=cv2.connectedComponentsWithStats(m); keep=np.zeros(n,bool); keep[1:]=st[1:,4]>=30; m=keep[lab].astype(np.uint8)
    dt=cv2.distanceTransform(m,cv2.DIST_L2,5); sk=skeletonize(m>0)
    P=set(zip(*np.nonzero(sk)))
    def nb(p): y,x=p; return [(y+a,x+c) for a in(-1,0,1) for c in(-1,0,1) if (a or c) and (y+a,x+c) in P]
    deg={p:len(nb(p)) for p in P}; nodes={p for p in P if deg[p]!=2}; used=set(); out=[]
    for s in nodes:
        for q in nb(s):
            e=(min(s,q),max(s,q))
            if e in used: continue
            path=[s,q]; used.add(e); prev,cur=s,q
            while cur not in nodes:
                nx=[t for t in nb(cur) if t!=prev and (min(cur,t),max(cur,t)) not in used]
                if not nx: break
                t=nx[0]; used.add((min(cur,t),max(cur,t))); path.append(t); prev,cur=cur,t
            a=np.array([(x,y) for y,x in path],float)
            L=np.sum(np.linalg.norm(np.diff(a,axis=0),axis=1))
            if L<7: continue
            w=float(np.clip(np.median([dt[y,x] for y,x in path])*2,4,12))
            ap=cv2.approxPolyDP(a.astype(np.float32).reshape(-1,1,2),1.2,False)[:,0,:].astype(float)
            for _ in range(2):
                if len(ap)<3: break
                q=[ap[0]]
                for u_,v_ in zip(ap[:-1],ap[1:]): q+=[0.75*u_+0.25*v_,0.25*u_+0.75*v_]
                q.append(ap[-1]); ap=np.array(q)
            ed=E[kind]; uv=[]
            for x,y in ap:
                yy=int(min(max(round(y),370),571)); i_,o_=ed[yy]; uv.append(((x-i_)/(o_-i_),y))
            out.append((np.array(uv),w/abs(ed[int(min(max(round(ap[:,1].mean()),370),571))][1]-ed[int(min(max(round(ap[:,1].mean()),370),571))][0])))
    return out
res={'F':trace((28,372,160,566),'F'),'B':trace((925,372,1066,566),'B'),'S':trace((664,372,795,566),'S')}
res['edges']=E
pickle.dump(res,open('/tmp/w/parts/sleeve_lines.pkl','wb'))
print({k:len(v) for k,v in res.items() if k!='edges'})
dbg=im.copy()
for k,ox in (('F',0),('B',0),('S',0)):
    for uv,w in res[k]:
        ed=E[k]; pts=[(int(ed[int(y)][0]+u*(ed[int(y)][1]-ed[int(y)][0])),int(y)) for u,y in uv]
        cv2.polylines(dbg,[np.array(pts).reshape(-1,1,2)],False,(255,0,255),2)
cv2.imwrite('/tmp/w/parts/dbg_sleeve_lines.png',np.hstack([dbg[360:580,20:170],dbg[360:580,655:800],dbg[360:580,920:1070]]))
