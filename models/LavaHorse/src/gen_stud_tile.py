# Generates a seamless Roblox-style "stud" shading tile (grayscale, 0.5 = neutral).
# Studs are painted, not modelled: square face + light top/left bevel + dark bottom/right bevel + soft drop shadow.
import numpy as np, random
from PIL import Image, ImageFilter
N=512; G=4; cell=N//G      # 4x4 studs per tile
random.seed(7)
img=np.full((N,N),0.5,np.float32)
shadow=np.zeros((N,N),np.float32)
missing={(2,1)}          # a few gaps like the reference plates
s=int(cell*0.56); b=max(5,int(s*0.16))
for gy in range(G):
  for gx in range(G):
    if (gx,gy) in missing: continue
    cx=gx*cell+cell//2; cy=gy*cell+cell//2
    x0=cx-s//2; y0=cy-s//2
    shadow[y0+b:y0+s+b+2, x0+b:x0+s+b+2]=1
    img[y0:y0+s, x0:x0+s]=0.6          # stud top slightly lighter
    for i in range(b):                   # bevels
      img[y0+i, x0+i:x0+s-i]=0.95        # top
      img[y0+i:y0+s-i, x0+i]=0.82        # left
      img[y0+s-1-i, x0+i:x0+s-i]=0.12    # bottom
      img[y0+i:y0+s-i, x0+s-1-i]=0.2    # right
sh=Image.fromarray((shadow*255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(4))
sh=np.asarray(sh,np.float32)/255
mask=(img==0.5)
img=np.where(mask, 0.5-0.2*sh, img)
Image.fromarray((np.clip(img,0,1)*255).astype(np.uint8)).save(__import__('os').path.join(__import__('os').path.dirname(__file__), '..', 'textures', 'stud_tile.png'))
print('ok')
