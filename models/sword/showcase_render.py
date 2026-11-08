"""Studio showcase renders of the exported GLB (what the user receives) with key/fill/rim lights + bloom on the glow."""
import bpy, math, numpy as np, cv2, os, sys
from mathutils import Vector
from PIL import Image
PFX=os.environ.get('PFX','')
S='/tmp/claude-0/-home-user-DingDongDitchGame/25723ca7-107e-59a5-b2ba-96635f274c48/scratchpad/'
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=os.environ['GLB'])
for o in bpy.data.objects:
    if o.type=='MESH' and 'body' in o.name:
        m=o.data.materials[0]; bs=m.node_tree.nodes['Principled BSDF']
        bs.inputs['Metallic'].default_value=0.0; bs.inputs['Roughness'].default_value=0.7; bs.inputs['Specular IOR Level'].default_value=0.15
sc=bpy.context.scene
sc.render.engine='CYCLES'; sc.cycles.device='CPU'; sc.cycles.samples=48; sc.cycles.use_denoising=False
sc.view_settings.view_transform='Standard'
sc.world=bpy.data.worlds.new('w'); sc.world.use_nodes=True
bg=sc.world.node_tree.nodes['Background']; bg.inputs['Color'].default_value=(0.20,0.20,0.21,1); bg.inputs['Strength'].default_value=1.0
def area(name,loc,energy,color,size=1.2):
    l=bpy.data.lights.new(name,'AREA'); l.energy=energy; l.size=size; l.color=color
    o=bpy.data.objects.new(name,l); bpy.context.collection.objects.link(o); o.location=loc
    d=Vector((0,0,0.05))-Vector(loc); o.rotation_euler=d.to_track_quat('-Z','Y').to_euler()
area('key',(1.4,-2.2,1.6),150,(1.0,1.0,1.0),1.8)
area('fill',(-1.8,-1.8,0.4),60,(1.0,1.0,1.0),2.5)
cam=bpy.data.objects.new('cam',bpy.data.cameras.new('cam')); bpy.context.collection.objects.link(cam); sc.camera=cam
def shot(name,loc,tgt,lens,res):
    cam.data.lens=lens; cam.location=loc; d=Vector(tgt)-Vector(loc); cam.rotation_euler=d.to_track_quat('-Z','Y').to_euler()
    sc.render.resolution_x,sc.render.resolution_y=res; sc.render.filepath=S+'raw_'+PFX+name; bpy.ops.render.render(write_still=True)
    im=np.array(Image.open(S+'raw_'+PFX+name).convert('RGB')).astype(np.float32)/255
    red=np.clip((im[...,0]-0.55*np.maximum(im[...,1],im[...,2])-0.25)*2.2,0,1)[...,None]*np.array([1,0.18,0.12])
    bloom=cv2.GaussianBlur(red.astype(np.float32),(0,0),9)*0.9+cv2.GaussianBlur(red.astype(np.float32),(0,0),22)*0.7
    out=np.clip(im+bloom,0,1); Image.fromarray((out*255).astype(np.uint8)).save(S+PFX+name)
shot('sc_full.png',(0.9,-2.3,0.12),(0,0,0.0),55,(700,1100))
shot('sc_34.png',(1.3,-2.0,0.3),(0,0,0.02),55,(700,1100))
shot('sc_back34.png',(-1.3,2.0,0.3),(0,0,0.02),55,(700,1100))
shot('sc_guard.png',(0.8,-1.1,0.02),(0,0,0.0),70,(1000,800))
shot('sc_blade.png',(0.7,-1.5,0.42),(0,0,0.40),70,(800,1000))
