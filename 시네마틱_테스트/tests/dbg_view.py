import os, sys, time
D = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(D, "..", "lib"))
import bpy, look, world_valley
a = sys.argv[sys.argv.index("--") + 1:]
cx, cy, cz, tx, ty, tz, lens = map(float, a[:7]); name = a[7]
look.clear_scene(); info = world_valley.build(a[8] if len(a) > 8 else "lite"); V = info["V"]
look.world("kloofendal_48d_partly_cloudy_puresky", 1.0, rot_deg=40); look.sun(32, 205, 4.5)
xr = float(V.river_x(cy)); look.camera((xr + cx, cy, cz), (float(V.river_x(ty)) + tx, ty, tz), lens=lens)
look.preset("EEVEE", "preview", samples=16, pct=40)
bpy.context.scene.render.filepath = os.path.join(D, "..", "out", name + ".png"); bpy.ops.render.render(write_still=True)
