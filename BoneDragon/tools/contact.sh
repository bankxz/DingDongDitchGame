#!/bin/bash
# usage: tools/contact.sh Walk 40 8   -> renders/contact_Walk.png (left + persp34 rows)
cd "$(dirname "$0")/.."; A=$1; N=$2; K=$3; mkdir -p renders/c_$A
for i in $(seq 0 $((K-1))); do f=$((i*N/K)); ACTION=$A FRAME=$f VIEWS=left,persp34 RES=420 SAMPLES=8 python3 tools/render_ref.py BoneDragon.blend renders/c_$A >/dev/null 2>&1; mv renders/c_$A/left.png renders/c_$A/L$i.png; mv renders/c_$A/persp34.png renders/c_$A/P$i.png; done
python3 - <<P
from PIL import Image
K=$K; R=420; s=Image.new('RGB',(R*K//2*1,R*4),(234,234,236))
s=Image.new('RGB',(R*(K//2),R*4),(234,234,236))
for i in range(K):
    for row,pre in ((0,'L'),(1,'P')):
        im=Image.open(f'renders/c_$A/{pre}{i}.png').convert('RGBA'); y=(i//(K//2))*2+row
        s.paste(im,((i%(K//2))*R,y*R),im)
s.save('renders/contact_$A.png')
P
