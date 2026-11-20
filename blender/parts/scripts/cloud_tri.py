import numpy as np, cv2, pickle, os, sys
sys.path.insert(0,'/tmp/w/s3')
import triangle
D=pickle.load(open('/tmp/w/parts/coat_trims.pkl','rb')); cl=D['cloud']
H,W=cl.shape
from tripre import components, prep, tri_safe, grid_fallback
res=[]
for view,(a,b) in (('F',(0,560)),('S',(560,905)),('B',(905,1448))):
    sub=np.zeros_like(cl); sub[:,a:b]=cl[:,a:b]
    for c,holes in components(sub):
        vs,segs,hp=prep(c,holes); t=tri_safe(vs,segs,hp,14) if len(vs)>=3 else None
        if t is None or len(t[1])==0: t=grid_fallback(c,holes)
        res.append((view,t[0],t[1]))
D['cloud_tris']=res; pickle.dump(D,open('/tmp/w/parts/coat_trims.pkl','wb')); print('cloud comps',len(res))
