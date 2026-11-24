"""별이 떨어지는 마을: Roblox Studio에서 뽑은 장면 데이터(scene_export.txt)를 블렌더 장면으로 다시 짓는다.

사용법 (창 없이):
  blender --background --factory-startup --python build_scene.py -- <scene_export.txt> <out.blend>

좌표 변환: Roblox (X, Y위, Z) -> Blender (X, -Z, Y위). 1 스터드 = 1 블렌더 단위.
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
EXPORT = argv[0] if len(argv) > 0 else os.path.join(os.path.dirname(__file__), "scene_export.txt")
OUT_BLEND = argv[1] if len(argv) > 1 else os.path.join(os.path.dirname(__file__), "town_test.blend")
FRAMES_DIR = os.path.join(os.path.dirname(OUT_BLEND), "frames")
FONT_PATH = r"C:\Windows\Fonts\malgunbd.ttf"
random.seed(7)

C = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))


def bpos(x, y, z):
    return Vector((x, -z, y))


def brot(w, x, y, z):
    return C @ Quaternion((w, x, y, z)).to_matrix() @ C.transposed()


def hex_rgb(h):
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    # sRGB -> linear
    return tuple(((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92 for c in (r, g, b))


# ------------------------------------------------------------------ 데이터 읽기
text = open(EXPORT, encoding="utf-8").read()
sections = {}
for chunk in text.split("\n#\n"):
    key = chunk.split(";", 1)[0] if not chunk.startswith("P;") else "P"
    sections[key] = chunk

# ------------------------------------------------------------------ 빈 장면
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.name = "StarTown"


def coll(name):
    c = bpy.data.collections.new(name)
    scene.collection.children.link(c)
    return c


COLS = {}


def col_for(tag):
    if tag not in COLS:
        COLS[tag] = coll(tag)
    return COLS[tag]


# ------------------------------------------------------------------ 기본 메시 (단위 크기, 원점 중심)
def mesh_from(name, verts, faces, smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    for p in me.polygons:
        p.use_smooth = smooth
    return me


h = 0.5
MESH_CUBE = mesh_from("u_cube", [(-h, -h, -h), (h, -h, -h), (h, h, -h), (-h, h, -h), (-h, -h, h), (h, -h, h), (h, h, h), (-h, h, h)],
                      [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)])
# Roblox 쐐기: 아래는 꽉 차고, 윗변은 Roblox 로컬 +Z 쪽(블렌더 로컬 -Y)
MESH_WEDGE = mesh_from("u_wedge", [(-h, -h, -h), (h, -h, -h), (h, h, -h), (-h, h, -h), (-h, -h, h), (h, -h, h)],
                       [(0, 3, 2, 1), (0, 1, 5, 4), (1, 2, 5), (0, 4, 3), (3, 4, 5, 2)])


def make_cylinder():
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=28, radius1=0.5, radius2=0.5, depth=1.0)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90), 3, "Y"))
    me = bpy.data.meshes.new("u_cyl")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = len(p.vertices) == 4
    return me


def make_sphere():
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=14, radius=0.5)
    me = bpy.data.meshes.new("u_sphere")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return me


MESH_CYL = make_cylinder()
MESH_SPHERE = make_sphere()

# ------------------------------------------------------------------ 재질
MATS = {}

# Roblox 재질 -> (거칠기, 금속성, 무늬, 무늬 크기, 무늬 세기, 요철)
MAT_INFO = {
    "SmoothPlastic": (0.42, 0, "noise", 0.6, 0.04, 0.0),
    "Plastic": (0.5, 0, "noise", 0.6, 0.05, 0.02),
    "Neon": (0.5, 0, "none", 1, 0, 0),
    "Wood": (0.62, 0, "wave", 0.9, 0.18, 0.05),
    "WoodPlanks": (0.66, 0, "planks", 0.35, 0.22, 0.08),
    "Cobblestone": (0.85, 0, "voronoi", 0.55, 0.35, 0.25),
    "Brick": (0.82, 0, "voronoi", 0.9, 0.25, 0.15),
    "Slate": (0.8, 0, "noise", 0.35, 0.22, 0.12),
    "Concrete": (0.88, 0, "noise", 0.8, 0.12, 0.06),
    "Sand": (0.9, 0, "noise", 1.6, 0.1, 0.05),
    "Rock": (0.9, 0, "noise", 0.3, 0.25, 0.2),
    "Ground": (0.92, 0, "noise", 0.4, 0.2, 0.1),
    "Grass": (0.9, 0, "noise", 0.25, 0.25, 0.08),
    "LeafyGrass": (0.9, 0, "noise", 0.25, 0.25, 0.08),
    "Fabric": (0.92, 0, "noise", 3.0, 0.08, 0.04),
    "Glass": (0.05, 0, "none", 1, 0, 0),
    "Marble": (0.3, 0, "noise", 0.5, 0.08, 0.0),
    "Metal": (0.35, 0.85, "noise", 1.0, 0.06, 0.02),
    "DiamondPlate": (0.35, 0.85, "noise", 1.0, 0.06, 0.02),
}


def new_nodes(mat):
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    return nt, nt.nodes, nt.links


def get_mat(rbx_mat, transparent=False, character=False):
    key = (rbx_mat, transparent, character)
    if key in MATS:
        return MATS[key]
    rough, metal, pattern, pscale, pstrength, bump = MAT_INFO.get(rbx_mat, MAT_INFO["SmoothPlastic"])
    if character:  # 캐릭터: 무늬 없음, 반사 줄여서 검은 눈이 회색으로 뜨지 않게
        pattern, bump = "none", 0
        rough = max(rough, 0.6)
    mat = bpy.data.materials.new(f"R_{rbx_mat}{'_T' if transparent else ''}{'_C' if character else ''}")
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
        if pattern == "noise":
            tex = N.new("ShaderNodeTexNoise")
            tex.inputs["Scale"].default_value = pscale
            tex.inputs["Detail"].default_value = 6
            L.new(geo.outputs["Position"], tex.inputs["Vector"])
            fac = tex.outputs["Fac"]
        elif pattern == "wave":
            tex = N.new("ShaderNodeTexWave")
            tex.inputs["Scale"].default_value = pscale
            tex.inputs["Distortion"].default_value = 6
            tex.inputs["Detail"].default_value = 3
            L.new(geo.outputs["Position"], tex.inputs["Vector"])
            fac = tex.outputs["Fac"]
        elif pattern == "planks":
            tex = N.new("ShaderNodeTexWave")
            tex.wave_profile = "SAW"
            tex.inputs["Scale"].default_value = pscale
            tex.inputs["Distortion"].default_value = 1.5
            L.new(geo.outputs["Position"], tex.inputs["Vector"])
            fac = tex.outputs["Fac"]
        else:  # voronoi: 돌 사이 줄눈
            tex = N.new("ShaderNodeTexVoronoi")
            tex.feature = "DISTANCE_TO_EDGE"
            tex.inputs["Scale"].default_value = pscale
            L.new(geo.outputs["Position"], tex.inputs["Vector"])
            ramp = N.new("ShaderNodeMapRange")
            ramp.inputs["From Min"].default_value = 0.0
            ramp.inputs["From Max"].default_value = 0.08
            L.new(tex.outputs["Distance"], ramp.inputs["Value"])
            fac = ramp.outputs["Result"]
        # 색 = 물체색 * (1 - 세기 + 세기 * 무늬)
        mr = N.new("ShaderNodeMapRange")
        mr.inputs["To Min"].default_value = 1 - pstrength
        mr.inputs["To Max"].default_value = 1.0
        L.new(fac, mr.inputs["Value"])
        mix = N.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
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
        if rbx_mat == "Glass":
            bsdf.inputs["Specular IOR Level"].default_value = 0.9
    MATS[key] = mat
    return mat


# ------------------------------------------------------------------ 조각 만들기
EMIT = {"Houses": 3.2, "Props": 10.0, "HaruRoom": 8.0, "Haru": 0.6, "Trees": 0, "default": 6.0}
SKIP_NAMES = set()
counts = {}
haru_objs = []


def unique_box(name, sx, sy, sz, bevel, segs=3):
    me = MESH_CUBE.copy()
    me.name = name
    for v in me.vertices:
        v.co = Vector((v.co.x * sx, v.co.y * sy, v.co.z * sz))
    return me


for line in sections["P"][2:].split("\n"):
    if not line:
        continue
    k, tag, size, pos, q, col, rmat, tr = line.split("|")
    sx, sy, sz = map(float, size.split(","))
    px, py, pz = map(float, pos.split(","))
    qw, qx, qy, qz = map(float, q.split(","))
    tr = float(tr)
    if k == "U" and sx * sy * sz < 30:
        continue  # 작은 합친 조각(횃불 불꽃 등)은 건너뜀
    rot = brot(qw, qx, qy, qz).to_4x4()
    loc = Matrix.Translation(bpos(px, py, pz))
    is_char = tag == "Haru"
    # 블렌더 로컬 크기: x=sx, y=sz, z=sy
    bx, by, bz = sx, sz, sy
    if is_char and k in ("B", "M", "H") and min(sx, sy, sz) > 0.12:
        me = unique_box(f"char_{len(haru_objs)}", bx, by, bz, 0)
        ob = bpy.data.objects.new(me.name, me)
        bev = ob.modifiers.new("bevel", "BEVEL")
        bev.width = 0.32 if k == "H" else min(0.09, min(bx, by, bz) * 0.25)
        bev.segments = 6 if k == "H" else 3
        bev.limit_method = "NONE"
        if k == "H":
            ob.modifiers.new("smooth", "SUBSURF").levels = 0
            for p in me.polygons:
                p.use_smooth = True
        ob.matrix_world = loc @ rot
    else:
        if k in ("W", "K"):
            me = MESH_WEDGE
        elif k == "C":
            me = MESH_CYL
            d = min(sy, sz)
            by, bz = d, d
        elif k == "S":
            me = MESH_SPHERE
        else:
            me = MESH_CUBE
        ob = bpy.data.objects.new(f"{tag}_{k}", me)
        ob.matrix_world = loc @ rot @ Matrix.Diagonal((bx, by, bz, 1))
    r, g, b = hex_rgb(col)
    alpha = 1 - tr
    transparent = alpha < 0.9
    ob.color = (r, g, b, alpha if transparent else 1.0)
    if is_char:  # 캐릭터 조각은 메시가 각자 따로라 메시에 바로 재질을 붙임
        ob.data.materials.append(get_mat(rmat, transparent, True))
    ob["emit"] = (EMIT.get(tag, EMIT["default"]) if rmat == "Neon" else 0.0)
    col_for(tag).objects.link(ob)
    ob["rbx_mat"] = rmat
    ob["transparent"] = transparent
    if is_char:
        haru_objs.append(ob)
    counts[tag] = counts.get(tag, 0) + 1

# 공유 메시는 재질 슬롯을 오브젝트 연결로 바꿔 각자 다른 재질을 갖게 함
for me in (MESH_CUBE, MESH_WEDGE, MESH_CYL, MESH_SPHERE):
    me.materials.clear()
    me.materials.append(None)
for ob in scene.objects:
    if ob.type == "MESH" and ob.data in (MESH_CUBE, MESH_WEDGE, MESH_CYL, MESH_SPHERE):
        ob.material_slots[0].link = "OBJECT"
        ob.material_slots[0].material = get_mat(ob["rbx_mat"], bool(ob["transparent"]), False)
print("parts", counts)

# ------------------------------------------------------------------ 지형
_, X0, X1, Z0, Z1, STEP, *rows = sections["T"].split(";")
X0, X1, Z0, Z1, STEP = map(int, (X0, X1, Z0, Z1, STEP))
TCOL = {"g": (0.075, 0.16, 0.035), "l": (0.09, 0.19, 0.04), "r": (0.13, 0.13, 0.14), "s": (0.8, 0.83, 0.9), "d": (0.12, 0.08, 0.045)}
verts, cols, faces = [], [], []
grid = [row.split(",") for row in rows]
nz, nx = len(grid), len(grid[0])
for iz, row in enumerate(grid):
    for ix, tok in enumerate(row):
        hgt = int(tok[:-1]) / 10.0
        verts.append(bpos(X0 + ix * STEP, hgt - 0.15, Z0 + iz * STEP))
        cols.append(TCOL.get(tok[-1], TCOL["g"]))
for iz in range(nz - 1):
    for ix in range(nx - 1):
        a = iz * nx + ix
        faces.append((a, a + 1, a + nx + 1, a + nx))
tme = bpy.data.meshes.new("terrain")
tme.from_pydata(verts, [], faces)
tme.update()
for p in tme.polygons:
    p.use_smooth = True
ca = tme.color_attributes.new("tcol", "FLOAT_COLOR", "POINT")
for i, c in enumerate(cols):
    ca.data[i].color = (*c, 1)
tob = bpy.data.objects.new("Terrain", tme)
tob.modifiers.new("subd", "SUBSURF").render_levels = 2
tmat = bpy.data.materials.new("Terrain")
nt, N, L = new_nodes(tmat)
out = N.new("ShaderNodeOutputMaterial")
bsdf = N.new("ShaderNodeBsdfPrincipled")
attr = N.new("ShaderNodeAttribute")
attr.attribute_name = "tcol"
geo = N.new("ShaderNodeNewGeometry")
noise = N.new("ShaderNodeTexNoise")
noise.inputs["Scale"].default_value = 0.08
noise.inputs["Detail"].default_value = 8
L.new(geo.outputs["Position"], noise.inputs["Vector"])
mr = N.new("ShaderNodeMapRange")
mr.inputs["To Min"].default_value = 0.7
mr.inputs["To Max"].default_value = 1.15
L.new(noise.outputs["Fac"], mr.inputs["Value"])
mix = N.new("ShaderNodeMix")
mix.data_type = "RGBA"
mix.blend_type = "MULTIPLY"
mix.inputs["Factor"].default_value = 1
L.new(attr.outputs["Color"], mix.inputs["A"])
L.new(mr.outputs["Result"], mix.inputs["B"])
L.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
bsdf.inputs["Roughness"].default_value = 0.92
bump = N.new("ShaderNodeBump")
bump.inputs["Strength"].default_value = 0.15
L.new(noise.outputs["Fac"], bump.inputs["Height"])
L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
tme.materials.append(tmat)
col_for("Terrain").objects.link(tob)

# ------------------------------------------------------------------ 간판 글자
font = None
if os.path.exists(FONT_PATH):
    font = bpy.data.fonts.load(FONT_PATH)
tx_entries = [e for e in sections.get("X", "X;").split(";")[1:] if e]
for e in tx_entries:
    face, size, pos, q, body = e.split("|", 4)
    sx, sy, sz = map(float, size.split(","))
    px, py, pz = map(float, pos.split(","))
    qw, qx, qy, qz = map(float, q.split(","))
    body = body.replace("\\n", "\n")
    cu = bpy.data.curves.new("sign", "FONT")
    cu.body = body
    if font:
        cu.font = font
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    lines = body.count("\n") + 1
    cu.size = sy * (0.33 if lines > 1 else 0.55)
    cu.extrude = 0.02
    ob = bpy.data.objects.new("SignText", cu)
    # 글자 x -> 조각 로컬 -x, 글자 y -> 로컬 +z(위), 글자 앞면 -> 로컬 +y (Roblox 앞면 -Z)
    frame = Matrix(((-1, 0, 0), (0, 0, 1), (0, 1, 0))).transposed().to_4x4()
    offs = Matrix.Translation(Vector((0, sz / 2 + 0.03, 0)))
    ob.matrix_world = Matrix.Translation(bpos(px, py, pz)) @ brot(qw, qx, qy, qz).to_4x4() @ offs @ frame
    dark = "병뚜껑" in body
    m = bpy.data.materials.new("SignInk")
    nt, N, L = new_nodes(m)
    o = N.new("ShaderNodeOutputMaterial")
    b = N.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = (0.05, 0.025, 0.015, 1) if dark else (1.0, 0.82, 0.5, 1)
    if not dark:
        b.inputs["Emission Color"].default_value = (1.0, 0.82, 0.5, 1)
        b.inputs["Emission Strength"].default_value = 0.6
    L.new(b.outputs["BSDF"], o.inputs["Surface"])
    cu.materials.append(m)
    col_for("Props").objects.link(ob)

# ------------------------------------------------------------------ 조명
lights = [e for e in sections.get("L", "L;").split(";")[1:] if e]
for i, e in enumerate(lights):
    pos, colh, bright, rng = e.split("|")
    px, py, pz = map(float, pos.split(","))
    ld = bpy.data.lights.new(f"lamp{i}", "POINT")
    ld.color = hex_rgb(colh)
    rng = float(rng)
    ld.energy = float(bright) * rng * rng * 2.2
    ld.shadow_soft_size = 0.35
    ld.use_custom_distance = True
    ld.cutoff_distance = rng * 3
    ld.use_shadow = (i % 4 == 0)  # 그림자 메모리 절약: 네 개 중 하나만 그림자
    lo = bpy.data.objects.new(f"lamp{i}", ld)
    lo.location = bpos(px, py, pz)
    col_for("Lights").objects.link(lo)
# 달빛
md = bpy.data.lights.new("moon", "SUN")
md.energy = 1.1
md.color = (0.55, 0.66, 1.0)
md.angle = math.radians(3)
mo = bpy.data.objects.new("moon", md)
moon_dir = bpos(0.96, 0.32, 0.2).normalized()
mo.rotation_euler = Vector((0, 0, 1)).rotation_difference(moon_dir).to_euler()
col_for("Lights").objects.link(mo)

# ------------------------------------------------------------------ 밤하늘 + 별
world = bpy.data.worlds.new("NightSky")
scene.world = world
nt, N, L = new_nodes(world)
wout = N.new("ShaderNodeOutputWorld")
tc = N.new("ShaderNodeTexCoord")
sep = N.new("ShaderNodeSeparateXYZ")
L.new(tc.outputs["Generated"], sep.inputs["Vector"])
ramp = N.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].position = 0.5
ramp.color_ramp.elements[0].color = (0.06, 0.12, 0.36, 1)
ramp.color_ramp.elements[1].position = 0.8
ramp.color_ramp.elements[1].color = (0.008, 0.016, 0.07, 1)
L.new(sep.outputs["Z"], ramp.inputs["Fac"])
vor = N.new("ShaderNodeTexVoronoi")
vor.inputs["Scale"].default_value = 260
L.new(tc.outputs["Generated"], vor.inputs["Vector"])
star_mask = N.new("ShaderNodeMapRange")
star_mask.inputs["From Min"].default_value = 0.06
star_mask.inputs["From Max"].default_value = 0.0
star_mask.inputs["To Max"].default_value = 3.0
L.new(vor.outputs["Distance"], star_mask.inputs["Value"])
thin = N.new("ShaderNodeMath")  # 별 일부만 남김
thin.operation = "GREATER_THAN"
thin.inputs[1].default_value = 0.72
L.new(vor.outputs["Color"], thin.inputs[0])
above = N.new("ShaderNodeMath")
above.operation = "GREATER_THAN"
above.inputs[1].default_value = 0.52
L.new(sep.outputs["Z"], above.inputs[0])
m1 = N.new("ShaderNodeMath")
m1.operation = "MULTIPLY"
L.new(star_mask.outputs["Result"], m1.inputs[0])
L.new(thin.outputs["Value"], m1.inputs[1])
m2 = N.new("ShaderNodeMath")
m2.operation = "MULTIPLY"
L.new(m1.outputs["Value"], m2.inputs[0])
L.new(above.outputs["Value"], m2.inputs[1])
add = N.new("ShaderNodeMix")
add.data_type = "RGBA"
add.blend_type = "ADD"
L.new(m2.outputs["Value"], add.inputs["Factor"])
L.new(ramp.outputs["Color"], add.inputs["A"])
add.inputs["B"].default_value = (1.0, 0.95, 0.85, 1)
bg_cam = N.new("ShaderNodeBackground")
L.new(add.outputs["Result"], bg_cam.inputs["Color"])
bg_light = N.new("ShaderNodeBackground")
bg_light.inputs["Color"].default_value = (0.05, 0.085, 0.24, 1)
bg_light.inputs["Strength"].default_value = 1.0
lp = N.new("ShaderNodeLightPath")
mixs = N.new("ShaderNodeMixShader")
L.new(lp.outputs["Is Camera Ray"], mixs.inputs["Fac"])
L.new(bg_light.outputs["Background"], mixs.inputs[1])
L.new(bg_cam.outputs["Background"], mixs.inputs[2])
L.new(mixs.outputs["Shader"], wout.inputs["Surface"])
# 옅은 안개 (가로등 빛 번짐 + 먼 산 흐림)
vol = N.new("ShaderNodeVolumeScatter")
vol.inputs["Density"].default_value = 0.00035
vol.inputs["Color"].default_value = (0.4, 0.55, 1.0, 1)
vol.inputs["Anisotropy"].default_value = 0.35
# 안개는 연결하지 않음: EEVEE 볼륨이 먼 하늘과 산을 검게 덮어버림 (테스트로 확인)

# ------------------------------------------------------------------ 떨어지는 별
STAR_MAT = bpy.data.materials.new("FallingStar")
nt, N, L = new_nodes(STAR_MAT)
o = N.new("ShaderNodeOutputMaterial")
em = N.new("ShaderNodeEmission")
em.inputs["Color"].default_value = (1.0, 0.7, 0.28, 1)
em.inputs["Strength"].default_value = 8
L.new(em.outputs["Emission"], o.inputs["Surface"])
TAIL_MAT = bpy.data.materials.new("StarTail")
nt, N, L = new_nodes(TAIL_MAT)
o = N.new("ShaderNodeOutputMaterial")
tc = N.new("ShaderNodeTexCoord")
sep = N.new("ShaderNodeSeparateXYZ")
L.new(tc.outputs["Generated"], sep.inputs["Vector"])
inv = N.new("ShaderNodeMapRange")
inv.inputs["To Min"].default_value = 1.0
inv.inputs["To Max"].default_value = 0.0
L.new(sep.outputs["Z"], inv.inputs["Value"])
em = N.new("ShaderNodeEmission")
em.inputs["Color"].default_value = (1.0, 0.75, 0.35, 1)
L.new(inv.outputs["Result"], em.inputs["Strength"])
trp = N.new("ShaderNodeBsdfTransparent")
mixs = N.new("ShaderNodeMixShader")
L.new(inv.outputs["Result"], mixs.inputs["Fac"])
L.new(trp.outputs["BSDF"], mixs.inputs[1])
L.new(em.outputs["Emission"], mixs.inputs[2])
add_s = N.new("ShaderNodeAddShader")
L.new(mixs.outputs["Shader"], o.inputs["Surface"])
TAIL_MAT.surface_render_method = "BLENDED"
for n in (em,):
    n.inputs["Strength"].default_value = 2.5

TOTAL_FRAMES = 69
fall_col = col_for("FallingStars")
tail_mesh = bpy.data.meshes.new("tail")
bm = bmesh.new()
bmesh.ops.create_cone(bm, cap_ends=False, segments=10, radius1=0.5, radius2=0.08, depth=1.0)
bm.to_mesh(tail_mesh)
bm.free()
for p in tail_mesh.polygons:
    p.use_smooth = True
tail_mesh.materials.append(TAIL_MAT)
star_mesh = MESH_SPHERE.copy()
star_mesh.name = "star"
star_mesh.materials.clear()
star_mesh.materials.append(STAR_MAT)


def falling_field(cx, cz, radius, n, top, bot, vmin, vmax, smin, smax):
    for i in range(n):
        a = random.uniform(0, math.tau)
        r = radius * math.sqrt(random.random())
        x, z = cx + math.sin(a) * r, cz + math.cos(a) * r
        y0 = random.uniform(bot, top)
        v = random.uniform(vmin, vmax)
        s = random.uniform(smin, smax)
        star = bpy.data.objects.new("star", star_mesh)
        star.scale = (s, s, s)
        tail = bpy.data.objects.new("tail", tail_mesh)
        tail.parent = star
        tail.location = (0, 0, 1.5)
        tail.scale = (0.75, 0.75, 2.6)
        fall_col.objects.link(star)
        fall_col.objects.link(tail)
        for f in (1, TOTAL_FRAMES):
            t = (f - 1) / 30.0
            star.location = bpos(x + math.sin(t * 0.8 + i) * 0.6, y0 - v * t, z)
            star.keyframe_insert("location", frame=f)
        for fc in star.animation_data.action.fcurves if hasattr(star.animation_data.action, "fcurves") else []:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"


falling_field(0, -40, 120, 120, 200, 18, 6, 10, 1.1, 1.9)   # 큰길 위
falling_field(2, 40, 45, 50, 60, 6, 3, 5, 0.6, 1.0)        # 하루 주변 가까운 별

# ------------------------------------------------------------------ 카메라
cam_d = bpy.data.cameras.new("FilmCam")
cam_d.sensor_fit = "HORIZONTAL"
cam_d.clip_start = 0.1
cam_d.clip_end = 6000
cam = bpy.data.objects.new("FilmCam", cam_d)
scene.collection.objects.link(cam)
scene.camera = cam
# 카메라에 붙어 다니는 부드러운 보조광: 가까운 인물 얼굴을 살림 (먼 곳은 닿지 않음)
fill_d = bpy.data.lights.new("CamFill", "AREA")
fill_d.energy = 220
fill_d.size = 4
fill_d.color = (0.85, 0.9, 1.0)
fill_d.use_custom_distance = True
fill_d.cutoff_distance = 22
fill_d.use_shadow = False
fill = bpy.data.objects.new("CamFill", fill_d)
fill.parent = cam
fill.location = (2.5, 1.8, 0.5)
col_for("Lights").objects.link(fill)


def cam_frames(key):
    return [tuple(map(float, f.split(","))) for f in sections[key].split(";")[1:] if f]


frames3, frames4 = cam_frames("C3"), cam_frames("C4")
all_frames = frames3 + frames4
CUT = len(frames3)  # 이 프레임까지가 3번 컷
for i, (px, py, pz, lx, ly, lz, ux, uy, uz, fov) in enumerate(all_frames):
    f = i + 1
    fwd = bpos(lx, ly, lz).normalized()
    up = bpos(ux, uy, uz).normalized()
    right = fwd.cross(up).normalized()
    up = right.cross(fwd).normalized()
    m = Matrix((right, up, -fwd)).transposed().to_4x4()
    m.translation = bpos(px, py, pz)
    cam.matrix_world = m
    cam.keyframe_insert("location", frame=f)
    cam.keyframe_insert("rotation_euler", frame=f)
    # Studio 창을 90도 눕혀 찍었으므로 Roblox 세로 시야각 = 세로 화면의 가로 시야각
    cam_d.angle = math.radians(fov)
    cam_d.keyframe_insert("lens", frame=f)


def set_interp(idb, interp_default="LINEAR", constant_at=None):
    ad = idb.animation_data
    if not ad or not ad.action:
        return
    curves = []
    act = ad.action
    if hasattr(act, "fcurves"):
        curves = list(act.fcurves)
    else:  # 계층형 액션 (Blender 5.x)
        for layer in act.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    curves += list(cb.fcurves)
    for fc in curves:
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT" if (constant_at and int(round(kp.co.x)) == constant_at) else interp_default


set_interp(cam, constant_at=CUT)
set_interp(cam_d, constant_at=CUT)
for ob in fall_col.objects:
    if ob.animation_data:
        set_interp(ob)

# 하루는 3번 컷에는 없다
for ob in haru_objs:
    ob.hide_render = True
    ob.keyframe_insert("hide_render", frame=1)
    ob.hide_render = False
    ob.keyframe_insert("hide_render", frame=CUT + 1)
    set_interp(ob, "CONSTANT")

# ------------------------------------------------------------------ 렌더 설정
scene.render.engine = "BLENDER_EEVEE"
ee = scene.eevee
ee.taa_render_samples = 64
ee.use_shadows = True
try:
    ee.shadow_pool_size = "1024"
except Exception as e:
    print("shadow pool:", e)
ee.shadow_ray_count = 2
ee.shadow_step_count = 8
ee.use_raytracing = True
try:
    ee.use_fast_gi = True
except Exception:
    pass
ee.volumetric_end = 1400
ee.volumetric_tile_size = "4"
ee.volumetric_samples = 64
ee.use_volumetric_shadows = False
scene.render.use_motion_blur = True
scene.render.motion_blur_shutter = 0.5
try:
    scene.render.motion_blur_position = "START"
except Exception:
    pass
scene.render.resolution_x = 1080
scene.render.resolution_y = 1920
scene.render.resolution_percentage = 100
scene.render.fps = 30
scene.frame_start = 1
scene.frame_end = len(all_frames)
scene.render.filepath = os.path.join(FRAMES_DIR, "f")
scene.render.image_settings.file_format = "PNG"
try:
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
except Exception as e:
    print("color mgmt:", e)
scene.view_settings.exposure = 0.4

# ------------------------------------------------------------------ 합성: 블룸
try:
    ng = bpy.data.node_groups.new("FilmComp", "CompositorNodeTree")
    ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    rl = ng.nodes.new("CompositorNodeRLayers")
    gl = ng.nodes.new("CompositorNodeGlare")
    go = ng.nodes.new("NodeGroupOutput")
    for name, val in (("Type", "Bloom"), ("Quality", "High"), ("Threshold", 1.0), ("Strength", 0.55), ("Size", 0.8)):
        try:
            gl.inputs[name].default_value = val
        except Exception as e:
            print("glare", name, e)
    ng.links.new(rl.outputs["Image"], gl.inputs["Image"])
    ng.links.new(gl.outputs["Image"], go.inputs[0])
    scene.compositing_node_group = ng
except Exception as e:
    print("compositor setup failed:", e)

os.makedirs(FRAMES_DIR, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print("SAVED", OUT_BLEND, "objects", len(scene.objects), "frames", scene.frame_end, "cut", CUT)
