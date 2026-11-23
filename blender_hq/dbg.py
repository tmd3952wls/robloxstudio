import sys,os,bpy
sys.path.insert(0,os.path.dirname(bpy.data.filepath))
import runtime as RT, hq_upgrade as HQ
from bpy_extras.object_utils import world_to_camera_view as w2c
sc=bpy.context.scene
HQ.apply(); sc.frame_set(1240)
cam=sc.camera
dg=bpy.context.evaluated_depsgraph_get()
ob=bpy.data.objects["HQ_Crowd"]
n=sum(1 for i in dg.object_instances if i.is_instance and i.parent and i.parent.original.name=="HQ_Crowd")
print("DBG inst",n,"hide",ob.hide_render,"verts",len(ob.data.vertices))
for v in list(ob.data.vertices)[:13]:
    print("DBG pt",tuple(round(c,1) for c in v.co),tuple(round(c,2) for c in w2c(sc,cam,v.co)))
for nm in ("HQ_Brazier","HQ_Fire","Rich#0" ):
    o=bpy.data.objects.get(nm)
    if o: print("DBG",nm,tuple(round(c,1) for c in o.matrix_world.translation),tuple(round(c,2) for c in w2c(sc,cam,o.matrix_world.translation)))
print("DBG cam",tuple(round(c,1) for c in cam.matrix_world.translation), cam.data.angle)
print("DBG idx",list(ob.data.attributes["inst_idx"].data.values()) if False else [a.value for a in ob.data.attributes["inst_idx"].data][:13])
print("DBG post",[h.__name__ for h in bpy.app.handlers.frame_change_post], "last",RT._S.get("last"), HQ.HQ["ready"])
import traceback
try:
    HQ.hq_frame(sc)
    print("DBG after manual", ob.hide_render, tuple(ob.data.vertices[0].co))
except Exception:
    traceback.print_exc()
