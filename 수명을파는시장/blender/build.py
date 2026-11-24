"""수명을 파는 시장 — 블렌더 장면 짓기.
입력: export.txt (Studio에서 뽑은 마을·배우), shots.py (배우 복제 목록)
출력: market.blend (+ runtime.py 내장)
사용: blender --background --factory-startup --python build.py
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector

DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DIR)
import shots as SH  # noqa: E402

EXPORT = os.path.join(DIR, "export.txt")
OUT_BLEND = os.path.join(DIR, "market.blend")
FRAMES_DIR = os.path.join(DIR, "frames")
FONT_SIGN = r"C:\Windows\Fonts\malgunbd.ttf"
FONT_INK = r"C:\Windows\Fonts\Inkfree.ttf"

C = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))


def bpos(x, y, z):
    return Vector((x, -z, y))


def brot(w, x, y, z):
    return C @ Quaternion((w, x, y, z)).to_matrix() @ C.transposed()


def lin(h):
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return tuple(((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92 for c in (r, g, b))


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.name = "Market"
COLS = {}


def col_for(tag):
    if tag not in COLS:
        c = bpy.data.collections.new(tag)
        scene.collection.children.link(c)
        COLS[tag] = c
    return COLS[tag]


def mesh_from(name, verts, faces):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    return me


h = 0.5
CUBE_V = [(-h, -h, -h), (h, -h, -h), (h, h, -h), (-h, h, -h), (-h, -h, h), (h, -h, h), (h, h, h), (-h, h, h)]
CUBE_F = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
MESH_CUBE = mesh_from("u_cube", CUBE_V, CUBE_F)
# 로블록스 쐐기 (지난 영상에서 확인한 방향 그대로)
MESH_WEDGE = mesh_from("u_wedge", [(-h, -h, -h), (h, -h, -h), (h, h, -h), (-h, h, -h), (-h, -h, h), (h, -h, h)],
                       [(0, 3, 2, 1), (0, 1, 5, 4), (1, 2, 5), (0, 4, 3), (3, 4, 5, 2)])


def make_cylinder(name="u_cyl", segs=28):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=0.5, radius2=0.5, depth=1.0)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90), 3, "Y"))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = len(p.vertices) == 4
    return me


def make_sphere(name="u_sphere"):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=14, radius=0.5)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return me


MESH_CYL = make_cylinder()
MESH_SPHERE = make_sphere()
for me in (MESH_CUBE, MESH_WEDGE, MESH_CYL, MESH_SPHERE):
    me.materials.append(None)


def unit_mesh(k):
    return {"W": MESH_WEDGE, "K": MESH_WEDGE, "C": MESH_CYL, "S": MESH_SPHERE}.get(k, MESH_CUBE)


# ------------------------------------------------------------------ 재질
MAT_INFO = {
    "SmoothPlastic": (0.42, 0, "noise", 0.6, 0.04, 0.0), "Plastic": (0.5, 0, "noise", 0.6, 0.05, 0.02),
    "Neon": (0.5, 0, "none", 1, 0, 0), "Wood": (0.62, 0, "wave", 0.9, 0.18, 0.05),
    "WoodPlanks": (0.66, 0, "planks", 0.35, 0.22, 0.08), "Cobblestone": (0.85, 0, "voronoi", 0.55, 0.35, 0.25),
    "Brick": (0.82, 0, "voronoi", 0.9, 0.25, 0.15), "Slate": (0.8, 0, "noise", 0.35, 0.22, 0.12),
    "Concrete": (0.88, 0, "noise", 0.8, 0.12, 0.06), "Sand": (0.9, 0, "noise", 1.6, 0.1, 0.05),
    "Rock": (0.9, 0, "noise", 0.3, 0.25, 0.2), "Ground": (0.92, 0, "noise", 0.4, 0.2, 0.1),
    "Grass": (0.9, 0, "noise", 0.25, 0.25, 0.08), "LeafyGrass": (0.9, 0, "noise", 0.25, 0.25, 0.08),
    "Fabric": (0.92, 0, "noise", 3.0, 0.08, 0.04), "Glass": (0.05, 0, "none", 1, 0, 0),
    "Marble": (0.3, 0, "noise", 0.5, 0.08, 0.0), "Metal": (0.32, 0.85, "noise", 1.0, 0.06, 0.02),
    "DiamondPlate": (0.35, 0.8, "noise", 1.0, 0.06, 0.02), "Foil": (0.25, 0.9, "noise", 1.0, 0.05, 0.02),
}
MATS = {}


def new_nodes(idb):
    idb.use_nodes = True
    nt = idb.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    return nt, nt.nodes, nt.links


def get_mat(rbx, transparent=False, character=False):
    key = (rbx, transparent, character)
    if key in MATS:
        return MATS[key]
    rough, metal, pattern, pscale, pstr, bump = MAT_INFO.get(rbx, MAT_INFO["SmoothPlastic"])
    if character:
        pattern, bump, rough = "none", 0, max(rough, 0.6)
    mat = bpy.data.materials.new(f"R_{rbx}{'_T' if transparent else ''}{'_C' if character else ''}")
    nt, N, L = new_nodes(mat)
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    oi = N.new("ShaderNodeObjectInfo")
    emit = N.new("ShaderNodeAttribute")
    emit.attribute_type = "OBJECT"
    emit.attribute_name = "emit"
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if character:
        bsdf.inputs["Specular IOR Level"].default_value = 0.2
    base = oi.outputs["Color"]
    if pattern != "none":
        geo = N.new("ShaderNodeNewGeometry")
        if pattern == "voronoi":
            tex = N.new("ShaderNodeTexVoronoi")
            tex.feature = "DISTANCE_TO_EDGE"
            tex.inputs["Scale"].default_value = pscale
            L.new(geo.outputs["Position"], tex.inputs["Vector"])
            rr = N.new("ShaderNodeMapRange")
            rr.inputs["From Max"].default_value = 0.08
            L.new(tex.outputs["Distance"], rr.inputs["Value"])
            fac = rr.outputs["Result"]
        elif pattern in ("wave", "planks"):
            tex = N.new("ShaderNodeTexWave")
            if pattern == "planks":
                tex.wave_profile = "SAW"
            tex.inputs["Scale"].default_value = pscale
            tex.inputs["Distortion"].default_value = 6 if pattern == "wave" else 1.5
            L.new(geo.outputs["Position"], tex.inputs["Vector"])
            fac = tex.outputs["Fac"]
        else:
            tex = N.new("ShaderNodeTexNoise")
            tex.inputs["Scale"].default_value = pscale
            tex.inputs["Detail"].default_value = 6
            L.new(geo.outputs["Position"], tex.inputs["Vector"])
            fac = tex.outputs["Fac"]
        mr = N.new("ShaderNodeMapRange")
        mr.inputs["To Min"].default_value = 1 - pstr
        L.new(fac, mr.inputs["Value"])
        mix = N.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 1
        L.new(oi.outputs["Color"], mix.inputs["A"])
        L.new(mr.outputs["Result"], mix.inputs["B"])
        base = mix.outputs["Result"]
        if bump > 0:
            bn = N.new("ShaderNodeBump")
            bn.inputs["Strength"].default_value = bump
            L.new(fac, bn.inputs["Height"])
            L.new(bn.outputs["Normal"], bsdf.inputs["Normal"])
    L.new(base, bsdf.inputs["Base Color"])
    L.new(oi.outputs["Color"], bsdf.inputs["Emission Color"])
    L.new(emit.outputs["Fac"], bsdf.inputs["Emission Strength"])
    if transparent:
        L.new(oi.outputs["Alpha"], bsdf.inputs["Alpha"])
        mat.surface_render_method = "DITHERED"
        if rbx == "Glass":
            bsdf.inputs["Specular IOR Level"].default_value = 0.9
    MATS[key] = mat
    return mat


def link_obj_mat(ob, mat):
    ob.material_slots[0].link = "OBJECT"
    ob.material_slots[0].material = mat


# ------------------------------------------------------------------ 읽기
text = open(EXPORT, encoding="utf-8").read()
sec = {}
for chunk in text.split("\n#\n"):
    sec[chunk[0]] = chunk[2:]

# ------------------------------------------------------------------ 고정 세트
EMIT = {"Lamps": 8.0, "Houses": 3.0, "BackHouses": 3.0, "PlazaHouses": 3.0, "default": 5.0}
dyn = {"Window": [], "Lamp": [], "Door": []}
for line in sec["P"].split("\n"):
    if not line:
        continue
    tag, name, dn, k, size, pos, q, col, rmat, tr = line.split("|")
    sx, sy, sz = map(float, size.split(","))
    tr = float(tr)
    bx, by, bz = sx, sz, sy
    if k == "C":
        d = min(sy, sz)
        by, bz = d, d
    if k == "M":
        k = "B"
    ob = bpy.data.objects.new(f"{tag}.{name}", unit_mesh(k))
    ob.matrix_world = Matrix.Translation(bpos(*map(float, pos.split(",")))) @ brot(*map(float, q.split(","))).to_4x4() @ Matrix.Diagonal((bx, by, bz, 1))
    alpha = 1 - tr
    transparent = alpha < 0.9
    ob.color = (*lin(col), alpha if transparent else 1.0)
    ob["emit"] = EMIT.get(tag, EMIT["default"]) if rmat == "Neon" else 0.0
    ob["emit0"] = ob["emit"]
    col_for(tag).objects.link(ob)
    link_obj_mat(ob, get_mat(rmat, transparent))
    if dn in dyn:
        dyn[dn].append(ob.name)
    if tag == "HaruRoom" and name == "Door":
        ob["base_M"] = [list(r) for r in ob.matrix_world]
        dyn["Door"].append(ob.name)
    if tag == "Hills":
        ob.visible_shadow = False

# 바닥 아래 큰 들판 (지평선까지)
gme = bpy.data.meshes.new("far_disc")
bm = bmesh.new()
bmesh.ops.create_circle(bm, cap_ends=True, segments=96, radius=4000)
bm.to_mesh(gme)
bm.free()
gob = bpy.data.objects.new("FarDisc", gme)
gob.location = (0, 100, -0.3)
gmat = bpy.data.materials.new("FarDisc")
nt, N, L = new_nodes(gmat)
o = N.new("ShaderNodeOutputMaterial")
b = N.new("ShaderNodeBsdfPrincipled")
b.inputs["Base Color"].default_value = (0.11, 0.16, 0.05, 1)
b.inputs["Roughness"].default_value = 0.95
L.new(b.outputs["BSDF"], o.inputs["Surface"])
gme.materials.append(gmat)
gob.visible_shadow = False
col_for("Ground").objects.link(gob)

# 간판 글자
font_sign = bpy.data.fonts.load(FONT_SIGN)
for e in [e for e in sec["X"].split(";") if e]:
    face, size, pos, q, fg, bg, body = e.split("|", 6)
    sx, sy, sz = map(float, size.split(","))
    body = body.replace("\\n", "\n").replace("  ", " ")
    cu = bpy.data.curves.new("sign", "FONT")
    cu.body = body
    cu.font = font_sign
    cu.align_x, cu.align_y = "CENTER", "CENTER"
    cu.size = min(sy * 0.55, sx / max(len(body), 1) * 1.45)
    cu.extrude = 0.015
    ob = bpy.data.objects.new("SignText", cu)
    frame = Matrix(((-1, 0, 0), (0, 0, 1), (0, 1, 0))).transposed().to_4x4()
    ob.matrix_world = Matrix.Translation(bpos(*map(float, pos.split(",")))) @ brot(*map(float, q.split(","))).to_4x4() @ Matrix.Translation(Vector((0, sz / 2 + 0.03, 0))) @ frame
    m = bpy.data.materials.new("SignInk")
    nt, N, L = new_nodes(m)
    o = N.new("ShaderNodeOutputMaterial")
    b = N.new("ShaderNodeBsdfPrincipled")
    c = lin(fg)
    b.inputs["Base Color"].default_value = (*c, 1)
    b.inputs["Emission Color"].default_value = (*c, 1)
    b.inputs["Emission Strength"].default_value = 0.5
    b.inputs["Metallic"].default_value = 0.6
    b.inputs["Roughness"].default_value = 0.35
    L.new(b.outputs["BSDF"], o.inputs["Surface"])
    cu.materials.append(m)
    col_for("Signs").objects.link(ob)

# 나눔 규칙 게시판 (결말)
board = bpy.data.objects.new("RuleBoard", MESH_CUBE)
board.matrix_world = Matrix.Translation(bpos(0, 5.2, 14)) @ Matrix.Diagonal((5.2, 0.25, 3.0, 1))
board.color = (*lin("5a3a22"), 1)
board["emit"] = 0.0
link_obj_mat(board, get_mat("WoodPlanks"))
col_for("Rule").objects.link(board)
for sxx in (-2.3, 2.3):
    post = bpy.data.objects.new("RulePost", MESH_CUBE)
    post.matrix_world = Matrix.Translation(bpos(sxx, 2.2, 14.05)) @ Matrix.Diagonal((0.35, 0.3, 4.4, 1))
    post.color = (*lin("3c2616"), 1)
    post["emit"] = 0.0
    link_obj_mat(post, get_mat("Wood"))
    col_for("Rule").objects.link(post)
cu = bpy.data.curves.new("rule", "FONT")
cu.body = "시간은 팔 수 있다\n그리고 나눌 수 있다"
cu.font = font_sign
cu.align_x, cu.align_y = "CENTER", "CENTER"
cu.size = 0.5
cu.extrude = 0.01
rt = bpy.data.objects.new("RuleText", cu)
rt.matrix_world = Matrix.Translation(bpos(0, 5.2, 14.0 + 0.14)) @ Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0))).to_4x4()
m = bpy.data.materials.new("RuleInk")
nt, N, L = new_nodes(m)
o = N.new("ShaderNodeOutputMaterial")
b = N.new("ShaderNodeBsdfPrincipled")
b.inputs["Base Color"].default_value = (1.0, 0.85, 0.5, 1)
b.inputs["Emission Color"].default_value = (1.0, 0.85, 0.5, 1)
b.inputs["Emission Strength"].default_value = 0.4
L.new(b.outputs["BSDF"], o.inputs["Surface"])
cu.materials.append(m)
col_for("Rule").objects.link(rt)

# 조명
lights = []
for i, e in enumerate([e for e in sec["L"].split(";") if e]):
    pos, colh, bright, rng, tag, pname, kind = e.split("|")
    rng = float(rng)
    ld = bpy.data.lights.new(f"L{i}", "POINT")
    ld.color = lin(colh)
    ld.energy = float(bright) * rng * rng * 2.0
    ld.shadow_soft_size = 0.4
    ld.use_custom_distance = True
    ld.cutoff_distance = rng * 2.5
    ld.use_shadow = tag in ("ShopInterior", "HaruRoom") or i % 3 == 0
    ld["base_energy"] = ld.energy
    lo = bpy.data.objects.new(f"L{i}", ld)
    lo.location = bpos(*map(float, pos.split(",")))
    lo["tag"] = tag
    col_for("Lights").objects.link(lo)
    lights.append(lo.name)

sun_d = bpy.data.lights.new("Sun", "SUN")
sun_d.angle = math.radians(2.0)
sun = bpy.data.objects.new("Sun", sun_d)
col_for("Lights").objects.link(sun)
moon_d = bpy.data.lights.new("Moon", "SUN")
moon_d.color = (0.55, 0.66, 1.0)
moon_d.angle = math.radians(3)
moon = bpy.data.objects.new("Moon", moon_d)
moon.rotation_euler = Vector((0, 0, 1)).rotation_difference(bpos(0.6, 0.55, 0.58).normalized()).to_euler()
col_for("Lights").objects.link(moon)
# 방 안 달빛 (다락방 둥근 창으로 들어오는 푸른 빛)
md = bpy.data.lights.new("RoomMoon", "SPOT")
md.color = (0.55, 0.68, 1.0)
md.energy = 900
md.spot_size = math.radians(70)
md.shadow_soft_size = 1.0
mo = bpy.data.objects.new("RoomMoon", md)
mo.location = bpos(470, 12, 16)
mo.rotation_euler = Vector((0, 0, -1)).rotation_difference((bpos(474, 1, -2) - bpos(470, 12, 16)).normalized()).to_euler()
col_for("Lights").objects.link(mo)
# 할머니 손에서 나는 따뜻한 빛 (숫자가 건너갈 때)
gd = bpy.data.lights.new("TouchGlow", "POINT")
gd.color = (1.0, 0.72, 0.38)
gd.energy = 0
gd.shadow_soft_size = 0.2
gd.use_custom_distance = True
gd.cutoff_distance = 4
go = bpy.data.objects.new("TouchGlow", gd)
col_for("Lights").objects.link(go)

# ------------------------------------------------------------------ 하늘
world = bpy.data.worlds.new("Sky")
scene.world = world
nt, N, L = new_nodes(world)
wout = N.new("ShaderNodeOutputWorld")
day_v = N.new("ShaderNodeValue")
day_v.name = "DAY"
tc = N.new("ShaderNodeTexCoord")
sep = N.new("ShaderNodeSeparateXYZ")
L.new(tc.outputs["Generated"], sep.inputs["Vector"])


def ramp_node(c0, c1, p0=0.5, p1=0.8):
    r = N.new("ShaderNodeValToRGB")
    r.color_ramp.elements[0].position, r.color_ramp.elements[0].color = p0, (*c0, 1)
    r.color_ramp.elements[1].position, r.color_ramp.elements[1].color = p1, (*c1, 1)
    L.new(sep.outputs["Z"], r.inputs["Fac"])
    return r


night_sky = ramp_node((0.07, 0.11, 0.32), (0.008, 0.014, 0.06))
day_sky = ramp_node((1.0, 0.62, 0.36), (0.25, 0.42, 0.85), 0.5, 0.78)   # 늦은 오후: 지평선 주황, 위는 파랑
vor = N.new("ShaderNodeTexVoronoi")
vor.inputs["Scale"].default_value = 150
L.new(tc.outputs["Generated"], vor.inputs["Vector"])
dot = N.new("ShaderNodeMapRange")
dot.inputs["From Min"].default_value = 0.14
dot.inputs["From Max"].default_value = 0.0
dot.inputs["To Max"].default_value = 5.0
L.new(vor.outputs["Distance"], dot.inputs["Value"])
thin = N.new("ShaderNodeMath")
thin.operation = "GREATER_THAN"
thin.inputs[1].default_value = 0.95
L.new(vor.outputs["Color"], thin.inputs[0])
above = N.new("ShaderNodeMath")
above.operation = "GREATER_THAN"
above.inputs[1].default_value = 0.53
L.new(sep.outputs["Z"], above.inputs[0])
nightness = N.new("ShaderNodeMath")
nightness.operation = "SUBTRACT"
nightness.inputs[0].default_value = 1.0
L.new(day_v.outputs[0], nightness.inputs[1])
m1 = N.new("ShaderNodeMath")
m1.operation = "MULTIPLY"
L.new(dot.outputs["Result"], m1.inputs[0])
L.new(thin.outputs["Value"], m1.inputs[1])
m2 = N.new("ShaderNodeMath")
m2.operation = "MULTIPLY"
L.new(m1.outputs["Value"], m2.inputs[0])
L.new(above.outputs["Value"], m2.inputs[1])
m3 = N.new("ShaderNodeMath")
m3.operation = "MULTIPLY"
L.new(m2.outputs["Value"], m3.inputs[0])
L.new(nightness.outputs["Value"], m3.inputs[1])
skymix = N.new("ShaderNodeMix")
skymix.data_type = "RGBA"
L.new(day_v.outputs[0], skymix.inputs["Factor"])
L.new(night_sky.outputs["Color"], skymix.inputs["A"])
L.new(day_sky.outputs["Color"], skymix.inputs["B"])
addstars = N.new("ShaderNodeMix")
addstars.data_type = "RGBA"
addstars.blend_type = "ADD"
L.new(m3.outputs["Value"], addstars.inputs["Factor"])
L.new(skymix.outputs["Result"], addstars.inputs["A"])
addstars.inputs["B"].default_value = (1.0, 0.95, 0.85, 1)
bg_cam = N.new("ShaderNodeBackground")
L.new(addstars.outputs["Result"], bg_cam.inputs["Color"])
lightmix = N.new("ShaderNodeMix")
lightmix.data_type = "RGBA"
L.new(day_v.outputs[0], lightmix.inputs["Factor"])
lightmix.inputs["A"].default_value = (0.05, 0.08, 0.22, 1)
lightmix.inputs["B"].default_value = (0.42, 0.42, 0.55, 1)
bg_light = N.new("ShaderNodeBackground")
L.new(lightmix.outputs["Result"], bg_light.inputs["Color"])
lp = N.new("ShaderNodeLightPath")
mixs = N.new("ShaderNodeMixShader")
L.new(lp.outputs["Is Camera Ray"], mixs.inputs["Fac"])
L.new(bg_light.outputs["Background"], mixs.inputs[1])
L.new(bg_cam.outputs["Background"], mixs.inputs[2])
L.new(mixs.outputs["Shader"], wout.inputs["Surface"])

# ------------------------------------------------------------------ 배우
rigs = {}
for line in sec["C"].split("\n"):
    if not line:
        continue
    f = line.split("|")
    if f[0] == "R":
        rigs[f[1]] = {"joints": {k: tuple(map(float, v.split(","))) for k, v in zip(("LA", "RA", "LL", "RL", "HD"), f[2:7])}, "parts": []}
    else:
        _, rname, g, pname, k, size, pos, q, col, rmat, tr = f
        rigs[rname]["parts"].append((g, pname, k, tuple(map(float, size.split(","))), tuple(map(float, pos.split(","))),
                                     tuple(map(float, q.split(","))), col, rmat, float(tr)))

font_ink = bpy.data.fonts.load(FONT_INK)
ink_mat = bpy.data.materials.new("Ink")
nt, N, L = new_nodes(ink_mat)
o = N.new("ShaderNodeOutputMaterial")
b = N.new("ShaderNodeBsdfPrincipled")
oi = N.new("ShaderNodeObjectInfo")
L.new(oi.outputs["Color"], b.inputs["Base Color"])
L.new(oi.outputs["Color"], b.inputs["Emission Color"])
at = N.new("ShaderNodeAttribute")
at.attribute_type = "OBJECT"
at.attribute_name = "emit"
L.new(at.outputs["Fac"], b.inputs["Emission Strength"])
b.inputs["Roughness"].default_value = 0.55
L.new(b.outputs["BSDF"], o.inputs["Surface"])

cast_col = col_for("Cast")
chars = {}
instances = dict(SH.INSTANCES)
for base in rigs:
    instances.setdefault(base, base)
for inst, base in instances.items():
    rig = rigs[base]
    parts = []
    head = None
    larm = None
    for i, (g, pname, k, (sx, sy, sz), pos, q, col, rmat, tr) in enumerate(rig["parts"]):
        bx, by, bz = sx, sz, sy
        transparent = tr > 0.05
        mat = get_mat(rmat, transparent, True)
        Rm = Matrix.Translation(bpos(*pos)) @ brot(*q).to_4x4()
        if k in ("B", "M", "H") and min(bx, by, bz) > 0.12:
            me = bpy.data.meshes.new(f"{inst}_{i}")
            me.from_pydata([(v[0] * bx, v[1] * by, v[2] * bz) for v in CUBE_V], [], CUBE_F)
            me.update()
            ob = bpy.data.objects.new(f"{inst}#{i}", me)
            bev = ob.modifiers.new("bevel", "BEVEL")
            if k == "H":
                bev.width, bev.segments = 0.32, 6
                for p in me.polygons:
                    p.use_smooth = True
            else:
                bev.width, bev.segments = min(0.09, min(bx, by, bz) * 0.25), 3
            bev.limit_method = "NONE"
            me.materials.append(mat)
            sc = (1.0, 1.0, 1.0)
        else:
            if k == "C":
                d = min(by, bz)
                by, bz = d, d
            ob = bpy.data.objects.new(f"{inst}#{i}", unit_mesh("B" if k in ("M", "H") else k))
            link_obj_mat(ob, mat)
            sc = (bx, by, bz)
        ob.color = (*lin(col), (1 - tr) * (0.4 if tr >= 0.5 else 1.0) if transparent else 1.0)
        ob["emit"] = 0.6 if rmat == "Neon" else 0.0
        ob.hide_render = True
        cast_col.objects.link(ob)
        parts.append({"ob": ob.name, "g": g, "name": pname, "M": [list(r) for r in (Rm @ Matrix.Diagonal((*sc, 1)))],
                      "col": lin(col), "a": ob.color[3]})
        if k == "H" or pname == "Head":
            head = {"idx": len(parts) - 1, "size": (sx, sz, sy), "R": [list(r) for r in Rm]}
        if pname == "LeftLowerArm":
            larm = {"idx": len(parts) - 1, "size": (sx, sy, sz), "R": [list(r) for r in Rm]}
    pool = {"B": [], "C": []}
    for kk, cnt in (("B", 22), ("C", 10)):
        for j in range(cnt):
            ob = bpy.data.objects.new(f"{inst}#F{kk}{j}", unit_mesh(kk))
            link_obj_mat(ob, get_mat("SmoothPlastic", False, True))
            ob.hide_render = True
            cast_col.objects.link(ob)
            pool[kk].append(ob.name)
    cu = bpy.data.curves.new(f"{inst}_num", "FONT")
    cu.body = "0:00:00"
    cu.font = font_ink
    cu.align_x, cu.align_y = "CENTER", "CENTER"
    cu.size = 0.24
    cu.extrude = 0.004
    cu.materials.append(ink_mat)
    num = bpy.data.objects.new(f"{inst}#NUM", cu)
    num.hide_render = True
    num.color = (0.03, 0.035, 0.08, 1)
    num["emit"] = 0.0
    cast_col.objects.link(num)
    J = {k: list(bpos(*v)) for k, v in rig["joints"].items()}
    chars[inst] = {"base": base, "parts": parts, "head": head, "larm": larm, "pool": pool, "num": num.name, "joints": J}
    print("cast", inst, len(parts))

# ------------------------------------------------------------------ 카메라
cam_d = bpy.data.cameras.new("FilmCam")
cam_d.sensor_fit = "HORIZONTAL"
cam_d.clip_start = 0.05
cam_d.clip_end = 5000
cam_d.dof.use_dof = True
cam = bpy.data.objects.new("FilmCam", cam_d)
scene.collection.objects.link(cam)
scene.camera = cam
fill_d = bpy.data.lights.new("CamFill", "AREA")
fill_d.energy, fill_d.size, fill_d.color = 160, 4, (0.95, 0.95, 1.0)
fill_d.use_custom_distance, fill_d.cutoff_distance, fill_d.use_shadow = True, 25, False
fill = bpy.data.objects.new("CamFill", fill_d)
fill.parent = cam
fill.location = (2.5, 1.8, 0.5)
col_for("Lights").objects.link(fill)
get_mat("Neon", False, True)
get_mat("SmoothPlastic", False, True)

import json  # noqa: E402
scene["chars"] = json.dumps(chars)
scene["lights"] = json.dumps(lights)
scene["dyn"] = json.dumps(dyn)

total = int(round(SH.TOTAL * 30))
scene.render.engine = "BLENDER_EEVEE"
ee = scene.eevee
ee.taa_render_samples = 24
ee.use_shadows = True
ee.shadow_pool_size = "1024"
ee.shadow_ray_count = 1
ee.shadow_step_count = 6
ee.use_raytracing = True
ee.use_fast_gi = True
scene.render.use_motion_blur = False
scene.render.resolution_x, scene.render.resolution_y = 1080, 1920
scene.render.resolution_percentage = 100
scene.render.fps = 30
scene.frame_start, scene.frame_end = 1, total
scene.render.filepath = os.path.join(FRAMES_DIR, "f")
scene.render.image_settings.file_format = "PNG"
scene.render.use_overwrite = False
scene.render.use_placeholder = True
try:
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
except Exception as e:
    print("color mgmt:", e)
try:
    ng = bpy.data.node_groups.new("FilmComp", "CompositorNodeTree")
    ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    rl = ng.nodes.new("CompositorNodeRLayers")
    gl = ng.nodes.new("CompositorNodeGlare")
    gout = ng.nodes.new("NodeGroupOutput")
    for nm, val in (("Type", "Bloom"), ("Quality", "High"), ("Threshold", 1.0), ("Strength", 0.5), ("Size", 0.8)):
        gl.inputs[nm].default_value = val
    ng.links.new(rl.outputs["Image"], gl.inputs["Image"])
    ng.links.new(gl.outputs["Image"], gout.inputs[0])
    scene.compositing_node_group = ng
except Exception as e:
    print("compositor:", e)
os.makedirs(FRAMES_DIR, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print("SAVED", OUT_BLEND, "objects", len(scene.objects), "frames", total)
