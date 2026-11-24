"""고퀄리티 시네마틱 업그레이드 (테스트 복사본 전용).
runtime.py 위에 얹어서 쓴다: 재질(PBR), 하늘(HDRI+물리 하늘), 키/림 조명, 대기 원근감(볼륨),
이펙트(굴뚝 연기, 화로 불·연기·불티, 먼지 입자, 물웅덩이), 군중(포즈 메시 재사용 + 인스턴싱 + LOD).
"""
import math
import os
import random

import bpy
from mathutils import Matrix, Vector

import runtime as RT

HQ = {"crowd": [], "parts": [], "ready": False}
HDRI_DIR = os.path.join(os.path.dirname(bpy.app.binary_path), "5.3", "datafiles", "studiolights", "world")


def bpos(x, y, z):
    return Vector((x, -z, y))


# ------------------------------------------------------------------ 노드 도우미
class NB:
    def __init__(self, nt):
        self.nt, self.N, self.L = nt, nt.nodes, nt.links

    def n(self, kind, **kw):
        nd = self.N.new(kind)
        for k, v in kw.items():
            setattr(nd, k, v)
        return nd

    def link(self, a, b):
        self.L.new(a, b)

    @staticmethod
    def sock(node, name, typ=None, out=False):
        lst = node.outputs if out else node.inputs
        for s in lst:
            if s.name == name and (typ is None or s.type == typ) and s.enabled:
                return s
        for s in lst:
            if s.name == name and (typ is None or s.type == typ):
                return s
        raise KeyError(name)

    def val(self, v):
        nd = self.n("ShaderNodeValue")
        nd.outputs[0].default_value = v
        return nd.outputs[0]

    def set_or_link(self, sock, v):
        if isinstance(v, (int, float)):
            sock.default_value = v
        elif isinstance(v, tuple):
            sock.default_value = v
        else:
            self.link(v, sock)

    def math(self, op, a, b=None, clamp=False):
        nd = self.n("ShaderNodeMath", operation=op, use_clamp=clamp)
        self.set_or_link(nd.inputs[0], a)
        if b is not None:
            self.set_or_link(nd.inputs[1], b)
        return nd.outputs[0]

    def mr(self, v, a, b, c=0.0, d=1.0, smooth=False, clamp=True):
        nd = self.n("ShaderNodeMapRange", clamp=clamp)
        if smooth:
            nd.interpolation_type = "SMOOTHSTEP"
        self.set_or_link(nd.inputs["Value"], v)
        nd.inputs["From Min"].default_value, nd.inputs["From Max"].default_value = a, b
        self.set_or_link(nd.inputs["To Min"], c)
        self.set_or_link(nd.inputs["To Max"], d)
        return nd.outputs["Result"]

    def noise(self, vec, scale, detail=4.0, rough=0.5, w=None, dist=0.0):
        nd = self.n("ShaderNodeTexNoise")
        if w is not None:
            nd.noise_dimensions = "4D"
            self.set_or_link(nd.inputs["W"], w)
        self.link(vec, nd.inputs["Vector"])
        nd.inputs["Scale"].default_value = scale
        nd.inputs["Detail"].default_value = detail
        nd.inputs["Roughness"].default_value = rough
        nd.inputs["Distortion"].default_value = dist
        return nd

    def mix(self, fac, a, b, blend="MIX"):
        nd = self.n("ShaderNodeMix", data_type="RGBA", blend_type=blend)
        self.set_or_link(self.sock(nd, "Factor", "VALUE"), fac)
        self.set_or_link(self.sock(nd, "A", "RGBA"), a)
        self.set_or_link(self.sock(nd, "B", "RGBA"), b)
        return self.sock(nd, "Result", "RGBA", out=True)

    def hsv(self, col, h=0.5, s=1.0, v=1.0):
        nd = self.n("ShaderNodeHueSaturation")
        self.set_or_link(nd.inputs["Hue"], h)
        self.set_or_link(nd.inputs["Saturation"], s)
        self.set_or_link(nd.inputs["Value"], v)
        self.set_or_link(nd.inputs["Color"], col)
        return nd.outputs["Color"]

    def vmath(self, op, a, b=None):
        nd = self.n("ShaderNodeVectorMath", operation=op)
        self.set_or_link(nd.inputs[0], a)
        if b is not None:
            self.set_or_link(nd.inputs[1], b)
        return nd.outputs["Value"] if op in ("LENGTH", "DOT_PRODUCT", "DISTANCE") else nd.outputs["Vector"]


# ------------------------------------------------------------------ 1. 재질
def _wrap(mat, kind):
    nt = mat.node_tree
    b = NB(nt)
    bsdf = next((n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None)
    oi = next((n for n in nt.nodes if n.bl_idname == "ShaderNodeObjectInfo"), None)
    if not bsdf or not oi:
        return
    bl = bsdf.inputs["Base Color"].links
    orig = bl[0].from_socket if bl else oi.outputs["Color"]
    col = oi.outputs["Color"]
    for nm in ("Normal", "Roughness", "Base Color"):
        for l in list(bsdf.inputs[nm].links):
            nt.links.remove(l)
    pos = b.n("ShaderNodeNewGeometry").outputs["Position"]
    base, rough, height, bstr, bdist = col, 0.6, None, 0.3, 0.05
    if kind == "cobble":
        v1 = b.n("ShaderNodeTexVoronoi", feature="F1")
        b.link(pos, v1.inputs["Vector"])
        v1.inputs["Scale"].default_value = 1.25
        v1.inputs["Randomness"].default_value = 0.85
        v2 = b.n("ShaderNodeTexVoronoi", feature="DISTANCE_TO_EDGE")
        b.link(pos, v2.inputs["Vector"])
        v2.inputs["Scale"].default_value = 1.25
        v2.inputs["Randomness"].default_value = 0.85
        stone = b.mr(v2.outputs["Distance"], 0.01, 0.08, smooth=True)
        cell = b.math("MULTIPLY", b.mr(v1.outputs["Color"], 0, 1), 1.0)
        fine = b.noise(pos, 7.0, 8.0, 0.62).outputs["Fac"]
        big = b.noise(pos, 0.12, 3.0).outputs["Fac"]
        sc = b.hsv(col, b.mr(cell, 0, 1, 0.48, 0.52), b.mr(cell, 0, 1, 0.8, 1.1), b.mr(cell, 0, 1, 0.72, 1.02))
        sc = b.hsv(sc, 0.5, 1.0, b.mr(fine, 0.3, 0.7, 0.85, 1.08))
        gap = b.hsv(col, 0.5, 0.7, 0.45)
        base = b.mix(stone, gap, sc)
        base = b.hsv(base, 0.5, 1.0, b.mr(big, 0.3, 0.7, 0.82, 1.05))
        pud = b.mr(b.noise(pos, 0.055, 3.0, 0.5).outputs["Fac"], 0.55, 0.585, smooth=True)
        base = b.mix(pud, base, b.hsv(base, 0.5, 1.1, 0.5))
        r_st = b.mr(fine, 0.2, 0.8, 0.52, 0.86)
        r = b.math("ADD", b.math("MULTIPLY", r_st, stone), b.math("MULTIPLY", 0.95, b.math("SUBTRACT", 1.0, stone)))
        rough = b.mr(pud, 0, 1, r, 0.03)
        h = b.math("ADD", b.math("MULTIPLY", stone, 0.7), b.math("MULTIPLY", fine, 0.18))
        height = b.math("MULTIPLY", h, b.math("SUBTRACT", 1.0, pud))
        bstr, bdist = 0.4, 0.05
    elif kind == "brick":
        br = b.n("ShaderNodeTexBrick")
        b.link(pos, br.inputs["Vector"])
        b.link(b.hsv(col, 0.5, 1.0, 0.9), br.inputs["Color1"])
        b.link(b.hsv(col, 0.51, 1.05, 1.1), br.inputs["Color2"])
        b.link(b.mix(0.55, col, (0.78, 0.75, 0.7, 1)), br.inputs["Mortar"])
        br.inputs["Scale"].default_value = 1.0
        br.inputs["Mortar Size"].default_value = 0.03
        br.inputs["Brick Width"].default_value = 1.0
        br.inputs["Row Height"].default_value = 0.4
        fine = b.noise(pos, 9.0, 6.0).outputs["Fac"]
        base = b.hsv(br.outputs["Color"], 0.5, 1.0, b.mr(fine, 0.3, 0.7, 0.9, 1.05))
        rough = b.mr(fine, 0.3, 0.7, 0.78, 0.92)
        height = b.math("ADD", b.math("SUBTRACT", 1.0, br.outputs["Fac"]), b.math("MULTIPLY", fine, 0.25))
        bstr, bdist = 0.6, 0.05
    elif kind == "plaster":
        fine = b.noise(pos, 14.0, 7.0, 0.6).outputs["Fac"]
        stain = b.noise(pos, 0.35, 4.0).outputs["Fac"]
        z = b.n("ShaderNodeSeparateXYZ")
        b.link(pos, z.inputs[0])
        grime = b.mr(z.outputs["Z"], 0.3, 3.0, 0.72, 1.0)
        base = b.hsv(col, 0.5, 1.0, b.math("MULTIPLY", grime, b.mr(stain, 0.3, 0.7, 0.88, 1.04)))
        rough = b.mr(fine, 0.3, 0.7, 0.82, 0.95)
        height, bstr, bdist = fine, 0.18, 0.03
    elif kind == "wood":
        grain = b.noise(pos, 3.0, 9.0, 0.65, dist=2.0).outputs["Fac"]
        base = b.hsv(orig, 0.5, 1.0, b.mr(grain, 0.3, 0.7, 0.94, 1.04))
        rough = b.mr(grain, 0.3, 0.7, 0.55, 0.8)
        height, bstr, bdist = grain, 0.15, 0.02
    elif kind == "slate":
        br = b.n("ShaderNodeTexBrick")
        b.link(pos, br.inputs["Vector"])
        b.link(b.hsv(col, 0.5, 1.0, 0.85), br.inputs["Color1"])
        b.link(b.hsv(col, 0.5, 1.0, 1.1), br.inputs["Color2"])
        b.link(b.hsv(col, 0.5, 1.0, 0.4), br.inputs["Mortar"])
        br.inputs["Scale"].default_value = 0.9
        br.inputs["Mortar Size"].default_value = 0.025
        br.inputs["Row Height"].default_value = 0.5
        fine = b.noise(pos, 6.0, 6.0).outputs["Fac"]
        base = br.outputs["Color"]
        rough = b.mr(fine, 0.3, 0.7, 0.55, 0.8)
        height = b.math("ADD", b.math("SUBTRACT", 1.0, br.outputs["Fac"]), b.math("MULTIPLY", fine, 0.3))
        bstr, bdist = 0.7, 0.06
    elif kind == "metal":
        bsdf.inputs["Metallic"].default_value = 0.85
        fine = b.noise(pos, 5.0, 8.0).outputs["Fac"]
        base = b.hsv(col, 0.5, 1.0, b.mr(fine, 0.3, 0.7, 0.85, 1.05))
        rough = b.mr(fine, 0.3, 0.7, 0.22, 0.5)
        height, bstr, bdist = fine, 0.1, 0.02
    elif kind == "marble":
        wv = b.n("ShaderNodeTexWave")
        b.link(pos, wv.inputs["Vector"])
        wv.inputs["Scale"].default_value = 0.6
        wv.inputs["Distortion"].default_value = 12
        base = b.mix(b.mr(wv.outputs["Fac"], 0.7, 1.0), col, b.hsv(col, 0.5, 0.6, 1.2))
        rough = 0.18
    elif kind == "grass":
        fine = b.noise(pos, 4.0, 6.0).outputs["Fac"]
        big = b.noise(pos, 0.3, 3.0).outputs["Fac"]
        base = b.hsv(col, b.mr(big, 0.3, 0.7, 0.48, 0.53), 1.0, b.mr(fine, 0.3, 0.7, 0.75, 1.15))
        rough, height, bstr, bdist = 0.95, fine, 0.4, 0.04
    elif kind == "sand":
        fine = b.noise(pos, 20.0, 6.0).outputs["Fac"]
        base = b.hsv(col, 0.5, 1.0, b.mr(fine, 0.3, 0.7, 0.92, 1.05))
        rough, height, bstr, bdist = 0.95, fine, 0.2, 0.02
    elif kind == "fabric":
        fine = b.noise(pos, 40.0, 3.0).outputs["Fac"]
        base = orig
        rough, height, bstr, bdist = 0.95, fine, 0.12, 0.01
    elif kind == "plastic":
        big = b.noise(pos, 0.8, 3.0).outputs["Fac"]
        base = orig
        rough = b.mr(big, 0.3, 0.7, 0.38, 0.52)
    elif kind == "char":
        base = orig
        rough = 0.5
        bsdf.inputs["Coat Weight"].default_value = 0.08
    b.link(base, bsdf.inputs["Base Color"])
    if isinstance(rough, float):
        bsdf.inputs["Roughness"].default_value = rough
    else:
        b.link(rough, bsdf.inputs["Roughness"])
    # 블록 모서리를 살짝 둥글게 (Cycles 에서만 보임, EEVEE 는 무시)
    bev = b.n("ShaderNodeBevel")
    bev.inputs["Radius"].default_value = 0.035 if kind == "char" else 0.05
    bev.samples = 6
    nrm = bev.outputs["Normal"]
    if height is not None:
        bump = b.n("ShaderNodeBump")
        bump.inputs["Strength"].default_value = bstr
        bump.inputs["Distance"].default_value = bdist
        b.link(height, bump.inputs["Height"])
        b.link(nrm, bump.inputs["Normal"])
        nrm = bump.outputs["Normal"]
    b.link(nrm, bsdf.inputs["Normal"])


KIND = {"R_Cobblestone": "cobble", "R_Brick": "brick", "R_Plaster": "plaster", "R_Wood": "wood", "R_WoodPlanks": "wood",
        "R_Slate": "slate", "R_Metal": "metal", "R_Marble": "marble", "R_Grass": "grass", "R_Sand": "sand",
        "R_Fabric": "fabric", "R_SmoothPlastic": "plastic", "R_SmoothPlastic_C": "char", "R_Plastic_C": "char",
        "R_Fabric_C": "char", "R_Metal_C": "char"}


def materials():
    for nm, kind in KIND.items():
        m = bpy.data.materials.get(nm)
        if m:
            _wrap(m, kind)


# ------------------------------------------------------------------ 2. 하늘 (물리 하늘 + HDRI 반사광)
SUN_DIR = bpos(-0.7, 0.42, 0.58).normalized()


def world():
    w = bpy.context.scene.world
    b = NB(w.node_tree)
    out = next(n for n in b.N if n.bl_idname == "ShaderNodeOutputWorld")
    old = out.inputs["Surface"].links[0].from_socket
    day = b.N["DAY"].outputs[0]
    sky = b.n("ShaderNodeTexSky", sky_type="MULTIPLE_SCATTERING")
    sky.sun_disc = False
    sky.sun_elevation = math.radians(4.0)          # 하늘만 해질녘 높이로 (따뜻한 지평선)
    sky.sun_rotation = math.atan2(SUN_DIR.x, -SUN_DIR.y) - math.pi / 2   # 실측: 이 값에서 노을이 해 쪽에 옴
    for k, v in (("altitude", 50.0), ("air_density", 1.0), ("aerosol_density", 2.2), ("dust_density", 2.2), ("ozone_density", 1.0)):
        if hasattr(sky, k):
            setattr(sky, k, v)
    bg_cam = b.n("ShaderNodeBackground")
    b.link(sky.outputs["Color"], bg_cam.inputs["Color"])
    bg_cam.inputs["Strength"].default_value = 0.16
    bg_cam.name = "HQ_SkyCam"
    env = b.n("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(os.path.join(HDRI_DIR, "sunset.exr"), check_existing=True)
    tc = b.n("ShaderNodeTexCoord")
    mp = b.n("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (0, 0, sky.sun_rotation + 1.2)
    b.link(tc.outputs["Generated"], mp.inputs["Vector"])
    b.link(mp.outputs["Vector"], env.inputs["Vector"])
    bg_lit = b.n("ShaderNodeBackground")
    b.link(b.mix(0.55, env.outputs["Color"], sky.outputs["Color"]), bg_lit.inputs["Color"])
    bg_lit.inputs["Strength"].default_value = 0.22
    bg_lit.name = "HQ_SkyLit"
    lp = b.n("ShaderNodeLightPath")
    m1 = b.n("ShaderNodeMixShader")
    b.link(lp.outputs["Is Camera Ray"], m1.inputs[0])
    b.link(bg_lit.outputs[0], m1.inputs[1])
    b.link(bg_cam.outputs[0], m1.inputs[2])
    # 카메라에 보이는 하늘은 원래 따뜻한 복숭아빛을 70% 살리고 물리 하늘의 깊이를 30% 섞는다
    mc = b.n("ShaderNodeMixShader")
    mc.inputs[0].default_value = 0.3
    b.link(old, mc.inputs[1])
    b.link(bg_cam.outputs[0], mc.inputs[2])
    m1b = b.n("ShaderNodeMixShader")
    b.link(lp.outputs["Is Camera Ray"], m1b.inputs[0])
    b.link(bg_lit.outputs[0], m1b.inputs[1])
    b.link(mc.outputs[0], m1b.inputs[2])
    m2 = b.n("ShaderNodeMixShader")
    b.link(day, m2.inputs[0])
    b.link(old, m2.inputs[1])
    b.link(m1b.outputs[0], m2.inputs[2])
    b.link(m2.outputs[0], out.inputs["Surface"])


# ------------------------------------------------------------------ 3. 조명: 소프트 키 + 림
def _area(name, size, color):
    ld = bpy.data.lights.new(name, "AREA")
    ld.size, ld.color = size, color
    ld.use_custom_distance, ld.cutoff_distance = True, 30
    ld.volume_factor = 0.0
    ob = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def lights():
    _area("HQ_Key", 6.0, (1.0, 0.95, 0.9))
    _area("HQ_Rim", 2.5, (1.0, 0.82, 0.6))
    bpy.data.objects["CamFill"].data.energy = 70


def _aim(ob, target):
    d = (target - ob.location).normalized()
    ob.rotation_euler = Vector((0, 0, -1)).rotation_difference(d).to_euler()


def _subject():
    cam = bpy.context.scene.camera
    cpos = cam.matrix_world.translation
    fwd = (cam.matrix_world.to_3x3() @ Vector((0, 0, -1))).normalized()
    best, bs = None, 1e9
    for name in RT._S["vis"]:
        info = RT._S["chars"][name]
        hp = bpy.data.objects[info["parts"][info["head"]["idx"]]["ob"]].matrix_world.translation
        v = hp - cpos
        dz = v.dot(fwd)
        if dz <= 0.5:
            continue
        off = (v - fwd * dz).length / dz
        score = off * 3 + dz * 0.05
        if score < bs:
            best, bs = hp, score
    return best


def update_lights(day):
    key, rim = bpy.data.objects["HQ_Key"], bpy.data.objects["HQ_Rim"]
    hp = _subject()
    if hp is None:
        key.data.energy = rim.data.energy = 0
        return
    cam = bpy.context.scene.camera
    cpos = cam.matrix_world.translation
    to_cam = (cpos - hp)
    to_cam.z = 0
    to_cam.normalize()
    side = to_cam.cross(Vector((0, 0, 1)))
    key.location = hp + (to_cam * 0.75 - side * 0.65).normalized() * 7 + Vector((0, 0, 3.5))
    rim.location = hp - to_cam * 4.5 + side * 1.6 + Vector((0, 0, 2.6))
    _aim(key, hp - Vector((0, 0, 0.6)))
    _aim(rim, hp - Vector((0, 0, 1.0)))
    key.data.energy = 900 if day else 90
    key.data.color = (1.0, 0.94, 0.86) if day else (0.75, 0.8, 1.0)
    indoor = hp.x > 300                      # 실내 세트(가게·다락방)는 x 300 너머에 있다
    if indoor:                               # 실내: 림을 가까이 붙이고 벽까지 닿지 않게
        rim.location = hp - to_cam * 1.8 + side * 0.9 + Vector((0, 0, 1.4))
        _aim(rim, hp - Vector((0, 0, 0.6)))
        rim.data.cutoff_distance = 3.5
        key.data.cutoff_distance = 8
    else:
        rim.data.cutoff_distance = 30
        key.data.cutoff_distance = 30
    rim.data.energy = (4200 if day else 1800) * (0.12 if indoor else 1.0)
    rim.data.color = (1.0, 0.8, 0.55) if day else (0.55, 0.7, 1.0)

    sun = bpy.data.objects["Sun"]
    sun.data.angle = math.radians(3.5)


# ------------------------------------------------------------------ 4. 대기 원근감 + 빛줄기 (볼륨)
def _cube(name, size=1.0):
    me = bpy.data.meshes.new(name)
    s = size
    v = [(-s, -s, -s), (s, -s, -s), (s, s, -s), (-s, s, -s), (-s, -s, s), (s, -s, s), (s, s, s), (-s, s, s)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    me.from_pydata(v, [], f)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def _vol_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    b = NB(nt)
    out = b.n("ShaderNodeOutputMaterial")
    pv = b.n("ShaderNodeVolumePrincipled")
    b.link(pv.outputs[0], out.inputs["Volume"])
    t = b.n("ShaderNodeValue")
    t.name = "HQ_TIME"
    return m, b, pv, t.outputs[0]


def atmosphere():
    ob = _cube("HQ_Atmos")
    ob.location = (0, 0, 40)
    ob.scale = (220, 420, 40)
    m, b, pv, _ = _vol_mat("HQ_AtmosVol")
    pos = b.n("ShaderNodeNewGeometry").outputs["Position"]
    z = b.n("ShaderNodeSeparateXYZ")
    b.link(pos, z.inputs[0])
    fall = b.math("EXPONENT", b.math("MULTIPLY", z.outputs["Z"], -1 / 16.0))
    b.link(b.math("MULTIPLY", fall, 0.0011), pv.inputs["Density"])
    pv.inputs["Color"].default_value = (1.0, 0.93, 0.84, 1)
    pv.inputs["Anisotropy"].default_value = 0.55
    ob.data.materials.append(m)
    ob.visible_shadow = False
    # 다락방 안 옅은 먼지 안개: 둥근 창으로 들어오는 달빛이 빛줄기로 보이게
    rm = _cube("HQ_RoomHaze")
    rm.location = bpos(472, 6.5, 2)
    rm.scale = (14, 14, 6.5)
    m2, b2, pv2, _ = _vol_mat("HQ_RoomHazeVol")
    pv2.inputs["Density"].default_value = 0.018
    pv2.inputs["Color"].default_value = (0.8, 0.86, 1.0, 1)
    pv2.inputs["Anisotropy"].default_value = 0.6
    rm.data.materials.append(m2)
    rm.visible_shadow = False


# ------------------------------------------------------------------ 5. 이펙트
def _emit_mat(name, col, strength):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bs = m.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Base Color"].default_value = col
    bs.inputs["Emission Color"].default_value = col
    bs.inputs["Emission Strength"].default_value = strength
    return m


def smoke_column(name, base, height=14.0, width=2.2, density=5.0, color=(0.62, 0.62, 0.64), wind=(1.0, 0.0), speed=0.5):
    ob = _cube(name)
    ob.scale = (width * 1.6, width * 1.6, height / 2)
    ob.location = base + Vector((wind[0] * height * 0.25, wind[1] * height * 0.25, height / 2))
    m, b, pv, T = _vol_mat(name + "_Vol")
    oc = b.n("ShaderNodeTexCoord").outputs["Object"]
    sx = b.n("ShaderNodeSeparateXYZ")
    b.link(oc, sx.inputs[0])
    h = b.mr(sx.outputs["Z"], -1, 1, 0, 1)
    hh = b.math("MULTIPLY", h, h)
    cx = b.math("SUBTRACT", sx.outputs["X"], b.math("MULTIPLY", hh, 0.55 * wind[0] + 1e-4))
    cy = b.math("SUBTRACT", sx.outputs["Y"], b.math("MULTIPLY", hh, 0.55 * wind[1] + 1e-4))
    cv = b.n("ShaderNodeCombineXYZ")
    b.link(cx, cv.inputs[0])
    b.link(cy, cv.inputs[1])
    r = b.math("DIVIDE", b.vmath("LENGTH", cv.outputs[0]), b.math("ADD", 0.12, b.math("MULTIPLY", h, 0.5)))
    radial = b.mr(r, 0.35, 1.0, 1.0, 0.0, smooth=True)
    vert = b.math("MULTIPLY", b.mr(h, 0.0, 0.06, smooth=True), b.mr(h, 0.45, 1.0, 1.0, 0.0, smooth=True))
    mv = b.vmath("ADD", oc, b.vmath("MULTIPLY", (0, 0, -1), b.math("MULTIPLY", T, speed)))
    nz = b.noise(mv, 2.4, 6.0, 0.62, w=b.math("MULTIPLY", T, 0.15))
    dens = b.math("MULTIPLY", b.math("MULTIPLY", b.mr(nz.outputs["Fac"], 0.42, 0.72), radial), vert)
    b.link(b.math("MULTIPLY", dens, density), pv.inputs["Density"])
    pv.inputs["Color"].default_value = color + (1,)
    pv.inputs["Anisotropy"].default_value = 0.25
    ob.data.materials.append(m)
    return ob


def fire(name, base, height=2.4, radius=0.75):
    ob = _cube(name)
    ob.scale = (radius, radius, height / 2)
    ob.location = base + Vector((0, 0, height / 2))
    m, b, pv, T = _vol_mat(name + "_Vol")
    oc = b.n("ShaderNodeTexCoord").outputs["Object"]
    sx = b.n("ShaderNodeSeparateXYZ")
    b.link(oc, sx.inputs[0])
    h = b.mr(sx.outputs["Z"], -1, 1, 0, 1)
    cv = b.n("ShaderNodeCombineXYZ")
    b.link(sx.outputs["X"], cv.inputs[0])
    b.link(sx.outputs["Y"], cv.inputs[1])
    width = b.math("ADD", 0.05, b.math("MULTIPLY", b.math("SUBTRACT", 1.0, h), 0.85))
    r = b.math("DIVIDE", b.vmath("LENGTH", cv.outputs[0]), width)
    core = b.math("MULTIPLY", b.mr(r, 0.15, 1.0, 1.0, 0.0, smooth=True), b.mr(h, 0.15, 1.0, 1.0, 0.0, smooth=True))
    mv = b.vmath("ADD", b.vmath("MULTIPLY", oc, (2.2, 2.2, 1.0)), b.vmath("MULTIPLY", (0, 0, -1), b.math("MULTIPLY", T, 2.6)))
    nz = b.noise(mv, 2.0, 5.0, 0.6, w=T)
    flame = b.math("MULTIPLY", core, b.mr(nz.outputs["Fac"], 0.32, 0.72), clamp=True)
    b.link(b.math("MULTIPLY", flame, 2.5), pv.inputs["Density"])
    pv.inputs["Color"].default_value = (0.05, 0.03, 0.02, 1)
    b.link(b.math("MULTIPLY", flame, 30.0), pv.inputs["Blackbody Intensity"])
    b.link(b.mr(h, 0, 1, 1900, 1150), pv.inputs["Temperature"])
    ob.data.materials.append(m)
    return ob


def flame_cards(name, base, height=1.6, radius=0.55):
    """EEVEE 에서도 또렷한 불꽃: 겹친 원뿔 3개에 아래는 흰노랑, 위는 주황, 위로 갈수록 투명 + 일렁임."""
    import bmesh
    m = bpy.data.materials.new(name + "_Mat")
    m.use_nodes = True
    try:
        m.surface_render_method = "BLENDED"
    except Exception:
        pass
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    b = NB(nt)
    out = b.n("ShaderNodeOutputMaterial")
    oc = b.n("ShaderNodeTexCoord").outputs["Object"]
    sx = b.n("ShaderNodeSeparateXYZ")
    b.link(oc, sx.inputs[0])
    h = b.mr(sx.outputs["Z"], 0, height, 0, 1)
    T = b.n("ShaderNodeValue")
    T.name = "HQ_TIME"
    mv = b.vmath("ADD", b.vmath("MULTIPLY", oc, (3, 3, 1.5)), b.vmath("MULTIPLY", (0, 0, -1), b.math("MULTIPLY", T.outputs[0], 3.0)))
    nz = b.noise(mv, 1.6, 4.0, 0.55, w=T.outputs[0]).outputs["Fac"]
    alpha = b.math("MULTIPLY", b.mr(h, 0.0, 1.0, 1.0, 0.0, smooth=True), b.mr(nz, 0.35, 0.65), clamp=True)
    ramp = b.n("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (1.0, 0.92, 0.55, 1)
    ramp.color_ramp.elements[1].color = (1.0, 0.22, 0.03, 1)
    b.link(h, ramp.inputs[0])
    em = b.n("ShaderNodeEmission")
    b.link(ramp.outputs[0], em.inputs["Color"])
    em.inputs["Strength"].default_value = 14.0
    tr = b.n("ShaderNodeBsdfTransparent")
    mx = b.n("ShaderNodeMixShader")
    b.link(alpha, mx.inputs[0])
    b.link(tr.outputs[0], mx.inputs[1])
    b.link(em.outputs[0], mx.inputs[2])
    b.link(mx.outputs[0], out.inputs["Surface"])
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    for i, (r, hh, dx, dy) in enumerate(((radius, height, 0, 0), (radius * 0.6, height * 0.8, 0.22, 0.1), (radius * 0.55, height * 0.75, -0.18, -0.15))):
        bmesh.ops.create_cone(bm, cap_ends=False, segments=14, radius1=r, radius2=0.02, depth=hh, matrix=Matrix.Translation((dx, dy, hh / 2)))
    bm.to_mesh(me)
    bm.free()
    me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    ob.location = base
    ob.visible_shadow = False
    bpy.context.scene.collection.objects.link(ob)
    return ob


def _points_obj(name, n, radius_rng, mat, seed):
    me = bpy.data.meshes.new(name)
    me.vertices.add(n)
    rnd = random.Random(seed)
    me.attributes.new("rad", "FLOAT", "POINT").data.foreach_set("value", [rnd.uniform(*radius_rng) for _ in range(n)])
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ng = bpy.data.node_groups.new(name + "_GN", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, L = ng.nodes, ng.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    ico = N.new("GeometryNodeMeshIcoSphere")
    ico.inputs["Radius"].default_value = 1.0
    ico.inputs["Subdivisions"].default_value = 1
    iop = N.new("GeometryNodeInstanceOnPoints")
    na = N.new("GeometryNodeInputNamedAttribute")
    na.data_type = "FLOAT"
    na.inputs["Name"].default_value = "rad"
    sm = N.new("GeometryNodeSetMaterial")
    sm.inputs["Material"].default_value = mat
    L.new(gi.outputs[0], iop.inputs["Points"])
    L.new(ico.outputs["Mesh"], iop.inputs["Instance"])
    L.new(na.outputs["Attribute"], iop.inputs["Scale"])
    L.new(iop.outputs["Instances"], sm.inputs["Geometry"])
    L.new(sm.outputs["Geometry"], go.inputs[0])
    ob.modifiers.new("GN", "NODES").node_group = ng
    return ob


def effects_static():
    # 화로 (군밤 장수 화로): 소품 + 불 + 연기 + 불티 + 깜빡이는 불빛
    base = bpos(6.8, 0.4, -42.0)
    metal = bpy.data.materials.get("R_Metal")
    bowl = bpy.data.meshes.new("HQ_Brazier")
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.45, radius2=0.85, depth=0.6,
                          matrix=Matrix.Translation((0, 0, 1.45)))
    for dx, dy in ((0.5, 0), (-0.25, 0.43), (-0.25, -0.43)):
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((dx, dy, 0.6)) @ Matrix.Diagonal((0.1, 0.1, 1.2, 1)))
    bm.to_mesh(bowl)
    bm.free()
    bo = bpy.data.objects.new("HQ_Brazier", bowl)
    bo.location = base
    bo.color = (0.12, 0.11, 0.1, 1)
    bowl.materials.append(metal)
    bpy.context.scene.collection.objects.link(bo)
    coal = bpy.data.meshes.new("HQ_Coal")
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.78, radius2=0.78, depth=0.05, matrix=Matrix.Translation((0, 0, 1.7)))
    bm.to_mesh(coal)
    bm.free()
    co = bpy.data.objects.new("HQ_Coal", coal)
    co.location = base
    coal.materials.append(_emit_mat("HQ_CoalMat", (1.0, 0.25, 0.05, 1), 6.0))
    bpy.context.scene.collection.objects.link(co)
    fire("HQ_Fire", base + Vector((0, 0, 1.68)), 2.2, 0.7)
    flame_cards("HQ_Flame", base + Vector((0, 0, 1.68)))
    smoke_column("HQ_FireSmoke", base + Vector((0, 0, 3.2)), height=9.0, width=1.0, density=2.5, color=(0.45, 0.44, 0.44), wind=(0.6, 0.4), speed=0.9)
    fl = bpy.data.lights.new("HQ_FireLight", "POINT")
    fl.color, fl.shadow_soft_size = (1.0, 0.55, 0.22), 0.4
    fl.use_custom_distance, fl.cutoff_distance = True, 18
    flo = bpy.data.objects.new("HQ_FireLight", fl)
    flo.location = base + Vector((0, 0, 2.4))
    bpy.context.scene.collection.objects.link(flo)
    HQ["fire_base"] = base + Vector((0, 0, 1.7))
    HQ["embers"] = _points_obj("HQ_Embers", 40, (0.012, 0.03), _emit_mat("HQ_EmberMat", (1.0, 0.45, 0.1, 1), 40.0), 7)
    HQ["dust"] = _points_obj("HQ_Dust", 140, (0.004, 0.009), _emit_mat("HQ_DustMat", (1.0, 0.9, 0.75, 1), 0.0), 11)
    rnd = random.Random(3)
    HQ["ember_ph"] = [(rnd.random(), rnd.uniform(0, 6.28), rnd.uniform(0.1, 0.45)) for _ in range(40)]
    HQ["dust_p0"] = [(rnd.uniform(-1, 1), rnd.uniform(0.15, 1), rnd.uniform(-1, 1), rnd.uniform(0, 6.28)) for _ in range(140)]


def chimney_smoke_from_pixel(u, v):
    """현재 카메라에서 화면 좌표(u,v: 0~1, 왼쪽위 기준)로 광선을 쏴 맞은 지붕 블록 위에 연기를 올린다."""
    sc = bpy.context.scene
    cam = sc.camera
    tr, br, bl, tl = [cam.matrix_world @ c for c in cam.data.view_frame(scene=sc)]
    p = tl + (tr - tl) * u + (bl - tl) * v
    o = cam.matrix_world.translation
    dg = bpy.context.evaluated_depsgraph_get()
    dv = (p - o).normalized()
    for _ in range(8):
        hit, loc, nrm, idx, ob, M = sc.ray_cast(dg, o, dv)
        if not hit:
            return None
        if not ob.name.startswith("HQ_"):
            break
        o = loc + dv * 0.05
    bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    top = Vector((sum(c.x for c in bb) / 8, sum(c.y for c in bb) / 8, max(c.z for c in bb)))
    if max(c.x for c in bb) - min(c.x for c in bb) > 3 or max(c.y for c in bb) - min(c.y for c in bb) > 3:
        top = loc.copy()        # 큰 벽에 맞으면 맞은 자리에서 연기
    smoke_column("HQ_ChimneySmoke", top, height=18, width=2.4, density=4.5, color=(0.7, 0.7, 0.72), wind=(-0.8, 0.5), speed=0.6)
    return ob.name, tuple(round(c, 2) for c in top)


def update_effects(T):
    for m in bpy.data.materials:
        if m.name.startswith("HQ_") and m.node_tree and "HQ_TIME" in m.node_tree.nodes:
            m.node_tree.nodes["HQ_TIME"].outputs[0].default_value = T
    fc = bpy.data.objects.get("HQ_Flame")
    if fc:
        fc.scale = (1 + 0.06 * math.sin(T * 13), 1 + 0.06 * math.cos(T * 11), 1 + 0.14 * math.sin(T * 9) + 0.07 * math.sin(T * 23))
    fl = bpy.data.objects.get("HQ_FireLight")
    if fl:
        fl.data.energy = 320 * (0.8 + 0.12 * math.sin(T * 17) + 0.08 * math.sin(T * 31 + 1.3))
        if HQ.get("nofire_now"):
            fl.data.energy = 0.0
    if "embers" in HQ:
        b0 = HQ["fire_base"]
        co = []
        for ph, ang, sp in HQ["ember_ph"]:
            h = (T * (0.35 + sp) + ph) % 1.0
            r = 0.2 + h * 0.9
            co += list(b0 + Vector((math.cos(ang + T * 1.3) * r * 0.6 + h * 1.2, math.sin(ang + T * 0.9) * r * 0.6, h * 5.0)))
        HQ["embers"].data.vertices.foreach_set("co", co)
        HQ["embers"].data.update()
    if "dust" in HQ:
        cam = bpy.context.scene.camera
        M = cam.matrix_world
        co = []
        for x, d, y, ph in HQ["dust_p0"]:
            dist = 2.0 + d * 18.0
            loc = Vector((x * dist * 0.5 + 0.25 * math.sin(T * 0.4 + ph), y * dist * 0.85 + 0.2 * math.cos(T * 0.33 + ph), -dist))
            co += list(M @ loc)
        HQ["dust"].data.vertices.foreach_set("co", co)
        HQ["dust"].data.update()


# ------------------------------------------------------------------ 6. 군중: 포즈 메시 재사용 + 인스턴싱 + LOD
VARIANTS = [("TownB", "기본 미소"), ("TownC", "무표정"), ("TownE", "기본 미소"), ("TownF", "놀람"), ("TownA2", "의심")]
NWALK = 8
POSES = ["walk%d" % i for i in range(NWALK)] + ["idle", "talk", "bow", "point"]
NP = len(POSES)


def _pose_spec(pose, face):
    if pose.startswith("walk"):
        i = int(pose[4:])
        return {"path": [(0, 0, 0, 180), (10, 0, -50, 180)], "y": 0.0, "face": face}, 4.5 * i / NWALK / 5.0
    a = {"x": 0, "z": 0, "yaw": 180, "y": 0.0, "face": face, "acts": []}
    if pose == "talk":
        a["acts"] = [("arm", "R", 45, 15, -1, 0.1, None, 20), ("look", 0, 10, -1, 0)]
        a["face"] = "활짝 웃음"
    elif pose == "bow":
        a["acts"] = [("lean", 18, -1, 0), ("look", 15, 0, -1, 0)]
    elif pose == "point":
        a["acts"] = [("arm", "R", 85, 0, -1, 0.1)]
        a["face"] = "놀람"
    return a, 0.0


def _crowd_mat(src):
    nm = "HQC_" + src.name
    if nm in bpy.data.materials:
        return bpy.data.materials[nm]
    m = src.copy()
    m.name = nm
    nt = m.node_tree
    att = nt.nodes.new("ShaderNodeAttribute")
    att.attribute_type = "GEOMETRY"
    att.attribute_name = "hq_col"
    for n in list(nt.nodes):
        if n.bl_idname == "ShaderNodeObjectInfo":
            for l in list(n.outputs["Color"].links):
                nt.links.new(att.outputs["Color"], l.to_socket)
    return m


def _bake(name, a, t, lod, mesh_name):
    O = bpy.data.objects
    RT._actor(name, a, t, t)
    info = RT._S["chars"][name]
    x, z, yaw, _, _ = RT._path(a, t)
    inv = (Matrix.Translation(bpos(x, 0.0, z)) @ Matrix.Rotation(math.radians(yaw - 180), 4, "Z")).inverted()
    obs = [O[p["ob"]] for p in info["parts"]]
    for lst in info["pool"].values():
        obs += [O[n] for n in lst if not O[n].hide_render]
    verts, faces, mats, cols, mlist = [], [], [], [], []
    for ob in obs:
        if ob.hide_render or ob.type != "MESH":
            continue
        me = ob.data
        M = inv @ ob.matrix_world
        mat = ob.active_material
        if mat is None:
            continue
        cm = _crowd_mat(mat)
        if cm not in mlist:
            mlist.append(cm)
        mi = mlist.index(cm)
        col = tuple(ob.color)
        off = len(verts)
        if lod == 1 and len(me.vertices) > 40:      # 멀리선 복잡한 소품(모자·머리카락)을 상자로
            bb = [M @ Vector(c) for c in ob.bound_box]
            verts += [tuple(v) for v in bb]
            for f in ((0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)):
                faces.append(tuple(off + i for i in f))
                mats.append(mi)
                cols.append(col)
            continue
        verts += [tuple(M @ v.co) for v in me.vertices]
        for p in me.polygons:
            faces.append(tuple(off + i for i in p.vertices))
            mats.append(mi)
            cols.append(col)
    me = bpy.data.meshes.new(mesh_name)
    me.from_pydata(verts, [], faces)
    for m in mlist:
        me.materials.append(m)
    me.polygons.foreach_set("material_index", mats)
    at = me.attributes.new("hq_col", "FLOAT_COLOR", "FACE")
    at.data.foreach_set("color", [c for cc in cols for c in cc])
    me.validate()
    return me, len(faces)


def crowd_library():
    lib = bpy.data.collections.new("HQ_CrowdLib")
    bpy.context.scene.collection.children.link(lib)
    tri = {0: 0, 1: 0}
    for vi, (name, face) in enumerate(VARIANTS):
        for lod in (0, 1):
            for pi, pose in enumerate(POSES):
                a, t = _pose_spec(pose, face)
                idx = (vi * 2 + lod) * NP + pi
                me, nf = _bake(name, a, t, lod, f"HQ_P{idx:03d}")
                tri[lod] += nf
                ob = bpy.data.objects.new(f"HQ_P{idx:03d}", me)
                lib.objects.link(ob)
        RT._hide(name)
        vl = bpy.context.view_layer.layer_collection.children.get("HQ_CrowdLib")
    if vl:
        vl.exclude = True
    HQ["lib_faces"] = tri
    return lib


def crowd_object(lib, n):
    me = bpy.data.meshes.new("HQ_Crowd")
    me.vertices.add(n)
    me.attributes.new("inst_idx", "INT", "POINT")
    me.attributes.new("rot_z", "FLOAT", "POINT")
    ob = bpy.data.objects.new("HQ_Crowd", me)
    bpy.context.scene.collection.objects.link(ob)
    ng = bpy.data.node_groups.new("HQ_CrowdGN", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, L = ng.nodes, ng.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    ci = N.new("GeometryNodeCollectionInfo")
    ci.inputs["Collection"].default_value = lib
    ci.inputs["Separate Children"].default_value = True
    ci.inputs["Reset Children"].default_value = True
    iop = N.new("GeometryNodeInstanceOnPoints")
    iop.inputs["Pick Instance"].default_value = True
    ia = N.new("GeometryNodeInputNamedAttribute")
    ia.data_type = "INT"
    ia.inputs["Name"].default_value = "inst_idx"
    ra = N.new("GeometryNodeInputNamedAttribute")
    ra.data_type = "FLOAT"
    ra.inputs["Name"].default_value = "rot_z"
    cx = N.new("ShaderNodeCombineXYZ")
    e2r = N.new("FunctionNodeEulerToRotation")
    L.new(ra.outputs["Attribute"], cx.inputs["Z"])
    L.new(cx.outputs[0], e2r.inputs[0])
    L.new(gi.outputs[0], iop.inputs["Points"])
    L.new(ci.outputs["Instances"], iop.inputs["Instance"])
    L.new(ia.outputs["Attribute"], iop.inputs["Instance Index"])
    L.new(e2r.outputs[0], iop.inputs["Rotation"])
    L.new(iop.outputs["Instances"], go.inputs[0])
    ob.modifiers.new("GN", "NODES").node_group = ng
    return ob


def _y(x):
    return 0.6 if abs(x) > 11.2 else 0.4


def crowd_shot24():
    """부자 등장 컷: 각자 할 일을 하는 시장 사람들. 부자 주변(가운데 |x|<3, z<-68)은 비워 둔다."""
    C = []
    W = lambda v, x0, z0, x1, z1, sp, ph: C.append({"v": v, "kind": "walk", "p0": (x0, z0), "p1": (x1, z1), "sp": sp, "ph": ph})
    S = lambda v, x, z, yaw, pose: C.append({"v": v, "kind": "still", "x": x, "z": z, "yaw": yaw, "pose": pose})
    W(0, 8.5, -30, 8.5, -62, 4.2, 0.1)      # 카메라 쪽으로 걸어오는 사람
    W(1, -8.5, -66, -8.5, -34, 4.6, 0.5)    # 멀어지는 사람
    W(2, 5.8, -52, 5.8, -22, 4.0, 0.3)
    W(3, -9.6, -26, -9.6, -56, 4.4, 0.7)
    W(4, -9.0, -47, 9.0, -47, 4.0, 0.2)     # 길을 건너는 사람
    S(0, -7.2, -57.5, 135, "talk")          # 수다 떠는 두 사람
    S(2, -5.8, -59.0, -45, "idle")
    S(1, 9.6, -44.5, 220, "idle")
    S(3, 8.3, -46.0, 40, "talk")
    S(4, 12.6, -52, 90, "point")            # 노점 물건을 가리키는 손님
    S(1, -12.6, -40, -90, "idle")           # 노점 구경
    S(2, -3.8, -70.5, 170, "bow")           # 부자에게 고개 숙이는 사람
    S(3, 4.2, -71.0, 195, "idle")
    rnd = random.Random(5)
    for i in range(12):                     # 먼 거리 군중 (LOD1)
        x = rnd.choice([-1, 1]) * rnd.uniform(2.5, 10)
        z = rnd.uniform(-15, 35)
        if rnd.random() < 0.6:
            W(rnd.randrange(5), x, z, x, z + rnd.choice([-1, 1]) * 20, rnd.uniform(3.5, 5), rnd.random())
        else:
            S(rnd.randrange(5), x, z, rnd.uniform(0, 360), rnd.choice(["idle", "talk"]))
    return C


def crowd_shot23():
    """하루가 시장 길을 걷는 컷: 뒤쪽 시장 사람들은 각자 할 일을 한다. 하루 뒤 가운데(|x|<3)는 비워 실루엣을 지킨다."""
    C = []
    W = lambda v, x0, z0, x1, z1, sp, ph: C.append({"v": v, "kind": "walk", "p0": (x0, z0), "p1": (x1, z1), "sp": sp, "ph": ph})
    S = lambda v, x, z, yaw, pose: C.append({"v": v, "kind": "still", "x": x, "z": z, "yaw": yaw, "pose": pose})
    W(0, 9.0, -20, 9.0, -50, 4.2, 0.1)       # 이쪽으로 걸어오는 사람
    W(1, -8.8, -50, -8.8, -18, 4.6, 0.5)     # 멀어지는 사람
    W(2, 5.2, -30, 5.2, 0, 4.0, 0.3)
    W(3, -5.0, -5, -5.0, -35, 4.4, 0.7)
    W(4, -9.0, -26, 9.0, -26, 4.0, 0.2)      # 길을 건너는 사람
    S(0, 9.0, -28.0, 130, "talk")            # 수다 떠는 두 사람
    S(2, 10.4, -26.6, -60, "idle")
    S(1, -12.6, -30, -90, "point")           # 노점 물건을 가리키는 손님
    S(3, -12.4, -33, -90, "idle")            # 노점 구경
    S(4, 12.6, -24, 90, "idle")
    S(2, -7.6, -46, 200, "bow")              # 군밤 화로 옆에서 인사하는 장수
    S(1, -9.6, -40, 200, "point")            # 하루 쪽을 가리키며 수군거림
    rnd = random.Random(5)
    for i in range(12):                      # 먼 거리 군중 (LOD1)
        x = rnd.choice([-1, 1]) * rnd.uniform(3.0, 10)
        z = rnd.uniform(-5, 45)
        if rnd.random() < 0.6:
            W(rnd.randrange(5), x, z, x, z + rnd.choice([-1, 1]) * 20, rnd.uniform(3.5, 5), rnd.random())
        else:
            S(rnd.randrange(5), x, z, rnd.uniform(0, 360), rnd.choice(["idle", "talk"]))
    return C


def crowd_shot4():
    """시장 전경 크레인 컷: 노점 앞 손님, 걷는 사람, 수다 떠는 무리 (위에서 내려다보므로 가운데 길도 써도 된다)."""
    C = []
    W = lambda v, x0, z0, x1, z1, sp, ph: C.append({"v": v, "kind": "walk", "p0": (x0, z0), "p1": (x1, z1), "sp": sp, "ph": ph})
    S = lambda v, x, z, yaw, pose: C.append({"v": v, "kind": "still", "x": x, "z": z, "yaw": yaw, "pose": pose})
    W(0, -2.5, 50, -2.5, -10, 4.2, 0.1)
    W(1, 2.5, -20, 2.5, 45, 4.6, 0.5)
    W(2, -9.0, 20, -9.0, -30, 4.0, 0.3)
    W(3, 9.0, -35, 9.0, 25, 4.4, 0.7)
    W(4, -9.0, 0, 9.0, 0, 4.0, 0.2)
    W(0, 6.0, 55, 6.0, 5, 4.8, 0.4)
    S(1, -12.8, 30, -90, "point")
    S(2, -12.6, 27.5, -90, "idle")
    S(3, -12.8, 4, -90, "talk")
    S(4, 12.8, -12, 90, "point")
    S(0, 12.6, 18, 90, "idle")
    S(2, 4.0, 12, 135, "talk")
    S(1, 5.4, 10.6, -45, "idle")
    S(3, -5.0, -18, 60, "talk")
    S(4, -3.6, -16.8, 240, "idle")
    rnd = random.Random(9)
    for i in range(14):
        x = rnd.choice([-1, 1]) * rnd.uniform(1.5, 10)
        z = rnd.uniform(-90, -30)
        if rnd.random() < 0.6:
            W(rnd.randrange(5), x, z, x, z + rnd.choice([-1, 1]) * 25, rnd.uniform(3.5, 5), rnd.random())
        else:
            S(rnd.randrange(5), x, z, rnd.uniform(0, 360), rnd.choice(["idle", "talk"]))
    return C


def _actor_pts(sh):
    pts = []
    for a in sh["actors"].values():
        if a.get("path"):
            pts += [(k[1], k[2]) for k in a["path"]]
        else:
            pts.append((a.get("x", 0.0), a.get("z", 0.0)))
    return pts


def auto_crowd(sh):
    """컷마다 화면에 보이는 거리 위치를 골라 배경 사람 8~15명(+먼 사람)을 배치.
    규칙: 실내·시계탑 컷 제외, 밤에는 사람들이 모이는 장면(64~78)만, 배우 3.2 이내와
    카메라→배우 시선 앞(옆 2.4 이내)은 비워서 주인공을 가리지 않는다."""
    if not sh.get("cam"):
        return []
    ln = sh["lines"][0]
    keys = sh["cam"]
    _, cp, lp, fov = keys[len(keys) // 2]
    if cp[0] > 300 or abs(cp[2]) > 150 or cp[1] > 40:
        return []
    night = sh.get("light") == "night"
    if night and not (64 <= ln <= 78):
        return []
    rnd = random.Random(ln * 7 + 1)
    fx, fz = lp[0] - cp[0], lp[2] - cp[2]
    L = math.hypot(fx, fz) or 1.0
    fx, fz = fx / L, fz / L
    rx, rz = fz, -fx
    tanh = math.tan(math.radians(fov) / 2) * 1.1
    A = _actor_pts(sh)
    Ad = []
    for ax, az in A:
        vx, vz = ax - cp[0], az - cp[2]
        Ad.append((ax, az, vx * fx + vz * fz, vx * rx + vz * rz))

    def ok(x, z):
        vx, vz = x - cp[0], z - cp[2]
        d, lat = vx * fx + vz * fz, vx * rx + vz * rz
        if d < 5 or d > 110 or abs(lat) > d * tanh:
            return None
        for ax, az, ad, al in Ad:
            if math.hypot(x - ax, z - az) < 3.2:
                return None
            if 0 < d < ad + 2 and abs(lat - al * d / max(ad, 0.1)) < 2.4:
                return None
        return d
    xs = [x * 1.5 for x in range(-7, 8)] + [-13.0, -12.2, 12.2, 13.0]
    cand = []
    for x in xs:
        for zi in range(-98, 99):
            z = zi * 1.5
            d = ok(x + rnd.uniform(-0.4, 0.4), z)
            if d is not None:
                cand.append((x, z, d))
    rnd.shuffle(cand)
    C, used = [], []
    near_n, far_n = (14, 0) if night else (12, 10)
    focal = None
    if night:
        g = sh["actors"].get("Grandma")
        focal = (g.get("x", 0), g.get("z", 0)) if g and not g.get("path") else (sum(p[0] for p in A) / max(len(A), 1), sum(p[1] for p in A) / max(len(A), 1))
    cnt = {"near": 0, "far": 0}
    for x, z, d in cand:
        band = "near" if d < 45 else "far"
        if cnt[band] >= (near_n if band == "near" else far_n):
            continue
        if any(math.hypot(x - ux, z - uz) < 2.6 for ux, uz in used):
            continue
        v = rnd.randrange(len(VARIANTS))
        if night:
            yaw = math.degrees(math.atan2(focal[0] - x, focal[1] - z)) + rnd.uniform(-15, 15)
            C.append({"v": v, "kind": "still", "x": x, "z": z, "yaw": yaw, "pose": rnd.choice(["idle", "idle", "idle", "bow"])})
        elif abs(x) > 11.2:
            C.append({"v": v, "kind": "still", "x": x, "z": z, "yaw": 90 if x > 0 else -90,
                      "pose": rnd.choice(["idle", "point", "talk", "idle"])})
        elif rnd.random() < 0.55:
            z1 = z + rnd.choice([-1, 1]) * rnd.uniform(12, 22)
            if ok(x, z1) is None or ok(x, (z + z1) / 2) is None:
                continue
            C.append({"v": v, "kind": "walk", "p0": (x, z), "p1": (x, z1), "sp": rnd.uniform(3.6, 5.0), "ph": rnd.random()})
        else:
            yaw = rnd.uniform(0, 360)
            C.append({"v": v, "kind": "still", "x": x, "z": z, "yaw": yaw, "pose": "talk"})
            px, pz = x + 1.4 * math.sin(math.radians(yaw)), z + 1.4 * math.cos(math.radians(yaw))
            if ok(px, pz) is not None and not any(math.hypot(px - ux, pz - uz) < 1.2 for ux, uz in used):
                C.append({"v": (v + 2) % len(VARIANTS), "kind": "still", "x": px, "z": pz, "yaw": yaw + 180, "pose": "idle"})
                used.append((px, pz))
        used.append((x, z))
        cnt[band] += 1
    return C


# ------------------------------------------------------------------ 역동 카메라
CROWD_WIDE = {10, 23, 24, 27, 31, 64, 65, 67, 75}   # 사람 많은 컷: 멀리·높이서 시작해 다가감


def _cam_eval(keys, ease, t):
    """runtime._cam 과 같은 보간 (로블록스 좌표)."""
    k0 = k1 = keys[0]
    for i in range(len(keys) - 1):
        if t >= keys[i][0]:
            k0, k1 = keys[i], keys[i + 1]
    if t >= keys[-1][0]:
        k0 = k1 = keys[-1]
    a = 0.0 if k1[0] <= k0[0] else min(max((t - k0[0]) / (k1[0] - k0[0]), 0.0), 1.0)
    if ease == "smooth":
        a = a * a * (3 - 2 * a) * 0.5 + a * 0.5
    elif ease == "out":
        a = 1 - (1 - a) ** 3
    P = Vector(k0[1]).lerp(Vector(k1[1]), a)
    L = Vector(k0[2]).lerp(Vector(k1[2]), a)
    return P, L, k0[3] + (k1[3] - k0[3]) * a


def _ray_block(dg, skip, a, b):
    """로블록스 좌표 a->b 사이에 (사람·안개 제외) 막는 물체가 있으면 a 로부터의 비율, 없으면 None."""
    pa, pb = bpos(*a), bpos(*b)
    d = pb - pa
    L = d.length
    if L < 1e-4:
        return None
    dn = d / L
    o, gone = pa.copy(), 0.0
    for _ in range(12):
        hit, loc, _, _, ob, _ = bpy.context.scene.ray_cast(dg, o, dn, distance=L - gone)
        if not hit:
            return None
        if ob is not None and ob.name in skip:
            step = (loc - o).length + 0.02
            gone += step
            o = o + dn * step
            continue
        return ((loc - pa).length) / L
    return None


def dynamic_cams():
    """모든 컷: 시작은 더 멀리·높이·옆으로 돌아간 곳에서, 원래 구도로 날아 들어오며 끝난다(처음 빠르고 끝에서 느림).
    벽·지붕에 막히거나 다른 배우 몸을 지나가면 움직임 크기를 줄인다."""
    dg = bpy.context.evaluated_depsgraph_get()
    skip = {o.name for o in bpy.data.objects if o.name.startswith("HQ_")}
    for info in RT._S["chars"].values():
        skip |= {p["ob"] for p in info["parts"]}
        for lst in info["pool"].values():
            skip |= set(lst)
        skip.add(info["num"])
    rep = []
    for si, sh in enumerate(RT._S["shots"]):
        keys = sh.get("cam")
        if not keys or len(keys) > 8 or sh.get("nodyn"):
            continue
        ln = sh["lines"][0]
        dur = sh["dur"]
        ease = sh.get("ease", "smooth")
        P0, L0, _ = _cam_eval(keys, ease, 0.0)
        P1, _, _ = _cam_eval(keys, ease, dur)
        v0 = P0 - L0
        dist = v0.length
        interior = L0.x > 300
        if ln in CROWD_WIDE:
            K, TH, H, W = 2.6, 8.0, 3.5, 1.8
        elif interior:
            K, TH, H, W = 0.8, 0.0, 0.0, 2.0      # 실내: 벽 밖으로 나가지 않게 가까이서 시작해 살짝 돌며 물러남
        elif dist < 3.6:
            K, TH, H, W = 1.9, 24.0, 0.3, 2.4
        else:
            K, TH, H, W = 1.7, 18.0, 1.2, 2.2
        st = min(1.0, max(0.45, dur / 1.6))
        if P0.y > 12 and not interior:          # 이미 높은 크레인 컷은 높이·거리 덜
            K, H = 1 + (K - 1) * 0.4, 0.0
        if (P1 - P0).length > 0.5 * dist:          # 이미 크게 움직이는 컷은 절반만
            st *= 0.5
        sgn = 1 if si % 2 == 0 else -1
        A = _actor_pts(sh)

        def path(f):
            out = []
            n = max(2, int(round(dur * 30)))
            for i in range(n + 1):
                t = dur * i / n
                P, L, fov = _cam_eval(keys, ease, t)
                p = 1 - max(0.0, 1 - t / dur) ** W
                r = 1 - p
                m = 1 + (K - 1) * st * f * r
                th = math.radians(TH * st * f * r * sgn)
                v = P - L
                vx = v.x * math.cos(th) - v.z * math.sin(th)
                vz = v.x * math.sin(th) + v.z * math.cos(th)
                Q = L + Vector((vx, v.y, vz)) * m + Vector((0, H * st * f * r, 0))
                out.append((t, Q, L, fov, P))
            return out

        def bad(pts):
            for t, Q, L, fov, P in pts[::2] + [pts[-1]]:
                if abs(L.x) < 13 and abs(L.z) < 150 and abs(Q.x) > max(10.0, abs(P.x)) and Q.y < 14:
                    return True       # 시장 길 밖(건물·노점 안)으로 나가지 않게
                # 원래 카메라 자리에서 새 자리까지, 그리고 피사체 쪽 시선(원래 거리 80% 지점부터)이 막히면 안 됨
                if _ray_block(dg, skip, tuple(P), tuple(Q)) is not None:
                    return True
                dq = Q - L
                if dq.length > 1e-3:
                    s0 = L + dq.normalized() * min((P - L).length * 0.8, dq.length * 0.95)
                    if _ray_block(dg, skip, tuple(s0), tuple(Q)) is not None:
                        return True
                At = []
                for a in sh["actors"].values():
                    try:
                        At.append(RT._path(a, t)[:2])
                    except Exception:
                        pass
                for ax, az in At + A:     # 다른 배우 몸 속으로 들어가지 않게 (그 시각 실제 위치)
                    dq = math.hypot(Q.x - ax, Q.z - az)
                    dp = math.hypot(P.x - ax, P.z - az)
                    if dq < 1.8 and Q.y < 6.5 and dq < dp - 0.05:
                        return True
            return False
        f = 1.0
        pts = path(f)
        while f > 0.05 and bad(pts):
            f *= 0.7
            pts = path(f)
        if f <= 0.05:
            continue
        sh["cam0"] = keys
        sh["cam"] = [(round(t, 4), tuple(Q), tuple(L), fov) for t, Q, L, fov, P in pts]
        sh["ease"] = "lin"
        rep.append((ln, round(f, 2)))
    print("DYNCAM", len(rep), rep, flush=True)


SEP_R = 2.3      # 몸통 폭 2 + 여유: 이보다 가까우면 겹쳐 보임


def _separate(S, fixed):
    """걷는 사람은 다른 사람(서 있는 사람·배우 포함)과 SEP_R 보다 가까워지면 자기 오른쪽(옆)으로 부드럽게 비켜 간다.
    위치는 시간의 연속 함수라 프레임마다 튀지 않는다. 서 있는 사람은 움직이지 않는다."""
    n = len(S)
    walk = [m["kind"] == "walk" for _, _, _, _, m in S]
    rgt = []
    for x, z, yaw, _, _ in S:
        a = math.radians(yaw)
        rgt.append((math.cos(a), -math.sin(a)))      # 진행 방향 (sin, cos) 의 오른쪽
    for _ in range(4):
        for i in range(n):
            if not walk[i]:
                continue
            rx, rz = rgt[i]
            others = [(S[j][0], S[j][1], walk[j] and j < i) for j in range(n) if j != i] + [(ax, az, False) for ax, az in fixed]
            for ox, oz, mutual in others:
                dx, dz = S[i][0] - ox, S[i][1] - oz
                d = math.hypot(dx, dz)
                if d >= SEP_R:
                    continue
                lat = dx * rx + dz * rz
                sgn = (1 if lat >= 0 else -1) if abs(lat) > 0.15 else 1
                push = (SEP_R - d) * (0.5 if mutual else 1.0)
                S[i][0] += rx * sgn * push
                S[i][1] += rz * sgn * push


MIN_CAM = 6.2     # 약 2m (캐릭터 키 5.5칸 ≈ 1.8m) : 사람 얼굴·몸이 화면을 꽉 채우지 않게
MIN_ACTOR = 6.5   # 다른 사람 몸과도 2m 이상 (어깨 너머 초근접 금지)


def _crowd_xz(m, t):
    if m["kind"] != "walk":
        return m["x"], m["z"]
    (x0, z0), (x1, z1) = m["p0"], m["p1"]
    L = math.hypot(x1 - x0, z1 - z0)
    d = (m["sp"] * t) % (2 * L)
    u = d / L if d < L else 2 - d / L
    return x0 + (x1 - x0) * u, z0 + (z1 - z0) * u


def _occludes(L, Q, ax, az, ay):
    """배우(세로 기둥: 발 ay ~ 머리 ay+5.6)가 카메라 Q -> 바라보는 곳 L 시선을 가리는가."""
    vx, vz = L.x - Q.x, L.z - Q.z
    ll = vx * vx + vz * vz
    if ll < 1e-6:
        return False
    u = ((ax - Q.x) * vx + (az - Q.z) * vz) / ll
    if u < 0.0 or u > 0.92:
        return False
    lat = math.hypot(Q.x + vx * u - ax, Q.z + vz * u - az)
    hy = Q.y + (L.y - Q.y) * u
    return lat < 2.2 and ay - 0.5 < hy < ay + 5.9


def enforce_distance():
    """모든 컷·모든 프레임: 카메라는 바라보는 곳과 MIN_CAM 이상, 사람들과 MIN_ACTOR 이상 떨어지고,
    주인공 앞을 다른 배우가 가리지 않게 필요하면 옆으로 돌아간 각도를 찾는다(컷 전체에 같은 각도 → 흔들림 없음).
    벽·지붕·시장 길 밖에 막히는 자리는 쓰지 않는다. 배경이 보이게 조리개도 조인다. 카메라 앞에 붙는 군중은 뺀다."""
    dg = bpy.context.evaluated_depsgraph_get()
    skip = {o.name for o in bpy.data.objects if o.name.startswith("HQ_")}
    for info in RT._S["chars"].values():
        skip |= {p["ob"] for p in info["parts"]}
        for lst in info["pool"].values():
            skip |= set(lst)
        skip.add(info["num"])
    ANG = [0, 15, -15, 30, -30, 45, -45, 60, -60, 80, -80, 100, -100]
    rep = []
    for sh in RT._S["shots"]:
        keys = sh.get("cam")
        if not keys or sh.get("nomin"):
            continue
        dur = sh["dur"]
        ease = sh.get("ease", "smooth")
        n = max(2, int(round(dur * 30)))
        fr = []
        for i in range(n + 1):
            t = dur * i / n
            P, L, fov = _cam_eval(keys, ease, t)
            At = []
            for a in sh["actors"].values():
                try:
                    ax, az = RT._path(a, t)[:2]
                    At.append((ax, az, a.get("y", 0.4)))
                except Exception:
                    pass
            fr.append((t, P, L, fov, At))

        armshot = False
        for a in sh["actors"].values():
            if a.get("num") and a.get("bare"):
                for t, P, L, fov, At in fr[::6]:
                    for ax, az, ay in At:
                        if math.hypot(L.x - ax, L.z - az) < 2.2 and ay + 2.0 < L.y < ay + 5.0 and (P - L).length < 4.5:
                            armshot = True
        HMIN = 5.2 if armshot else 6.5      # 화면 세로에 최소 이만큼(칸) 담기게: 얼굴·몸 확대 금지

        def solve(P, L, At, ang, rays=True, fov=40.0):
            v = P - L
            d0 = v.length
            dn = v / d0 if d0 > 1e-4 else Vector((0, 0.3, -1)).normalized()
            th = math.radians(ang)
            dn = Vector((dn.x * math.cos(th) - dn.z * math.sin(th), dn.y, dn.x * math.sin(th) + dn.z * math.cos(th)))
            subj = [p for p in At if math.hypot(p[0] - L.x, p[1] - L.z) < 2.6]
            others = [p for p in At if p not in subj]
            D = max(d0, MIN_CAM, HMIN / (2 * math.tan(math.radians(fov) / 2)))
            while D <= 34:
                Q = L + dn * D
                good = all(not (math.hypot(Q.x - ax, Q.z - az) < MIN_ACTOR and Q.y - ay < 8.0) for ax, az, ay in At)
                good = good and not any(_occludes(L, Q, ax, az, ay) for ax, az, ay in others)
                if abs(L.x) < 13 and abs(L.z) < 150 and abs(Q.x) > max(10.5, abs(P.x)) and Q.y < 14:
                    return None
                if good:
                    break
                D += 0.25
            if D > 34:
                return None
            Q = L + dn * D
            if rays and (D > d0 + 0.05 or ang):
                if _ray_block(dg, skip, tuple(P), tuple(Q)) is not None:
                    return None
                s0 = L + dn * min(d0 * 0.8, D * 0.95)
                if _ray_block(dg, skip, tuple(s0), tuple(Q)) is not None:
                    return None
            return D, dn, d0
        best = None
        for ang in ANG:
            fails = 0
            for t, P, L, fov, At in fr[::3] + [fr[-1]]:
                if solve(P, L, At, ang, fov=fov) is None:
                    fails += 1
            if best is None or fails < best[1]:
                best = (ang, fails)
            if fails == 0:
                break
        ang = best[0]
        sol = []
        for t, P, L, fov, At in fr:
            r = solve(P, L, At, ang, rays=False, fov=fov)
            if r is None:
                r = solve(P, L, At, 0, rays=False, fov=fov) or ((P - L).length, (P - L).normalized(), (P - L).length)
            sol.append(r)
        Ds = [r[0] for r in sol]
        W = 12
        sm = [max(Ds[max(0, i - W):i + W + 1]) for i in range(len(Ds))]
        sm2 = [sum(sm[max(0, i - W):i + W + 1]) / len(sm[max(0, i - W):i + W + 1]) for i in range(len(sm))]
        out, changed = [], 0.0
        for (t, P, L, fov, At), (D, dn, d0), Dm in zip(fr, sol, sm2):
            D = max(D, Dm)
            Q = L + dn * D
            P0 = L + dn * d0
            if D > d0 + 0.05:                     # 벽·지붕 밖으로는 절대 안 나가게 마지막 확인
                frb = _ray_block(dg, skip, tuple(P0), tuple(Q))
                if frb is not None:
                    D = d0 + (D - d0) * frb * 0.85
                    Q = L + dn * D
            changed = max(changed, D - d0)
            out.append((round(t, 4), tuple(Q), tuple(L), fov))
        sh["cam"] = out
        sh["ease"] = "lin"
        sh["fstop"] = max(sh.get("fstop", 2.8) or 2.8, 5.6)     # 배경도 또렷하게
        rep.append((sh["lines"][0], ang, best[1], round(changed, 1)))
        # 카메라 앞에 붙거나 주인공을 가리는 배경 군중 빼기
        ln = sh["lines"][0]
        cr = HQ["crowd_by_shot"].get(ln)
        if cr:
            keep = []
            for m in cr:
                bad = False
                for t, Q, L, fov in out[::3]:
                    Q, L = Vector(Q), Vector(L)
                    x, z = _crowd_xz(m, t)
                    dq = math.hypot(Q.x - x, Q.z - z)
                    if dq < MIN_ACTOR + 0.6 and Q.y < 9:
                        bad = True
                        break
                    if dq < 14 and _occludes(L, Q, x, z, 0.4):
                        bad = True
                        break
                    # 주인공보다 카메라 쪽(앞)에 있고 화면 안쪽이면 크게 걸리므로 뺀다
                    dl = math.hypot(Q.x - L.x, Q.z - L.z)
                    if dq < dl + 1.5 and dq < 16:
                        fx, fz = (L.x - Q.x) / max(dl, 1e-3), (L.z - Q.z) / max(dl, 1e-3)
                        fwd = (x - Q.x) * fx + (z - Q.z) * fz
                        lat = abs((x - Q.x) * fz - (z - Q.z) * fx)
                        if fwd > 0 and lat < fwd * math.tan(math.radians(fov) * 0.5) * 0.75 + 1.2:
                            bad = True
                            break
                if not bad:
                    keep.append(m)
            HQ["crowd_by_shot"][ln] = keep
    print("MINDIST", rep, flush=True)


def update_crowd(shot_n, t):
    ob = bpy.data.objects.get("HQ_Crowd")
    if not ob:
        return
    spec = HQ["crowd_by_shot"].get(shot_n, [])
    ob.hide_render = not spec
    if not spec:
        return
    cam = bpy.context.scene.camera.matrix_world.translation
    co, idx, rot = [], [], []
    S = []
    for m in spec:
        if m["kind"] == "walk":
            (x0, z0), (x1, z1) = m["p0"], m["p1"]
            L = math.hypot(x1 - x0, z1 - z0)
            d = (m["sp"] * t) % (2 * L)
            fwd = d < L
            u = d / L if fwd else 2 - d / L
            x, z = x0 + (x1 - x0) * u, z0 + (z1 - z0) * u
            dx, dz = (x1 - x0, z1 - z0) if fwd else (x0 - x1, z0 - z1)
            yaw = math.degrees(math.atan2(dx, dz))
            pose = int(((m["sp"] * t) / 4.5 + m["ph"]) * NWALK) % NWALK
        else:
            x, z, yaw = m["x"], m["z"], m["yaw"]
            pose = POSES.index(m["pose"])
            if m["pose"] == "talk" and (t + m["x"]) % 1.6 > 0.9:
                pose = POSES.index("idle")
        S.append([x, z, yaw, pose, m])
    _separate(S, HQ.get("actor_xz", []))
    zs = HQ.get("zoom_seg")
    if zs:      # 팔 확대 중: 카메라 -> 숫자 시선을 가리는 군중은 뺀다
        (qx, qz), (cx, cz) = zs
        vx, vz = cx - qx, cz - qz
        ll = vx * vx + vz * vz
        keep = []
        for s in S:
            u = ((s[0] - qx) * vx + (s[1] - qz) * vz) / max(ll, 1e-6)
            u = min(max(u, 0.0), 1.0)
            if math.hypot(qx + vx * u - s[0], qz + vz * u - s[1]) > 2.0:
                keep.append(s)
        S = keep
    for x, z, yaw, pose, m in S:
        p = bpos(x, _y(x), z)
        lod = 0 if (p - cam).length < 40 else 1
        co += list(p)
        idx.append((m["v"] * 2 + lod) * NP + pose)
        rot.append(math.radians(yaw - 180))
    me = ob.data
    n = len(me.vertices)
    while len(idx) < n:                       # 남는 점은 땅 아래로 숨김
        co += [0.0, 0.0, -500.0]
        idx.append(0)
        rot.append(0.0)
    me.vertices.foreach_set("co", co)
    me.attributes["inst_idx"].data.foreach_set("value", idx)
    me.attributes["rot_z"].data.foreach_set("value", rot)
    me.update()


# ------------------------------------------------------------------ 프레임 처리기
def hq_frame(scene, depsgraph=None):
    if not HQ["ready"]:
        return
    ff = scene.frame_current + scene.frame_subframe
    T = max(ff - 1, 0) / 30.0
    sh = RT._S["shots"][RT._S["last"]] if RT._S.get("last") is not None else None
    if sh is None:
        return
    t = T - sh["start"]
    axz = []
    for a in sh["actors"].values():
        try:
            px, pz = RT._path(a, t)[:2]
            axz.append((px, pz))
        except Exception:
            pass
    HQ["actor_xz"] = axz
    HQ["zoom_seg"] = None
    try:
        zoom_cam(scene, sh, t, depsgraph)
    except Exception as ex:
        print("ZOOM ERR", ex, flush=True)
    qmark(scene, sh, t)
    nofire = bool(sh.get("nofire"))
    HQ["nofire_now"] = nofire
    hlo = bpy.data.objects.get("HQ_HallLight")
    if hlo:
        hlo.data.energy = 900.0 if sh.get("door") else 0.0
    for ob in HQ.get("fire_objs", []):
        ob.hide_render = nofire
    update_crowd(sh["lines"][0], t)
    update_lights(sh.get("light", "day") == "day")
    if sh.get("light", "day") != "day":
        scene.view_settings.exposure = 0.05 + sh.get("exp", 0.0)   # 기존 +0.55 → 밤답게
    update_effects(T)
    tg = bpy.data.objects.get("TouchGlow")       # 손목 빛 조명은 팔까지 번쩍이게 하므로 끈다 (빛은 숫자에만)
    if tg:
        tg.data.energy = 0.0
    am = bpy.data.materials.get("HQ_AtmosVol")
    if am:
        pv = next(n for n in am.node_tree.nodes if n.bl_idname == "ShaderNodeVolumePrincipled")
        pv.inputs["Color"].default_value = (1.0, 0.93, 0.84, 1) if sh.get("light", "day") == "day" else (0.55, 0.65, 1.0, 1)


def numbers():
    """팔 시간: 한글 '일' 이 들어가므로 또렷한 둥근 고딕(Jua). 숫자 빛은 숫자에만 — 팔·주변을 비추지 않게 광선 가시성을 끈다."""
    fp = os.path.join(os.path.dirname(bpy.data.filepath), "..", "audio", "fonts", "Jua-Regular.ttf")
    font = bpy.data.fonts.load(os.path.abspath(fp), check_existing=True)
    for ob in bpy.data.objects:
        if ob.name.endswith("#NUM") and ob.type == "FONT":
            ob.data.font = font
            ob.data.size = 0.24
            ob.data.extrude = 0.003
            ob.data.space_line = 1.0
            ob.visible_diffuse = ob.visible_glossy = ob.visible_transmission = ob.visible_volume_scatter = False
            ob.visible_shadow = False
    # 실제 글꼴로 글자 폭·줄 간격을 재서 runtime.fit 에 넘김 (크기 1 기준)
    cu = bpy.data.curves.new("HQ_Measure", "FONT")
    cu.font = font
    cu.size = 1.0
    cu.space_line = 1.0
    tmp = bpy.data.objects.new("HQ_Measure", cu)
    bpy.context.scene.collection.objects.link(tmp)

    def ext(body):
        cu.body = body
        dg = bpy.context.evaluated_depsgraph_get()
        dg.update()
        me = tmp.evaluated_get(dg).to_mesh()
        xs = [v.co.x for v in me.vertices]
        ys = [v.co.y for v in me.vertices]
        r = (max(xs) - min(xs), max(ys) - min(ys)) if xs else (0.0, 0.0)
        tmp.evaluated_get(dg).to_mesh_clear()
        return r
    cw = {}
    for ch in "0123456789,:일 ":
        cw[ch] = (ext("0" + ch * 10 + "0")[0] - ext("00")[0]) / 10.0
    h1 = ext("0")[1]
    pitch = ext("0\n0\n0")[1] - ext("0\n0")[1]
    RT.GLYPH.update({"w": cw, "h": h1, "pitch": pitch})
    bpy.data.objects.remove(tmp)
    bpy.data.curves.remove(cu)
    print("GLYPH", {k: round(v, 3) for k, v in cw.items()}, round(h1, 3), round(pitch, 3), flush=True)


# ------------------------------------------------------------------ 팔 숫자 확대 (망원) 카메라
ZOOM_D = 6.8        # 카메라는 숫자에서 이만큼(약 2m) 떨어져 망원으로 당겨 찍는다 (막히면 더 가까이)


def _sm(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def zoom_cam(scene, sh, t, dg):
    """shot["zoom"] = [(배우, 시작, 끝, [가로폭 칸], [올려보기])]: 그 배우 팔 숫자를 정면에서 망원으로 크게.
    시작<=0 이면 컷 처음부터, 끝>=길이 면 컷 끝까지 확대. 그 사이 0.45초에 걸쳐 부드럽게 들어가고 나온다."""
    zs = sh.get("zoom")
    if not zs:
        return
    R = 0.45
    w, who, wid, elev = 0.0, None, 1.15, 0.3
    for z in zs:
        a = 1.0 if z[1] <= 0 else _sm((t - z[1]) / R)
        b = 1.0 if z[2] >= sh["dur"] - 1e-3 else 1 - _sm((t - (z[2] - R)) / R)
        ww = min(a, b)
        if ww > w:
            w, who = ww, z[0]
            wid = z[3] if len(z) > 3 else 1.15
            elev = z[4] if len(z) > 4 else 0.3
    info = RT._S["chars"].get(who)
    if w <= 1e-4 or not info:
        return
    O = bpy.data.objects
    num = O[info["num"]]
    if num.hide_render:
        return
    if dg is None:
        dg = bpy.context.evaluated_depsgraph_get()
    ev = num.evaluated_get(dg)
    Mn = num.matrix_world
    cs = [Mn @ Vector(c) for c in ev.bound_box]
    c = sum(cs, Vector()) / 8
    M3 = Mn.to_3x3()
    n = (M3 @ Vector((0, 0, 1))).normalized()
    u = (M3 @ Vector((0, 1, 0))).normalized()
    UP = Vector((0, 0, 1))
    skip = set(HQ["zoom_skip"]) | {p["ob"] for p in info["parts"]} | {info["num"]}
    for lst in info["pool"].values():
        skip |= set(lst)
    best = None
    for ang in (0, 22, -22, 45, -45):
        d = (n + UP * elev).normalized()
        th = math.radians(ang)
        d = Vector((d.x * math.cos(th) - d.y * math.sin(th), d.x * math.sin(th) + d.y * math.cos(th), d.z)).normalized()
        o, free = c + d * 0.03, ZOOM_D + 0.5
        for _ in range(10):
            hit, loc, _, _, ob, _ = scene.ray_cast(dg, o, d, distance=ZOOM_D + 0.5 - (o - c).length)
            if not hit:
                break
            if ob is not None and (ob.name in skip or ob.name.startswith("HQ_")):
                o = loc + d * 0.02
                continue
            free = (loc - c).length
            break
        if best is None or free > best[1] + 0.3:
            best = (d, free)
        if free >= ZOOM_D:
            break
    d, free = best
    D = max(1.4, min(ZOOM_D, free * 0.85))
    zc = d
    # 화면 위쪽: 수평선은 최대한 유지(세상 위쪽), 글자가 읽히도록 글자 위쪽 쪽으로 최대 40도만 기울임
    y0 = UP - zc * UP.dot(zc)
    y1 = u - zc * u.dot(zc)
    if y0.length < 1e-3:
        y0 = y1
    y0.normalize()
    zy = y0
    if y1.length > 1e-3:
        y1.normalize()
        ang = math.atan2(y0.cross(y1).dot(zc), y0.dot(y1))
        if abs(ang) <= math.radians(115):
            ang = max(-math.radians(40), min(math.radians(40), ang))
        zy = (Matrix.Rotation(ang, 3, zc) @ y0).normalized()
    zx = zy.cross(zc).normalized()
    Rz = Matrix((zx, zy, zc)).transposed()
    pz = c + d * D
    V = wid * 16.0 / 9.0
    az = 2 * math.atan(V / 2 / D)
    cam = scene.camera
    pc = cam.matrix_world.translation.copy()
    qc = cam.matrix_world.to_quaternion()
    qz = Rz.to_quaternion()
    p = pc.lerp(pz, w)
    q = qc.slerp(qz, w)
    cam.matrix_world = Matrix.Translation(p) @ q.to_matrix().to_4x4()
    cam.data.angle = cam.data.angle + (az - cam.data.angle) * w
    dof = cam.data.dof
    dof.focus_distance = dof.focus_distance + ((c - p).length - dof.focus_distance) * w
    dof.aperture_fstop = dof.aperture_fstop + (4.0 - dof.aperture_fstop) * w
    HQ["zoom_seg"] = ((p.x, -p.y), (c.x, -c.y))


# ------------------------------------------------------------------ 머리 위 물음표
def qmark(scene, sh, t):
    ob = bpy.data.objects.get("HQ_QMark")
    if not ob:
        return
    q = sh.get("qmark")
    info = RT._S["chars"].get(q[0]) if q else None
    if not q or not info or t < q[1]:
        ob.hide_render = True
        return
    hp = bpy.data.objects[info["parts"][info["head"]["idx"]]["ob"]].matrix_world.translation
    e = _sm((t - q[1]) / 0.12)
    pop = 1 + 0.35 * math.sin(math.pi * min(max((t - q[1]) / 0.3, 0), 1))
    s = 1.15 * e * pop
    cam = scene.camera
    R = cam.matrix_world.to_quaternion().to_matrix().to_4x4()
    pos = hp + Vector((0, 0, 2.3 + 0.06 * math.sin((t - q[1]) * 6)))
    ob.matrix_world = Matrix.Translation(pos) @ R @ Matrix.Rotation(math.radians(8 * math.sin((t - q[1]) * 4)), 4, "Z") @ Matrix.Diagonal((s, s, s, 1))
    ob.hide_render = s < 1e-3


def qmark_object():
    fp = os.path.join(os.path.dirname(bpy.data.filepath), "..", "audio", "fonts", "Jua-Regular.ttf")
    font = bpy.data.fonts.load(os.path.abspath(fp), check_existing=True)
    cu = bpy.data.curves.new("HQ_QMark", "FONT")
    cu.body = "?"
    cu.font = font
    cu.size = 2.4
    cu.extrude = 0.14
    cu.offset = 0.035          # 굵게
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    ob = bpy.data.objects.new("HQ_QMark", cu)
    cu.materials.append(_emit_mat("HQ_QMarkMat", (1.0, 0.8, 0.1, 1), 4.0))
    ob.visible_shadow = False
    ob.hide_render = True
    bpy.context.scene.collection.objects.link(ob)


# ------------------------------------------------------------------ 다락방 문: 벽에 문 구멍 + 문 밖 복도
def _box(name, lo, hi, color, mat=None):
    """로블록스 좌표 lo~hi 상자."""
    import bmesh
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    c = [(lo[i] + hi[i]) / 2 for i in range(3)]
    s = [hi[i] - lo[i] for i in range(3)]
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(bpos(*c)) @ Matrix.Diagonal((s[0], s[2], s[1], 1)))
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    if mat:
        me.materials.append(mat)
    ob.color = color + (1,) if len(color) == 3 else color
    bpy.context.scene.collection.objects.link(ob)
    return ob


def door_hole():
    door = bpy.data.objects.get("HaruRoom.Door")
    if not door:
        return
    cut = _box("HQ_DoorCut", (456.6, 0.05, -6.75), (459.8, 6.95, -3.25), (1, 1, 1))
    cut.hide_render = True
    cut.hide_viewport = True
    lo, hi = bpos(456.6, 0.05, -6.75), bpos(459.8, 6.95, -3.25)
    blo = Vector((min(lo.x, hi.x), min(lo.y, hi.y), min(lo.z, hi.z)))
    bhi = Vector((max(lo.x, hi.x), max(lo.y, hi.y), max(lo.z, hi.z)))
    n = 0
    for ob in list(bpy.data.objects):
        if ob.type != "MESH" or not ob.name.startswith("HaruRoom.") or ob.name == "HaruRoom.Door":
            continue
        bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        a = Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb)))
        b = Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))
        if all(a[i] < bhi[i] and b[i] > blo[i] for i in range(3)):
            if (b - a).length < 3.0:
                continue        # 작은 소품(문고리 등)은 건드리지 않음
            m = ob.modifiers.new("HQ_DoorHole", "BOOLEAN")
            m.object = cut
            m.operation = "DIFFERENCE"
            m.solver = "EXACT"
            n += 1
    wood = bpy.data.materials.get("R_WoodPlanks") or bpy.data.materials.get("R_Wood")
    col = (0.22, 0.15, 0.1)
    _box("XQ_HallFloor", (447.0, -1.0, -10.0), (457.6, 0.0, 0.0), col, wood)
    _box("XQ_HallWallS", (447.0, 0.0, -10.6), (457.6, 8.5, -10.0), col, wood)
    _box("XQ_HallWallN", (447.0, 0.0, 0.0), (457.6, 8.5, 0.6), col, wood)
    _box("XQ_HallWallW", (446.4, 0.0, -10.6), (447.0, 8.5, 0.6), col, wood)
    _box("XQ_HallCeil", (447.0, 8.5, -10.6), (457.6, 9.1, 0.6), col, wood)
    hl = bpy.data.lights.new("HQ_HallLight", "POINT")       # 복도 등불: 문이 열리면 따뜻한 빛이 새어 들어옴
    hl.color, hl.energy, hl.shadow_soft_size = (1.0, 0.68, 0.38), 0.0, 0.3
    hl.use_custom_distance, hl.cutoff_distance = True, 16
    hlo = bpy.data.objects.new("HQ_HallLight", hl)
    hlo.location = bpos(451.5, 6.5, -5.0)
    bpy.context.scene.collection.objects.link(hlo)
    print("DOORHOLE cut", n, flush=True)


# ------------------------------------------------------------------ 수리점 안 아기 침대
CRIB = (395.0, -2.0)      # 아기 침대 중심 (로블록스 x, z)
CRIB_TOP = 2.3            # 매트리스 윗면 높이


def crib():
    wood = bpy.data.materials.get("R_Wood") or bpy.data.materials.get("R_WoodPlanks")
    cx, cz = CRIB
    hx, hz = 1.5, 1.9
    wc = (0.78, 0.6, 0.4)
    for i, (sx, sz) in enumerate(((-1, -1), (1, -1), (-1, 1), (1, 1))):
        x, z = cx + sx * (hx - 0.12), cz + sz * (hz - 0.12)
        _box(f"XQ_CribLeg{i}", (x - 0.12, 0.0, z - 0.12), (x + 0.12, CRIB_TOP + 0.75, z + 0.12), wc, wood)
    _box("XQ_CribBase", (cx - hx, CRIB_TOP - 0.45, cz - hz), (cx + hx, CRIB_TOP - 0.25, cz + hz), wc, wood)
    _box("XQ_CribMat", (cx - hx + 0.1, CRIB_TOP - 0.25, cz - hz + 0.1), (cx + hx - 0.1, CRIB_TOP, cz + hz - 0.1), (0.92, 0.9, 0.86))
    _box("XQ_CribPillow", (cx - 0.55, CRIB_TOP, cz + hz - 0.9), (cx + 0.55, CRIB_TOP + 0.18, cz + hz - 0.2), (0.97, 0.95, 0.92))
    # 난간: 위 가로대 + 살 (앞쪽 -x 면은 낮게: 팔 숫자를 위에서 보도록)
    for side, top in ((-1, CRIB_TOP + 0.35), (1, CRIB_TOP + 0.7)):
        x = cx + side * (hx - 0.06)
        _box(f"XQ_CribRail{side}", (x - 0.06, top - 0.1, cz - hz), (x + 0.06, top, cz + hz), wc, wood)
        k = 0
        z = cz - hz + 0.35
        while z < cz + hz - 0.2:
            _box(f"XQ_CribBar{side}_{k}", (x - 0.04, CRIB_TOP, z - 0.04), (x + 0.04, top - 0.1, z + 0.04), wc, wood)
            z += 0.42
            k += 1
    for side in (-1, 1):
        z = cz + side * (hz - 0.06)
        _box(f"XQ_CribEnd{side}", (cx - hx, CRIB_TOP - 0.25, z - 0.08), (cx + hx, CRIB_TOP + 0.85, z + 0.08), wc, wood)


def apply():
    RT._init()
    qmark_object()
    door_hole()
    crib()
    numbers()
    materials()
    world()
    lights()
    atmosphere()
    effects_static()
    HQ["fire_objs"] = [o for o in bpy.data.objects if o.name.startswith(("HQ_Fire", "HQ_Flame", "HQ_Embers", "HQ_Coal", "HQ_Brazier"))
                       and o.type != "LIGHT"]
    HQ["zoom_skip"] = {o.name for o in bpy.data.objects if o.name.startswith("HQ_")}
    lib = crowd_library()
    HQ["crowd_by_shot"] = {}
    for sh in RT._S["shots"]:
        c = auto_crowd(sh)
        if c:
            HQ["crowd_by_shot"][sh["lines"][0]] = c
    HQ["crowd_by_shot"].update({23: crowd_shot23(), 4: crowd_shot4()})
    dynamic_cams()
    enforce_distance()
    crowd_object(lib, max(len(v) for v in HQ["crowd_by_shot"].values()))
    RT._S["vis"] = set()
    for lst in (bpy.app.handlers.frame_change_post,):
        for h in list(lst):
            if getattr(h, "__name__", "") == "hq_frame":
                lst.remove(h)
    bpy.app.handlers.frame_change_post.append(hq_frame)
    HQ["ready"] = True


def eevee_hq(samples):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    e = sc.eevee
    e.taa_render_samples = samples
    for k, v in (("shadow_pool_size", "2048"), ("shadow_ray_count", 3), ("shadow_step_count", 12), ("use_shadows", True),
                 ("use_raytracing", True), ("use_fast_gi", True), ("fast_gi_method", "GLOBAL_ILLUMINATION"),
                 ("volumetric_tile_size", "4"), ("volumetric_samples", 96), ("volumetric_start", 0.5), ("volumetric_end", 350.0),
                 ("use_volumetric_shadows", True), ("volumetric_shadow_samples", 32), ("volumetric_light_clamp", 0.0),
                 ("use_shadow_jitter_viewport", False)):
        try:
            setattr(e, k, v)
        except Exception as ex:
            print("eevee opt skip", k, ex)
    try:
        e.ray_tracing_options.resolution_scale = "1"
        e.ray_tracing_options.use_denoise = True
    except Exception as ex:
        print("rt opt", ex)
    for lo in bpy.data.objects:
        if lo.type == "LIGHT":
            try:
                lo.data.use_shadow_jitter = lo.name in ("Sun", "HQ_Key", "HQ_Rim")
            except Exception:
                pass


def cycles_hq(samples):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    pr = bpy.context.preferences.addons["cycles"].preferences
    pr.compute_device_type = "OPTIX"
    pr.refresh_devices()
    names = []
    for d in pr.devices:
        d.use = d.type == "OPTIX"
        if d.use:
            names.append(d.name)
    c = sc.cycles
    c.device = "GPU"
    c.samples = samples
    c.use_adaptive_sampling = True
    c.adaptive_threshold = 0.01
    c.use_denoising = True
    c.denoiser = "OPENIMAGEDENOISE"
    try:
        c.denoising_use_gpu = True
    except Exception:
        pass
    c.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    c.max_bounces, c.diffuse_bounces, c.glossy_bounces, c.transmission_bounces, c.volume_bounces = 8, 3, 3, 6, 1
    c.caustics_reflective = c.caustics_refractive = False
    c.volume_step_rate = 2.0
    c.use_light_tree = True
    c.sample_clamp_indirect = 8.0
    return names
