"""캐릭터 비율 확인: 정면 전신 (팔 윗면 = 어깨선)"""
import os, sys
D = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(D, "..", "lib")); sys.path.insert(0, os.path.join(D, "..", "emotion"))
import bpy, look, pbr, mesh as MS, roblox_char as RC, library as LB
from mathutils import Vector
look.clear_scene(); look.world("kloofendal_48d_partly_cloudy_puresky", 1.0); look.sun(40, 230, 4)
g = pbr.flat_mat("g", (0.3, 0.3, 0.3), 0.8); mb = MS.MB(); mb.box("g", (0, 0, -0.05), (20, 20, 0.1)); mb.build("ground", {"g": g})
for i, (nm, x) in enumerate((("하루", -0.75), ("불주민A", 0.75))):
    c = RC.Char(f"c{i}", nm, (x, 0, 0), 0.0); f, b = LB.target("평온", 1.0, "하루" if i == 0 else "불마을"); b["breath"] = 0; c.pose(b); c.set_face(f)
look.camera((0, -5.2, 0.95), (0, 0, 0.88), lens=50)
look.preset("EEVEE", "preview", samples=16, pct=40)
bpy.context.scene.render.filepath = os.path.join(D, "..", "out", "t_char.png"); bpy.ops.render.render(write_still=True)
