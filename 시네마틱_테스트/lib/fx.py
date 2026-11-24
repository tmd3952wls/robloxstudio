"""환경 이펙트: 불꽃(화로·횃불), 연기 기둥(볼륨), 화산 분연, 분수, 불티 입자.
무거운 시뮬레이션 대신 셰이더+노이즈 애니메이션 (8GB VRAM 에서 안정적, EEVEE/Cycles 공통).
"""
import math
import random

import bpy
import numpy as np
from mathutils import Matrix, Vector

import mesh as MS
import pbr


def _time_value(b, speed=1.0):
    v = b.n("ShaderNodeValue")
    fc = v.outputs[0].driver_add("default_value")
    fc.driver.expression = f"frame/30*{speed}"
    return v.outputs[0]


def flame_mat(name="Flame", strength=5.0):
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = pbr.new_mat(name)
    m.surface_render_method = "BLENDED" if hasattr(m, "surface_render_method") else None
    b = pbr.NB(m)
    N = b.N
    for n in list(N):
        N.remove(n)
    out = b.n("ShaderNodeOutputMaterial")
    tc = b.n("ShaderNodeTexCoord")
    t = _time_value(b, 1.0)
    mp = b.n("ShaderNodeMapping")
    cmb = b.n("ShaderNodeCombineXYZ")
    b.ln(b.math("MULTIPLY", t, -1.6), cmb.inputs["Z"])
    b.ln(tc.outputs["Object"], mp.inputs["Vector"])
    b.ln(cmb.outputs[0], mp.inputs["Location"])
    mp.inputs["Scale"].default_value = (2.2, 2.2, 1.3)
    nz = b.n("ShaderNodeTexNoise", i_Scale=2.5, i_Detail=4.0, i_Distortion=0.6)
    b.ln(mp.outputs[0], nz.inputs["Vector"])
    sep = b.n("ShaderNodeSeparateXYZ")
    b.ln(tc.outputs["Generated"], sep.inputs[0])
    # 아래는 진하고 위로 갈수록 노이즈로 끊김
    h = sep.outputs["Z"]
    dens = b.math("SUBTRACT", nz.outputs["Fac"], b.math("MULTIPLY", h, 0.75))
    a = b.n("ShaderNodeMapRange", i_From_Min=0.05, i_From_Max=0.35)
    b.ln(dens, a.inputs["Value"])
    bb = b.n("ShaderNodeBlackbody")
    tmp = b.n("ShaderNodeMapRange", i_From_Min=0.0, i_From_Max=1.0, i_To_Min=1900, i_To_Max=1100)
    b.ln(h, tmp.inputs["Value"])
    b.ln(tmp.outputs[0], bb.inputs["Temperature"])
    em = b.n("ShaderNodeEmission", i_Strength=strength)
    b.ln(bb.outputs[0], em.inputs["Color"])
    tr = b.n("ShaderNodeBsdfTransparent")
    mx = b.n("ShaderNodeMixShader")
    b.ln(a.outputs[0], mx.inputs[0])
    b.ln(tr.outputs[0], mx.inputs[1])
    b.ln(em.outputs[0], mx.inputs[2])
    b.ln(mx.outputs[0], out.inputs["Surface"])
    return m


def flame(loc, height=1.2, radius=0.4, name="Flame", n=3, seed=0, light=True, energy=300):
    """교차된 불꽃 판 여러 장 + 흔들리는 점광원"""
    rnd = random.Random(seed)
    mb = MS.MB()
    for i in range(n):
        a = math.pi * i / n
        R = MS.rotz(a)
        w = radius * 2
        pts = [R @ Vector((-w / 2, 0, 0)), R @ Vector((w / 2, 0, 0)), R @ Vector((w * 0.3, 0, height * 0.6)),
               R @ Vector((0, 0, height)), R @ Vector((-w * 0.3, 0, height * 0.6))]
        mb.poly("f", [tuple(p) for p in pts], [(p.x / w + 0.5, p.z / height) for p in [Vector((-w / 2, 0, 0)), Vector((w / 2, 0, 0)), Vector((w * 0.3, 0, height * 0.6)), Vector((0, 0, height)), Vector((-w * 0.3, 0, height * 0.6))]])
    ob = mb.build(name, {"f": flame_mat()})
    ob.location = loc
    ob.visible_shadow = False
    if light:
        import look
        L = look.point(name + "_L", Vector(loc) + Vector((0, 0, height * 0.5)), energy, (1.0, 0.5, 0.18), radius * 0.8)
        fc = L.data.driver_add("energy")
        fc.driver.expression = f"{energy}*(0.85+0.15*sin(frame*0.9+{seed})*sin(frame*0.37+{seed * 2}))"
    return ob


def volume_mat(name, color=(0.25, 0.24, 0.23), density=1.0, scale=0.02, speed=0.3, emission=None, up=1.0):
    m = pbr.new_mat(name)
    b = pbr.NB(m)
    N = b.N
    for n in list(N):
        N.remove(n)
    out = b.n("ShaderNodeOutputMaterial")
    tc = b.n("ShaderNodeTexCoord")
    t = _time_value(b, speed)
    mp = b.n("ShaderNodeMapping")
    cmb = b.n("ShaderNodeCombineXYZ")
    b.ln(b.math("MULTIPLY", t, -up), cmb.inputs["Z"])
    b.ln(tc.outputs["Object"], mp.inputs["Vector"])
    b.ln(cmb.outputs[0], mp.inputs["Location"])
    nz = b.n("ShaderNodeTexNoise", i_Scale=1.0, i_Detail=6.0, i_Roughness=0.6, i_Distortion=0.4)
    mp.inputs["Scale"].default_value = (scale,) * 3
    b.ln(mp.outputs[0], nz.inputs["Vector"])
    # 가장자리로 갈수록 옅게 (Generated 좌표 중심 거리)
    sep = b.n("ShaderNodeSeparateXYZ")
    b.ln(tc.outputs["Generated"], sep.inputs[0])
    dx = b.math("SUBTRACT", sep.outputs["X"], 0.5)
    dy = b.math("SUBTRACT", sep.outputs["Y"], 0.5)
    rr = b.math("SQRT", b.math("ADD", b.math("MULTIPLY", dx, dx), b.math("MULTIPLY", dy, dy)))
    edge = b.n("ShaderNodeMapRange", i_From_Min=0.5, i_From_Max=0.15)
    b.ln(rr, edge.inputs["Value"])
    top = b.n("ShaderNodeMapRange", i_From_Min=1.0, i_From_Max=0.7)
    b.ln(sep.outputs["Z"], top.inputs["Value"])
    d0 = b.n("ShaderNodeMapRange", i_From_Min=0.42, i_From_Max=0.75, i_To_Max=density)
    b.ln(nz.outputs["Fac"], d0.inputs["Value"])
    dens = b.math("MULTIPLY", b.math("MULTIPLY", d0.outputs[0], edge.outputs[0]), top.outputs[0])
    pv = b.n("ShaderNodeVolumePrincipled")
    pv.inputs["Color"].default_value = tuple(color) + (1,)
    pv.inputs["Anisotropy"].default_value = 0.2
    b.ln(dens, pv.inputs["Density"])
    if emission:
        pv.inputs["Emission Color"].default_value = tuple(emission[0]) + (1,)
        bot = b.n("ShaderNodeMapRange", i_From_Min=0.25, i_From_Max=0.0, i_To_Max=emission[1])
        b.ln(sep.outputs["Z"], bot.inputs["Value"])
        b.ln(b.math("MULTIPLY", bot.outputs[0], dens), pv.inputs["Emission Strength"])
    b.ln(pv.outputs[0], out.inputs["Volume"])
    return m


def plume(loc, r0, r1, h, mat, name="Plume", segs=24, lean=(0, 0)):
    """아래 r0 -> 위 r1 로 퍼지는 연기 기둥 메시 (볼륨 그릇)"""
    mb = MS.MB()
    mb.cyl("v", (0, 0, h / 2), r0, h, segs, r2=r1)
    ob = mb.build(name, {"v": mat})
    ob.location = loc
    if lean != (0, 0):
        ob.rotation_euler = (lean[0], lean[1], 0)
    return ob


def volcano_smoke(V):
    vx, vy = V.volcano
    z = float(V.H(vx, vy)) + 20
    m = volume_mat("VolcanoSmoke", (0.16, 0.15, 0.15), density=0.03, scale=0.009, speed=6.0,
                   emission=((1.0, 0.35, 0.08), 0.02), up=1.0)
    plume((vx, vy, z), 160, 650, 2200, m, "VolcanoSmoke", lean=(0.0, math.radians(14)))
    import look
    look.point("CraterGlow", (vx, vy, z + 40), 4.0e7, (1.0, 0.35, 0.1), 60)


def chimney_smoke(pos, i, h=14):
    m = bpy.data.materials.get("ChimneySmoke") or volume_mat("ChimneySmoke", (0.55, 0.53, 0.5), density=0.6, scale=0.25, speed=1.0)
    return plume(pos, 0.35, 2.6, h, m, f"Smoke{i}", 16, lean=(math.radians(random.uniform(8, 18)), 0))


def plaza_fire(c, z):
    """불 마을 광장: 큰 돌 화로 + 불꽃"""
    st = bpy.data.materials.get("fire_stone") or pbr.flat_mat("pf_stone", (0.2, 0.18, 0.16), 0.8)
    mb = MS.MB()
    for i in range(16):
        a = 2 * math.pi * i / 16
        mb.box("s", (math.cos(a) * 2.2, math.sin(a) * 2.2, 0.45), (0.95, 0.75, 0.9), MS.rotz(a))
    mb.box("s", (0, 0, 0.12), (4.2, 4.2, 0.24))
    ob = mb.build("PlazaFirePit", {"s": st}, bevel=0.05)
    ob.location = (c[0], c[1], z)
    flame((c[0], c[1], z + 0.4), 4.0, 1.6, "PlazaFlame", n=5, seed=3, energy=12000)
    return ob


def plaza_fountain(c, z):
    st = bpy.data.materials.get("water_stone") or pbr.flat_mat("pw_stone", (0.6, 0.62, 0.64), 0.7)
    import terrain
    wm = terrain.water_mat("FountainWater", deep=(0.04, 0.12, 0.14), wave_scale=1.5)
    mb = MS.MB()
    for i in range(24):
        a = 2 * math.pi * i / 24
        mb.box("s", (math.cos(a) * 4.0, math.sin(a) * 4.0, 0.4), (1.1, 0.5, 0.8), MS.rotz(a))
    mb.cyl("s", (0, 0, 1.4), 0.5, 2.8, 16)
    mb.cyl("s", (0, 0, 2.9), 1.6, 0.3, 24, r2=1.3)
    mb.cyl("w", (0, 0, 0.6), 3.8, 0.1, 32)
    ob = mb.build("Fountain", {"s": st, "w": wm}, bevel=0.03)
    ob.location = (c[0], c[1], z)
    return ob


def embers(center, n=400, spread=(30, 30, 12), name="Embers", seed=1):
    """불티: 작은 빛나는 점들 (프레임마다 위로 떠오르며 흔들림 — 드라이버 대신 GN 시간 노드)"""
    rng = np.random.default_rng(seed)
    P = rng.uniform(-1, 1, (n, 3)) * np.array(spread) + np.array(center)
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(p) for p in P], [], [])
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ng = bpy.data.node_groups.new(name + "_GN", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, L = ng.nodes, ng.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    m2p = N.new("GeometryNodeMeshToPoints")
    m2p.inputs["Radius"].default_value = 0.025
    sp = N.new("GeometryNodeSetPosition")
    pos = N.new("GeometryNodeInputPosition")
    tm = N.new("GeometryNodeInputSceneTime")
    idx = N.new("GeometryNodeInputIndex")
    rnd = N.new("FunctionNodeRandomValue"); rnd.data_type = "FLOAT"
    L.new(idx.outputs[0], rnd.inputs["ID"])
    # z 오프셋 = (t*속도 + 랜덤) mod 높이
    mul = N.new("ShaderNodeMath"); mul.operation = "MULTIPLY"; mul.inputs[1].default_value = 1.2
    L.new(tm.outputs["Seconds"], mul.inputs[0])
    add = N.new("ShaderNodeMath"); add.operation = "MULTIPLY_ADD"; add.inputs[2].default_value = 0
    L.new(rnd.outputs[0], add.inputs[0]); add.inputs[1].default_value = spread[2] * 2
    L.new(mul.outputs[0], add.inputs[2])
    md_ = N.new("ShaderNodeMath"); md_.operation = "FLOORED_MODULO"; md_.inputs[1].default_value = spread[2] * 2
    L.new(add.outputs[0], md_.inputs[0])
    sx = N.new("ShaderNodeMath"); sx.operation = "SINE"
    L.new(mul.outputs[0], sx.inputs[0])
    cmb = N.new("ShaderNodeCombineXYZ")
    L.new(md_.outputs[0], cmb.inputs["Z"])
    L.new(sx.outputs[0], cmb.inputs["X"])
    sub = N.new("ShaderNodeVectorMath"); sub.operation = "ADD"
    L.new(pos.outputs[0], sub.inputs[0]); L.new(cmb.outputs[0], sub.inputs[1])
    L.new(gi.outputs[0], m2p.inputs["Mesh"])
    L.new(m2p.outputs[0], sp.inputs["Geometry"])
    L.new(sub.outputs[0], sp.inputs["Position"])
    smat = N.new("GeometryNodeSetMaterial")
    smat.inputs["Material"].default_value = pbr.flat_mat("Ember", (0.1, 0.03, 0.0), 0.5, emit=(1.0, 0.28, 0.03), emit_str=30)
    L.new(sp.outputs[0], smat.inputs["Geometry"])
    L.new(smat.outputs[0], go.inputs[0])
    md = ob.modifiers.new("GN", "NODES")
    md.node_group = ng
    return ob
