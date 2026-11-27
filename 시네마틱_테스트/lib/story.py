"""불과 물의 마을 — 이야기 전용 소품: 표지판, 하루 방, 다리 밑 벽화, 갈라진 땅, 김, 구름, 낙엽·이끼, 빗방울, 등불, 빛 흐름.
모든 텍스처는 Poly Haven CC0(이미 받은 것) 또는 film/make_art.py 로 직접 그린 그림.
"""
import math
import os
import random

import bpy
from mathutils import Vector

import fx
import look
import mesh as MS
import pbr
import town as TW

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ART = os.path.join(ROOT, "film", "art")
FONT = r"C:\Users\tmd39\Desktop\haru_short\불과물의마을\audio\fonts\Jua-Regular.ttf"


def _img_mat(name, path, rough=0.8, emit=0.0, mix_tex=None, tile=1.0):
    m = pbr.new_mat(name)
    b = pbr.NB(m)
    bs = m.node_tree.nodes["Principled BSDF"]
    tx = b.n("ShaderNodeTexImage")
    tx.image = bpy.data.images.load(path, check_existing=True)
    b.ln(tx.outputs["Color"], bs.inputs["Base Color"])
    bs.inputs["Roughness"].default_value = rough
    if emit:
        b.ln(tx.outputs["Color"], bs.inputs["Emission Color"])
        bs.inputs["Emission Strength"].default_value = emit
    return m


def text_obj(text, size, mat, name, extrude=0.01):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = text
    cu.font = bpy.data.fonts.load(FONT, check_existing=True)
    cu.size = size
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.extrude = extrude
    cu.space_line = 1.05
    ob = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(mat)
    return ob


def sign(center, yaw, text="절대\n건너지 말 것", name="Sign"):
    """나무 표지판 (기둥 2개 + 판). 판 정면 = yaw 방향(0 이면 -Y 를 봄), 뒷면에도 같은 글씨.
    판 크기는 글씨보다 넉넉하게 — 글씨가 잘리거나 가려지지 않게."""
    wood = pbr.tex_mat("Sign_wood", "medieval_wood", 1.0, tint=pbr.srgb(150, 110, 80), var=0.2)
    paint = pbr.flat_mat("Sign_paint", (0.55, 0.03, 0.02), 0.6)
    W, H, T = 1.9, 1.15, 0.08
    mb = MS.MB()
    R = MS.rotz(yaw)
    for sx in (-1, 1):
        mb.box("w", tuple(R @ Vector((sx * (W / 2 - 0.12), 0, 1.0))), (0.12, T - 0.02, 2.0), R)   # 기둥 깊이 < 판 두께: 판 앞으로 튀어나와 글씨를 가리지 않게
    mb.box("w", tuple(R @ Vector((0, 0, 1.65))), (W, T, H), R)
    ob = mb.build(name, {"w": wood}, bevel=0.015)
    ob.location = center
    for k, (dy, rz) in enumerate(((-T / 2 - 0.004, 0.0), (T / 2 + 0.004, math.pi))):
        t = text_obj(text, 0.36, paint, f"{name}_text{k}", extrude=0.004)
        t.rotation_euler = (math.pi / 2, 0, yaw + rz)
        t.location = Vector(center) + R @ Vector((0, dy, 1.65))
    return ob


def steam_mat(name, ratio, density=0.9):
    """뭉게뭉게 피어오르는 김: 원기둥 그릇 안에서 셰이더로 아래 좁고 위 넓은 모양 + 큰 노이즈로 가장자리를 흔듦 (딱딱한 원뿔 X)"""
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = pbr.new_mat(name)
    b = pbr.NB(m)
    for n in list(b.N):
        b.N.remove(n)
    out = b.n("ShaderNodeOutputMaterial")
    tc = b.n("ShaderNodeTexCoord")
    t = fx._time_value(b, 1.0)
    cmb = b.n("ShaderNodeCombineXYZ")
    b.ln(b.math("MULTIPLY", t, -0.9), cmb.inputs["Z"])
    mp = b.n("ShaderNodeMapping")
    b.ln(tc.outputs["Generated"], mp.inputs["Vector"])
    b.ln(cmb.outputs[0], mp.inputs["Location"])
    mp.inputs["Scale"].default_value = (2.2, 2.2, 3.2)
    big = b.n("ShaderNodeTexNoise", i_Scale=1.6, i_Detail=3.0, i_Roughness=0.5)
    b.ln(mp.outputs[0], big.inputs["Vector"])
    fine = b.n("ShaderNodeTexNoise", i_Scale=5.0, i_Detail=8.0, i_Roughness=0.6, i_Distortion=0.6)
    b.ln(mp.outputs[0], fine.inputs["Vector"])
    sep = b.n("ShaderNodeSeparateXYZ")
    b.ln(tc.outputs["Generated"], sep.inputs[0])
    dx = b.math("SUBTRACT", sep.outputs["X"], 0.5)
    dy = b.math("SUBTRACT", sep.outputs["Y"], 0.5)
    rr = b.math("SQRT", b.math("ADD", b.math("MULTIPLY", dx, dx), b.math("MULTIPLY", dy, dy)))
    rr = b.math("ADD", rr, b.math("MULTIPLY", b.math("SUBTRACT", big.outputs["Fac"], 0.5), 0.34))
    zf = sep.outputs["Z"]
    rz = b.math("MULTIPLY", b.math("ADD", ratio, b.math("MULTIPLY", 1.0 - ratio, b.math("POWER", zf, 0.6))), 0.46)
    edge = b.n("ShaderNodeMapRange", clamp=True)
    b.ln(rr, edge.inputs["Value"])
    b.ln(rz, edge.inputs["From Min"])
    b.ln(b.math("MULTIPLY", rz, 0.35), edge.inputs["From Max"])
    top = b.n("ShaderNodeMapRange", i_From_Min=1.0, i_From_Max=0.72, clamp=True)
    b.ln(zf, top.inputs["Value"])
    d0 = b.n("ShaderNodeMapRange", i_From_Min=0.3, i_From_Max=0.7, i_To_Max=density, clamp=True)
    b.ln(fine.outputs["Fac"], d0.inputs["Value"])
    dens = b.math("MULTIPLY", b.math("MULTIPLY", d0.outputs[0], edge.outputs[0]), top.outputs[0])
    pv = b.n("ShaderNodeVolumePrincipled")
    pv.inputs["Color"].default_value = (0.95, 0.95, 0.96, 1)
    pv.inputs["Anisotropy"].default_value = 0.25
    b.ln(dens, pv.inputs["Density"])
    b.ln(pv.outputs[0], out.inputs["Volume"])
    return m


def steam(loc, frame0, frame1, r0=0.6, r1=6.0, h=14.0, name="Steam", density=0.9, frame_hide=None):
    """하얀 김이 확 피어오름: frame0 에 나타나 frame1 까지 커짐 (볼륨). frame_hide 이후 사라짐"""
    ratio = round(max(0.05, min(0.6, r0 / r1)), 2)
    m = steam_mat(f"SteamVol_{ratio}", ratio, density)
    ob = fx.plume(loc, r1, r1, h, m, name, 24)
    for fr, s in ((frame0 - 1, 0.001), (frame0, 0.05), (frame1, 1.0)):
        ob.scale = (s, s, s)
        ob.keyframe_insert("scale", frame=fr)
    if frame_hide:
        ob.hide_render = False
        ob.keyframe_insert("hide_render", frame=frame_hide - 1)
        ob.hide_render = True
        ob.keyframe_insert("hide_render", frame=frame_hide)
    return ob


def cloud(center, size, name="Cloud", density=0.6, seed=0):
    """볼륨 구름 덩어리 (찌그러진 구 여러 개)"""
    m = bpy.data.materials.get("CloudVol") or fx.volume_mat("CloudVol", (0.96, 0.96, 0.97), density=density, scale=0.05, speed=0.15, up=0.05)
    rnd = random.Random(seed)
    obs = []
    for i in range(5):
        mb = MS.MB()
        mb.cyl("v", (0, 0, 0), 1.0, 1.0, 20)
        o = mb.build(f"{name}{i}", {"v": m})
        o.location = Vector(center) + Vector((rnd.uniform(-0.5, 0.5) * size[0], rnd.uniform(-0.5, 0.5) * size[1], rnd.uniform(-0.15, 0.15) * size[2]))
        k = rnd.uniform(0.45, 0.8)
        o.scale = (size[0] * k / 2, size[1] * k / 2, size[2] * k)
        obs.append(o)
    return obs


def crack_ground(center, size, name="Cracks"):
    """갈라진 땅 (보로노이 갈라짐 + 마른 흙 텍스처). 강바닥·강둑 위에 얇게 덮음"""
    m = pbr.tex_mat("CrackMud", "dry_riverbed_rock", 3.0, tint=pbr.srgb(170, 140, 110), var=0.2, bump=0.6)
    b = pbr.NB(m)
    bs = m.node_tree.nodes["Principled BSDF"]
    src = bs.inputs["Base Color"].links[0].from_socket if bs.inputs["Base Color"].links else None
    tc = b.n("ShaderNodeTexCoord")
    vo = b.n("ShaderNodeTexVoronoi", i_Scale=1.3)
    vo.feature = "DISTANCE_TO_EDGE"
    b.ln(tc.outputs["Object"], vo.inputs["Vector"])
    mr = b.n("ShaderNodeMapRange", i_From_Min=0.0, i_From_Max=0.035)
    b.ln(vo.outputs["Distance"], mr.inputs["Value"])
    mix = b.n("ShaderNodeMix", data_type="RGBA")
    mix.inputs["B"].default_value = (0.02, 0.015, 0.01, 1)
    b.ln(mr.outputs[0], mix.inputs["Factor"])
    if src:
        b.ln(src, mix.inputs["B"])
        mix.inputs["A"].default_value = (0.02, 0.015, 0.01, 1)
    b.ln(mix.outputs[2], bs.inputs["Base Color"])
    bp = b.n("ShaderNodeBump", i_Strength=0.9, i_Distance=0.06)
    b.ln(mr.outputs[0], bp.inputs["Height"])
    if bs.inputs["Normal"].links:
        b.ln(bs.inputs["Normal"].links[0].from_socket, bp.inputs["Normal"])
    b.ln(bp.outputs["Normal"], bs.inputs["Normal"])
    me = bpy.data.meshes.new(name)
    sx, sy = size
    me.from_pydata([(-sx / 2, -sy / 2, 0), (sx / 2, -sy / 2, 0), (sx / 2, sy / 2, 0), (-sx / 2, sy / 2, 0)], [], [(0, 1, 2, 3)])
    me.uv_layers.new()
    for i, l in enumerate(me.uv_layers[0].data):
        l.uv = [(0, 0), (sx / 3, 0), (sx / 3, sy / 3), (0, sy / 3)][i]
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = center
    me.materials.append(m)
    return ob


def leaves_moss(V, y, n=900, seed=4):
    """백 년 동안 아무도 안 건넌 다리: 상판 위 낙엽·이끼 조각"""
    rnd = random.Random(seed)
    xc = float(V.river_x(y))
    half = TW.bridge_half(V)
    col = bpy.data.collections.new("LeafVariants")
    TW.lib_collection().children.link(col)
    mats = [pbr.flat_mat("Leaf_a", (0.45, 0.2, 0.05), 0.7), pbr.flat_mat("Leaf_b", (0.55, 0.32, 0.08), 0.7),
            pbr.flat_mat("Moss", (0.05, 0.11, 0.025), 0.95), pbr.flat_mat("Leaf_c", (0.3, 0.12, 0.04), 0.7)]
    for i, m in enumerate(mats):
        mb = MS.MB()
        if m.name == "Moss":                               # 이끼: 작은 울퉁불퉁 덩이 (연잎처럼 보이지 않게)
            r_ = random.Random(i)
            for j in range(5):
                mb.box("m", (r_.uniform(-0.08, 0.08), r_.uniform(-0.08, 0.08), 0.015), (r_.uniform(0.05, 0.11), r_.uniform(0.05, 0.11), 0.03))
        else:
            mb.poly("m", [(-0.06, 0, 0.005), (0, -0.04, 0.012), (0.07, 0, 0.005), (0, 0.04, 0.01)], [(0, 0.5), (0.5, 0), (1, 0.5), (0.5, 1)])
        o = mb.build(f"Leaf{i}", {"m": m}, col)
    pts, scs, rots = [], [], []
    import numpy as np
    for _ in range(n):
        x = xc + rnd.uniform(-half + 1, half - 1)
        yy = y + rnd.gauss(0, 1.6)
        yy = max(y - 3.2, min(y + 3.2, yy))
        if abs(yy - y) < 2.6 and rnd.random() < 0.5:
            yy = y + math.copysign(rnd.uniform(2.2, 3.3), yy - y)        # 난간 쪽에 더 많이 쌓임
        z = TW.deck_z(V, y, x)
        if z is None:
            continue
        pts.append((x, yy, z))
        scs.append(rnd.uniform(0.6, 1.6))
        rots.append(rnd.uniform(0, 6.28))
    return TW.scatter(np.array(pts), col, "BridgeLeaves", np.array(scs), np.array(rots))


def lantern(parent, offset=(0, -0.25, -0.55), energy=60, name="HandLantern"):
    """손에 든 등불 (Poly Haven wooden_lantern_01 + 따뜻한 점광원)"""
    col = TW.load_model("wooden_lantern_01")
    inst = TW.instance(col, (0, 0, 0), 0.0, 0.7, name=name)
    inst.parent = parent
    inst.location = offset
    L = look.point(name + "_L", (0, 0, 0), energy, (1.0, 0.62, 0.3), 0.08)
    L.parent = parent
    L.location = (offset[0], offset[1], offset[2] + 0.2)
    L.data.use_shadow = True
    return inst, L


def droplet(name="Drop"):
    mb = MS.MB()
    mb.cyl("w", (0, 0, 0), 0.05, 0.16, 16, r2=0.005)
    m = bpy.data.materials.get("DropGlass") or pbr.flat_mat("DropGlass", (0.75, 0.9, 1.0), 0.02)
    bs = m.node_tree.nodes["Principled BSDF"]
    bs.inputs["Transmission Weight"].default_value = 1.0
    bs.inputs["IOR"].default_value = 1.33
    return mb.build(name, {"w": m})


def glow_ball(name, color, strength=12.0, r=0.07):
    m = pbr.flat_mat(name + "_m", color, 0.5, emit=color, emit_str=strength)
    mb = MS.MB()
    mb.cyl("g", (0, 0, 0), r, r * 2, 12)
    ob = mb.build(name, {"g": m})
    L = look.point(name + "_L", (0, 0, 0), 8, color, 0.05)
    L.parent = ob
    return ob


def room(center, yaw, name="HaruRoom"):
    """하루 방: 4.2 x 4.2 x 3 m, 정면(-Y, yaw 회전) 벽에 창문, 왼쪽 벽에 액자 2개, 침대·탁자.
    반환: dict(window=창 중심, frames=[액자 중심 2개], floor_z, inward=방 안쪽 방향)"""
    wall = pbr.tex_mat("Room_wall", "clay_plaster", 2.0, tint=pbr.srgb(214, 196, 170), var=0.15, sat=0.4, gain=1.4)
    floor = pbr.tex_mat("Room_floor", "dark_wooden_planks", 1.6, var=0.2)
    wood = pbr.tex_mat("Room_wood", "medieval_wood", 1.0, tint=pbr.srgb(150, 110, 80), var=0.2)
    cloth = pbr.flat_mat("Room_bed", (0.55, 0.62, 0.72), 0.9)
    R = MS.rotz(yaw)
    c = Vector(center)
    P = lambda x, y, z: tuple(c + R @ Vector((x, y, z)))
    mb = MS.MB()
    W, D, H, t = 4.2, 4.2, 3.0, 0.2
    mb.box("f", P(0, 0, -0.1), (W + 2 * t, D + 2 * t, 0.2), R)
    mb.box("w", P(0, 0, H + 0.1), (W + 2 * t, D + 2 * t, 0.2), R)
    mb.box("w", P(0, D / 2 + t / 2, H / 2), (W + 2 * t, t, H), R)                  # 뒷벽
    for sx in (-1, 1):
        mb.box("w", P(sx * (W / 2 + t / 2), 0, H / 2), (t, D, H), R)               # 옆벽
    # 앞벽(창문): 창 1.4 x 1.3, 아래턱 1.0 m
    ww, wh, sill = 1.5, 1.35, 1.0
    yf = -D / 2 - t / 2
    mb.box("w", P(0, yf, sill / 2), (W + 2 * t, t, sill), R)
    mb.box("w", P(0, yf, (sill + wh + H) / 2), (W + 2 * t, t, H - sill - wh), R)
    for sx in (-1, 1):
        sw = (W + 2 * t - ww) / 2
        mb.box("w", P(sx * (ww / 2 + sw / 2), yf, sill + wh / 2), (sw, t, wh), R)
    mb.box("d", P(0, yf - 0.08, sill - 0.04), (ww + 0.2, 0.3, 0.08), R)            # 창턱
    for sx in (-1, 1):
        mb.box("d", P(sx * (ww / 2 + 0.05), yf - 0.02, sill + wh / 2), (0.1, 0.26, wh), R)
    mb.box("d", P(0, yf - 0.02, sill + wh + 0.05), (ww + 0.2, 0.26, 0.1), R)
    # 침대·탁자
    mb.box("d", P(1.3, 1.1, 0.25), (1.2, 2.0, 0.5), R)
    mb.box("b", P(1.3, 1.1, 0.55), (1.15, 1.95, 0.12), R)
    mb.box("d", P(-1.4, -0.9, 0.38), (0.9, 0.7, 0.06), R)
    for sx in (-1, 1):
        for sy in (-1, 1):
            mb.box("d", P(-1.4 + sx * 0.38, -0.9 + sy * 0.28, 0.18), (0.06, 0.06, 0.36), R)
    ob = mb.build(name, {"w": wall, "f": floor, "d": wood, "b": cloth}, bevel=0.01)
    # 액자 2개: 왼쪽 벽(-X) 안쪽 면
    frames = []
    for k, (img, fy) in enumerate((("frame_fire.png", -0.55), ("frame_water.png", 0.55))):
        fm = MS.MB()
        fx_ = -W / 2 + 0.03
        fm.box("d", P(fx_, fy, 1.75), (0.05, 0.7, 0.9), R)
        fo = fm.build(f"{name}_frame{k}", {"d": wood}, bevel=0.01)
        pm = _img_mat(f"FramePic{k}", os.path.join(ART, img), 0.7)
        me = bpy.data.meshes.new(f"{name}_pic{k}")
        q = [P(fx_ + 0.03, fy + 0.29, 1.75 - 0.38), P(fx_ + 0.03, fy - 0.29, 1.75 - 0.38), P(fx_ + 0.03, fy - 0.29, 1.75 + 0.38), P(fx_ + 0.03, fy + 0.29, 1.75 + 0.38)]
        me.from_pydata(q, [], [(0, 1, 2, 3)])
        me.uv_layers.new()
        for i, l in enumerate(me.uv_layers[0].data):
            l.uv = [(0, 0), (1, 0), (1, 1), (0, 1)][i]
        me.materials.append(pm)
        po = bpy.data.objects.new(f"{name}_pic{k}", me)
        bpy.context.scene.collection.objects.link(po)
        frames.append(Vector(P(fx_ + 0.05, fy, 1.75)))
    L = look.point(name + "_lamp", P(0.6, 0.8, 2.6), 160, (1.0, 0.8, 0.6), 0.3)
    return dict(ob=ob, window=Vector(P(0, yf, sill + wh / 2)), frames=frames, floor_z=c.z, inward=R @ Vector((0, 1, 0)),
                P=P)


def mural(V, y, name="Mural"):
    """다리 밑 벽화: 가운데 아치 양쪽 교각 중 불 마을 쪽 교각의 안쪽(+X) 면. 반환: dict(center, normal, w, h, uv(u,v)->월드)"""
    xc = float(V.river_x(y))
    span = V.river_w + 30
    pier = 3.2
    aw = (span - 4 * pier) / 3
    x0 = xc - span / 2
    px = x0 + pier / 2 + 1 * (aw + pier)               # 1번 교각 (가운데 아치의 불 마을 쪽)
    face_x = px + pier / 2 + 0.02
    # 아치가 교각 면에서 바로 시작하므로 (스프링 높이 약 0.3 m) 그 아래 드러난 교각 면에만 그림
    w, h = 5.6, 4.0
    bed = float(V.H(face_x + 1.0, y))
    zc = bed + 0.2 + h / 2
    m = _img_mat("MuralPaint", os.path.join(ART, "mural.png"), 0.85)
    me = bpy.data.meshes.new(name)
    q = [(face_x, y + w / 2, zc - h / 2), (face_x, y - w / 2, zc - h / 2), (face_x, y - w / 2, zc + h / 2), (face_x, y + w / 2, zc + h / 2)]
    me.from_pydata(q, [], [(0, 1, 2, 3)])
    me.uv_layers.new()
    for i, l in enumerate(me.uv_layers[0].data):
        l.uv = [(0, 0), (1, 0), (1, 1), (0, 1)][i]
    me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)

    def at(u, v):                                       # 그림 좌표(u 0~1 왼->오, v 0~1 위->아래) -> 월드
        return Vector((face_x, y + w / 2 - u * w, zc + h / 2 - v * h))
    return dict(ob=ob, center=Vector((face_x, y, zc)), normal=Vector((1, 0, 0)), w=w, h=h, at=at)


def hide_near(prefix, p, r):
    """p 근처(r m) 의 prefix 오브젝트 숨김 (방을 넣을 자리의 집 등)"""
    n = 0
    for o in bpy.data.objects:
        if o.name.startswith(prefix) and (Vector(o.matrix_world.translation[:2]) - Vector(p[:2])).length < r:
            o.hide_render = o.hide_viewport = True
            n += 1
    return n
