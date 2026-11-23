import bpy
c=[]
for o in bpy.data.objects:
    if o.type!='MESH' or o.name.split('.')[0] not in ('Houses','PlazaHouses','BackHouses','ClockShop'): continue
    bb=[o.matrix_world@__import__('mathutils').Vector(v) for v in o.bound_box]
    xs=[v.x for v in bb]; ys=[v.y for v in bb]; zs=[v.z for v in bb]
    w,d,h=max(xs)-min(xs),max(ys)-min(ys),max(zs)-min(zs)
    if 0.7<w<2.6 and 0.7<d<2.6 and 0.8<h<5 and min(zs)>18 and abs(w-d)<0.8:
        c.append((round(sum(xs)/8,1),round(sum(ys)/8,1),round(max(zs),1),round(w,1),round(d,1),round(h,1),o.name, tuple(round(x,2) for x in o.color[:3])))
c.sort(key=lambda r:abs(r[1]))
print("CH",len(c))
for r in c[:60]: print("CH",r)
