import bpy, math, os, sys
from mathutils import Vector
sys.path.insert(0,os.path.dirname(bpy.data.filepath))
sc=bpy.context.scene
w=bpy.data.worlds.new("T"); w.use_nodes=True; sc.world=w
nt=w.node_tree; bg=nt.nodes["Background"]
sky=nt.nodes.new("ShaderNodeTexSky"); sky.sky_type="MULTIPLE_SCATTERING"; sky.sun_disc=False; sky.sun_elevation=math.radians(4)
nt.links.new(sky.outputs[0],bg.inputs[0]); bg.inputs[1].default_value=0.2
d=Vector((-0.7,-0.58,0.0)).normalized()
cam=sc.camera
cam.data.angle=math.radians(60)
cam.location=(0,0,0); cam.rotation_euler=Vector((0,0,-1)).rotation_difference(Vector((d.x,d.y,0.15)).normalized()).to_euler()
# hide everything
for o in bpy.data.objects:
    if o.type!='CAMERA': o.hide_render=True
for h in list(bpy.app.handlers.frame_change_pre): bpy.app.handlers.frame_change_pre.remove(h)
sc.render.resolution_percentage=6; sc.eevee.taa_render_samples=1
sc.view_settings.use_white_balance=False; sc.view_settings.exposure=0
base=math.atan2(d.x,-d.y)
for k,off in enumerate([0,90,180,270]):
    sky.sun_rotation=base+math.radians(off)
    sc.render.filepath=os.path.join(os.path.dirname(bpy.data.filepath),"out",f"sky{off}.png")
    bpy.ops.render.render(write_still=True)
    img=bpy.data.images.load(sc.render.filepath); px=list(img.pixels)
    n=len(px)//4; r=sum(px[0::4])/n; b=sum(px[2::4])/n
    print("SKY",off,round(r,3),round(b,3))
