import os, sys, time
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(D, "..", "lib"))
import bpy, math
import look, buildings, pbr, mesh as MS

look.clear_scene()
look.world("kloofendal_48d_partly_cloudy_puresky", 1.0)
look.sun(30, 200, 4.0)
g = pbr.tex_mat("ground", "cobblestone_floor_01", 2.0, var=0.15, bump=0.5, detile=True)
mb = MS.MB(); mb.box("g", (0, 0, -0.05), (60, 60, 0.1)); mb.build("ground", {"g": g})
x = -14
for i, (st, gf) in enumerate((("fire", False), ("fire", True), ("water", True), ("water", False))):
    ob, info = buildings.house(11 + i * 7, st, gable_front=gf, floors=2)
    ob.location = (x, 0, 0)
    x += 8.5
look.camera((4, -24, 4.5), (-3, 0, 5.5), lens=30)
look.preset("EEVEE", "preview", samples=32, res=(1080, 1920), pct=50)
t = time.time()
bpy.context.scene.render.filepath = os.path.join(D, "..", "out", "t_house.png")
bpy.ops.render.render(write_still=True)
print("RENDER", time.time() - t)
