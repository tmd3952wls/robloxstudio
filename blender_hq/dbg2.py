import sys,os,bpy
sys.path.insert(0,os.path.dirname(bpy.data.filepath))
import runtime as RT
from bpy_extras.object_utils import world_to_camera_view as w2c
from mathutils import Vector
sc=bpy.context.scene; sc.frame_set(1170); cam=sc.camera
bp=lambda x,y,z: Vector((x,-z,y))
for x in (-10,-8,-6.5,6.5,8,10):
  for z in (-56,-50,-44,-36):
    a=w2c(sc,cam,bp(x,0.4,z)); b=w2c(sc,cam,bp(x,3,z))
    print("DBG",x,z,round(a.x*1080),round((1-a.y)*1920),round((1-b.y)*1920))
