from PIL import Image
ref=Image.open('reference/bone_dragon_reference.webp').convert('RGB')
a=ref.crop((150,40,380,300)).resize((720,814)); b=ref.crop((1024,110,1300,330)).resize((900,717))
def comp(p):
    m=Image.open(p).convert('RGBA'); bg=Image.new('RGBA',m.size,(234,234,236,255)); bg.alpha_composite(m); return bg.convert('RGB')
hf=comp('renders/hf.png').resize((814,814)); hl=comp('renders/hl.png').resize((717,717))
s=Image.new('RGB',(720+814+717+900,830),(255,255,255)); s.paste(a,(0,0)); s.paste(hf,(720,0)); s.paste(b,(1534,0)); s.paste(hl,(2434,0)); s.resize((s.width//2,s.height//2)).save('renders/cmp_head.png')
