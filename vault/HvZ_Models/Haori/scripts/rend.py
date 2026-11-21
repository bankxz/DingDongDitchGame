import bpy,sys,math
from mathutils import Vector
def setup(res=(700,900)):
    sc=bpy.context.scene
    sc.render.engine='BLENDER_WORKBENCH'
    sh=sc.display.shading
    sh.light='STUDIO'; sh.color_type='TEXTURE'; sh.show_cavity=False; sh.show_object_outline=False
    sh.background_type='VIEWPORT'; sh.background_color=(0.62,0.62,0.62)
    sc.render.resolution_x,sc.render.resolution_y=res
    sc.render.image_settings.file_format='PNG'
    sc.view_settings.view_transform='Standard'
    sc.render.film_transparent=False
    for n in ('Circle','Circle.005','Cube','GRAHHH.001','Plane','Armature','Camera'):
        o=bpy.data.objects.get(n)
        if o: o.hide_render=True; o.hide_viewport=True
def shot(path,az,el=0,center=(0,0,2.9),scale=7.0,persp=False,dist=30):
    sc=bpy.context.scene
    cam=bpy.data.objects.get('RCam')
    if not cam:
        cd=bpy.data.cameras.new('RCam'); cam=bpy.data.objects.new('RCam',cd); sc.collection.objects.link(cam)
    sc.camera=cam
    cam.data.type='PERSP' if persp else 'ORTHO'
    cam.data.ortho_scale=scale
    if persp: cam.data.lens=50
    a=math.radians(az); e=math.radians(el)
    # az 0 => camera at -y (back view), 180 => at +y(front)
    d=Vector((math.sin(a)*-1*math.cos(e)*-1, 0,0))
    pos=Vector((math.sin(math.radians(az))*math.cos(e)*-1*-1, -math.cos(math.radians(az))*math.cos(e), math.sin(e)))
    # az=180 => (0, +cos.. ) check below
    pos=Vector((math.sin(a)*math.cos(e), -math.cos(a)*math.cos(e), math.sin(e)))
    cam.location=Vector(center)+pos*dist
    cam.rotation_euler=(-pos).to_track_quat('-Z','Y').to_euler()
    sc.render.filepath=path
    bpy.ops.render.render(write_still=True)
