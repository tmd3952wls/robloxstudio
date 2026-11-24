"""별이 떨어지는 마을 — 전체 영화 장면 짓기.

입력: world_export.txt (고정 세트), bake_export.txt (76컷 프레임 기록)
출력: town_film.blend + film_data.pkl (프레임별 데이터, film_runtime.py 가 렌더 중에 읽음)

사용법:
  blender --background --factory-startup --python build_film.py -- <폴더>
"""
import math
import os
import pickle
import sys

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
DIR = argv[0] if argv else os.path.dirname(os.path.abspath(__file__))
WORLD = os.path.join(DIR, "world_export.txt")
BAKE = os.path.join(DIR, "bake_export.txt")
OUT_BLEND = os.path.join(DIR, "town_film.blend")
OUT_DATA = os.path.join(DIR, "film_data.pkl")
RUNTIME = os.path.join(DIR, "film_runtime.py")
FRAMES_DIR = os.path.join(DIR, "frames_full")
FONT_PATH = r"C:\Windows\Fonts\malgunbd.ttf"

C = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))


def bpos(x, y, z):
    return Vector((x, -z, y))


def brot(w, x, y, z):
    """Roblox 조각 회전 -> 블렌더 (로컬 축도 같이 변환: 로컬 크기 x=sx, y=sz, z=sy)"""
    return C @ Quaternion((w, x, y, z)).to_matrix() @ C.transposed()


def bcam(w, x, y, z):
    """Roblox 카메라 회전 -> 블렌더 카메라 (둘 다 -Z 가 앞, +Y 가 위)"""
    return C @ Quaternion((w, x, y, z)).to_matrix()


def lin(h):
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return tuple(((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92 for c in (r, g, b))


# ------------------------------------------------------------------ 빈 장면
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.name = "StarTown"
COLS = {}


def col_for(tag):
    if tag not in COLS:
        c = bpy.data.collections.new(tag)
        scene.collection.children.link(c)
        COLS[tag] = c
    return COLS[tag]


# ------------------------------------------------------------------ 단위 메시
def mesh_from(name, verts, faces, smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    for p in me.polygons:
        p.use_smooth = smooth
    return me


h = 0.5
CUBE_V = [(-h, -h, -h), (h, -h, -h), (h, h, -h), (-h, h, -h), (-h, -h, h), (h, -h, h), (h, h, h), (-h, h, h)]
CUBE_F = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
MESH_CUBE = mesh_from("u_cube", CUBE_V, CUBE_F)
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
SHARED = (MESH_CUBE, MESH_WEDGE, MESH_CYL, MESH_SPHERE)


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
    "Marble": (0.3, 0, "noise", 0.5, 0.08, 0.0), "Metal": (0.35, 0.85, "noise", 1.0, 0.06, 0.02),
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


for me in SHARED:
    me.materials.append(None)

# 먼 산: 빛을 받지 않는 실루엣. 밤/낮 색은 실행 스크립트가 DAY 값으로 바꿈
FAR_MAT = bpy.data.materials.new("FarMtn")
nt, N, L = new_nodes(FAR_MAT)
o = N.new("ShaderNodeOutputMaterial")
oi = N.new("ShaderNodeObjectInfo")
dv = N.new("ShaderNodeValue")
dv.name = "DAY"
dv.outputs[0].default_value = 0.0
mx = N.new("ShaderNodeMix")
mx.data_type = "RGBA"
L.new(dv.outputs[0], mx.inputs["Factor"])
mx.inputs["A"].default_value = (0.045, 0.07, 0.17, 1)
mx.inputs["B"].default_value = (1.4, 1.6, 1.9, 1)
mul = N.new("ShaderNodeMix")
mul.data_type = "RGBA"
mul.blend_type = "MULTIPLY"
mul.inputs["Factor"].default_value = 1
L.new(mx.outputs["Result"], mul.inputs["A"])
L.new(oi.outputs["Color"], mul.inputs["B"])
em = N.new("ShaderNodeEmission")
L.new(mul.outputs["Result"], em.inputs["Color"])
L.new(em.outputs["Emission"], o.inputs["Surface"])

# ------------------------------------------------------------------ 고정 세트
wtext = open(WORLD, encoding="utf-8").read()
sec = {}
for chunk in wtext.split("\n#\n"):
    sec["P" if chunk.startswith("P;") else chunk.split(";", 1)[0]] = chunk
EMIT = {"Houses": 3.2, "Props": 10.0, "HaruRoom": 8.0, "default": 6.0}
dyn_objs = {"LampStar": [], "RoomStar": [], "RoomLid": [], "Window": [], "Loaf": []}
counts = {}
for line in sec["P"][2:].split("\n"):
    if not line:
        continue
    k, tag, size, pos, q, col, rmat, tr, dyn = line.split("|")
    sx, sy, sz = map(float, size.split(","))
    tr = float(tr)
    if k == "U" and sx * sy * sz < 30:
        continue
    bx, by, bz = sx, sz, sy
    me = unit_mesh(k)
    if k == "C":
        d = min(sy, sz)
        by, bz = d, d
    ob = bpy.data.objects.new(f"{tag}_{k}", me)
    ob.matrix_world = Matrix.Translation(bpos(*map(float, pos.split(",")))) @ brot(*map(float, q.split(","))).to_4x4() @ Matrix.Diagonal((bx, by, bz, 1))
    alpha = 1 - tr
    transparent = alpha < 0.9
    ob.color = (*lin(col), alpha if transparent else 1.0)
    ob["emit"] = EMIT.get(tag, EMIT["default"]) if rmat == "Neon" else 0.0
    col_for(tag).objects.link(ob)
    link_obj_mat(ob, FAR_MAT if tag == "FarMountains" else get_mat(rmat, transparent))
    if tag == "FarMountains":   # 각진 삼각형이 어색해서 렌더에서는 숨김 (밤하늘 그라데이션으로 충분)
        ob.visible_shadow = False
        ob.hide_render = True
    if dyn in dyn_objs:
        dyn_objs[dyn].append(ob)
        ob["dyn"] = dyn
        if dyn == "Loaf":
            ob["emit"] = 1.2
    counts[tag] = counts.get(tag, 0) + 1
print("world parts", counts, {k: len(v) for k, v in dyn_objs.items()})

# 지형
_, X0, X1, Z0, Z1, STEP, *rows = sec["T"].split(";")
X0, X1, Z0, Z1, STEP = map(int, (X0, X1, Z0, Z1, STEP))
TCOL = {"g": (0.075, 0.16, 0.035), "l": (0.09, 0.19, 0.04), "r": (0.13, 0.13, 0.14), "s": (0.62, 0.66, 0.74), "d": (0.12, 0.08, 0.045)}
grid = [r.split(",") for r in rows]
nz, nx = len(grid), len(grid[0])
verts, cols, faces = [], [], []
for iz, row in enumerate(grid):
    for ix, tok in enumerate(row):
        verts.append(bpos(X0 + ix * STEP, int(tok[:-1]) / 10.0 - 0.15, Z0 + iz * STEP))
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
bn = N.new("ShaderNodeBump")
bn.inputs["Strength"].default_value = 0.15
L.new(noise.outputs["Fac"], bn.inputs["Height"])
L.new(bn.outputs["Normal"], bsdf.inputs["Normal"])
L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
tme.materials.append(tmat)
col_for("Terrain").objects.link(tob)

# 간판 글자
font = bpy.data.fonts.load(FONT_PATH) if os.path.exists(FONT_PATH) else None
for e in [e for e in sec.get("X", "X;").split(";")[1:] if e]:
    face, size, pos, q, body = e.split("|", 4)
    sx, sy, sz = map(float, size.split(","))
    body = body.replace("\\n", "\n")
    cu = bpy.data.curves.new("sign", "FONT")
    cu.body = body
    if font:
        cu.font = font
    cu.align_x, cu.align_y = "CENTER", "CENTER"
    cu.size = sy * (0.33 if "\n" in body else 0.55)
    cu.extrude = 0.02
    ob = bpy.data.objects.new("SignText", cu)
    frame = Matrix(((-1, 0, 0), (0, 0, 1), (0, 1, 0))).transposed().to_4x4()
    ob.matrix_world = Matrix.Translation(bpos(*map(float, pos.split(",")))) @ brot(*map(float, q.split(","))).to_4x4() @ Matrix.Translation(Vector((0, sz / 2 + 0.03, 0))) @ frame
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

# 조명 (가로등 / 방 별등 / 기타)
light_groups = {"LampStar": [], "RoomStar": [], "-": []}
for i, e in enumerate([e for e in sec.get("L", "L;").split(";")[1:] if e]):
    pos, colh, bright, rng, dyn = e.split("|")
    rng = float(rng)
    ld = bpy.data.lights.new(f"lamp{i}", "POINT")
    ld.color = lin(colh)
    ld.energy = float(bright) * rng * rng * 2.2
    ld.shadow_soft_size = 0.35
    ld.use_custom_distance = True
    ld.cutoff_distance = rng * 3
    ld.use_shadow = (i % 4 == 0)
    ld["base_energy"] = ld.energy
    lo = bpy.data.objects.new(f"lamp{i}", ld)
    lo.location = bpos(*map(float, pos.split(",")))
    col_for("Lights").objects.link(lo)
    light_groups.get(dyn, light_groups["-"]).append(lo)
    lo["group"] = dyn if dyn in light_groups else "-"

# 달빛과 햇빛
moon_d = bpy.data.lights.new("Moon", "SUN")
moon_d.color = (0.55, 0.66, 1.0)
moon_d.angle = math.radians(3)
moon = bpy.data.objects.new("Moon", moon_d)
moon.rotation_euler = Vector((0, 0, 1)).rotation_difference(bpos(0.96, 0.32, 0.2).normalized()).to_euler()
col_for("Lights").objects.link(moon)
sun_d = bpy.data.lights.new("Sun", "SUN")
sun_d.color = (1.0, 0.9, 0.75)
sun_d.angle = math.radians(1.5)
sun = bpy.data.objects.new("Sun", sun_d)
sun.rotation_euler = Vector((0, 0, 1)).rotation_difference(bpos(-0.884, 0.422, 0.199).normalized()).to_euler()
col_for("Lights").objects.link(sun)

# ------------------------------------------------------------------ 하늘 (낮/밤, 별 양은 실행 스크립트가 조절)
world = bpy.data.worlds.new("Sky")
scene.world = world
nt, N, L = new_nodes(world)
wout = N.new("ShaderNodeOutputWorld")
day_v = N.new("ShaderNodeValue")
day_v.name = "DAY"
day_v.outputs[0].default_value = 0.0
star_v = N.new("ShaderNodeValue")
star_v.name = "STARS"
star_v.outputs[0].default_value = 0.86
tc = N.new("ShaderNodeTexCoord")
sep = N.new("ShaderNodeSeparateXYZ")
L.new(tc.outputs["Generated"], sep.inputs["Vector"])


def ramp_node(c0, c1, p0=0.5, p1=0.8):
    r = N.new("ShaderNodeValToRGB")
    r.color_ramp.elements[0].position, r.color_ramp.elements[0].color = p0, (*c0, 1)
    r.color_ramp.elements[1].position, r.color_ramp.elements[1].color = p1, (*c1, 1)
    L.new(sep.outputs["Z"], r.inputs["Fac"])
    return r


night_sky = ramp_node((0.06, 0.12, 0.36), (0.008, 0.016, 0.07))
day_sky = ramp_node((0.55, 0.72, 0.95), (0.18, 0.38, 0.85), 0.5, 0.85)
vor = N.new("ShaderNodeTexVoronoi")
vor.inputs["Scale"].default_value = 260
L.new(tc.outputs["Generated"], vor.inputs["Vector"])
dot = N.new("ShaderNodeMapRange")
dot.inputs["From Min"].default_value = 0.06
dot.inputs["From Max"].default_value = 0.0
dot.inputs["To Max"].default_value = 3.0
L.new(vor.outputs["Distance"], dot.inputs["Value"])
thin = N.new("ShaderNodeMath")
thin.operation = "GREATER_THAN"
L.new(vor.outputs["Color"], thin.inputs[0])
L.new(star_v.outputs[0], thin.inputs[1])
above = N.new("ShaderNodeMath")
above.operation = "GREATER_THAN"
above.inputs[1].default_value = 0.52
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
lightmix.inputs["A"].default_value = (0.05, 0.085, 0.24, 1)
lightmix.inputs["B"].default_value = (0.35, 0.48, 0.75, 1)
bg_light = N.new("ShaderNodeBackground")
L.new(lightmix.outputs["Result"], bg_light.inputs["Color"])
lp = N.new("ShaderNodeLightPath")
mixs = N.new("ShaderNodeMixShader")
L.new(lp.outputs["Is Camera Ray"], mixs.inputs["Fac"])
L.new(bg_light.outputs["Background"], mixs.inputs[1])
L.new(bg_cam.outputs["Background"], mixs.inputs[2])
L.new(mixs.outputs["Shader"], wout.inputs["Surface"])

# ------------------------------------------------------------------ 샷 기록 읽기
shots = []
cur = None
for line in open(BAKE, encoding="utf-8").read().split("\n"):
    if not line:
        continue
    t = line[0]
    if t == "S":
        _, n, start, count, light, sky, lamps, room = line.split("|")
        cur = {"n": int(n), "start": int(start), "count": int(count), "day": light == "day", "sky": sky,
               "lamps": lamps == "1", "room_open": room == "1", "cam": [], "decl": [], "stars": [], "chars": {}}
        shots.append(cur)
    elif t == "c":
        _, f, pos, q, fov, *rest = line.split("|")
        m = bcam(*map(float, q.split(","))).to_4x4()
        m.translation = bpos(*map(float, pos.split(",")))
        fd = float(rest[0]) if rest else -1.0        # 초점 거리 (-1 = 자동)
        fs = float(rest[1]) if len(rest) > 1 else 0.0  # 조리개 (0 = 자동)
        cur["cam"].append((tuple(tuple(r) for r in m), float(fov), fd, fs))
    elif t == "d":
        cur["decl"] = [(float(a), b == "1") for a, b in (x.split(",") for x in line[2:].split(";"))]
    elif t == "f":
        fr = []
        for x in line[2:].split(";"):
            fr.append(None if x == "-" else tuple(bpos(*map(float, x.split(",")))))
        cur["stars"].append(fr)
    elif t == "k":
        _, f, name, body = line.split("|", 3)
        nonface, face = [], []
        for pl in body.split("~"):
            idx, isf, k, size, pos, q, col, rmat, tr = pl.split("|")
            sx, sy, sz = map(float, size.split(","))
            loc = tuple(bpos(*map(float, pos.split(","))))
            rq = tuple(brot(*map(float, q.split(","))).to_quaternion())
            entry = (int(idx), k, (sx, sz, sy), loc, rq, lin(col), rmat, float(tr))
            (face if isf == "1" else nonface).append(entry)
        cur["chars"].setdefault(name, []).append((int(f), nonface, face))
print("shots", len(shots), "frames", shots[-1]["start"] + shots[-1]["count"])

# ------------------------------------------------------------------ 캐릭터
char_info = {}  # name -> {"parts": {idx: objname}, "pool": {kind: [objnames]}, "head": objname}
char_col = col_for("Cast")
for sh in shots:
    for name, snaps in sh["chars"].items():
        info = char_info.setdefault(name, {"first": None, "minT": {}, "faceMax": {}})
        for f, nonface, face in snaps:
            if info["first"] is None:
                info["first"] = nonface
            for e in nonface:
                tr = e[7]
                if 0.01 < tr < 0.99:
                    info["minT"][e[0]] = True
            cnt = {}
            for e in face:
                kk = "C" if e[1] == "C" else ("S" if e[1] == "S" else "B")
                cnt[kk] = cnt.get(kk, 0) + 1
            for kk, v in cnt.items():
                info["faceMax"][kk] = max(info["faceMax"].get(kk, 0), v)

for name, info in char_info.items():
    parts = {}
    head = None
    for idx, k, (bx, by, bz), loc, rq, col, rmat, tr in info["first"]:
        transparent = info["minT"].get(idx, False)
        mat = get_mat(rmat, transparent, True)
        if k in ("B", "M", "H", "A") and min(bx, by, bz) > 0.12:
            me = bpy.data.meshes.new(f"{name}_{idx}")
            if k == "A":
                # 머리카락: 상자 전체가 얼굴을 덮지 않게 정수리 판 + 뒷머리 판 두 개로 근사
                def box(x0, x1, y0, y1, z0, z1):
                    return [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
                hx, hy, hz = bx / 2, by / 2, bz / 2
                vs = box(-hx, hx, -hy, hy, hz - 0.42 * bz, hz) + box(-hx * 0.97, hx * 0.97, -hy, -hy + 0.34 * by, -0.08 * bz, hz - 0.1 * bz)
                fs = CUBE_F + [tuple(i + 8 for i in f) for f in CUBE_F]
                me.from_pydata(vs, [], fs)
                bx, by, bz = min(bx, 0.42 * bz * 2.2), by, bz   # 둥글리기 폭 계산용
            else:
                me.from_pydata([(v[0] * bx, v[1] * by, v[2] * bz) for v in CUBE_V], [], CUBE_F)
            me.update()
            ob = bpy.data.objects.new(f"{name}#{idx}", me)
            bev = ob.modifiers.new("bevel", "BEVEL")
            if k == "H":
                bev.width, bev.segments = 0.32, 6
            elif k == "A":
                bev.width, bev.segments = 0.18, 4
            else:
                bev.width, bev.segments = min(0.09, min(bx, by, bz) * 0.25), 3
            bev.limit_method = "NONE"
            if k in ("H", "A"):
                for p in me.polygons:
                    p.use_smooth = True
            me.materials.append(mat)
            ob["scale"] = (1.0, 1.0, 1.0)
        else:
            ob = bpy.data.objects.new(f"{name}#{idx}", unit_mesh(k))
            if k == "C":
                d = min(by, bz)
                by, bz = d, d
            link_obj_mat(ob, mat)
            ob["scale"] = (bx, by, bz)
        ob.color = (*col, 1.0)
        ob["emit"] = 0.6 if rmat == "Neon" else 0.0
        ob.hide_render = True
        char_col.objects.link(ob)
        parts[idx] = ob.name
        if k == "H":
            head = ob.name
    pool = {}
    # 표정 바꾸기·눈 깜빡임을 렌더 중에 새로 그리므로 표정 하나에 필요한 최대 개수만큼 넉넉히
    need = dict(info["faceMax"])
    need["B"] = max(need.get("B", 0), 20)
    need["C"] = max(need.get("C", 0), 10)
    for kk, cnt in need.items():
        pool[kk] = []
        for j in range(cnt):
            ob = bpy.data.objects.new(f"{name}#F{kk}{j}", unit_mesh(kk))
            link_obj_mat(ob, get_mat("SmoothPlastic", False, True))
            ob.hide_render = True
            char_col.objects.link(ob)
            pool[kk].append(ob.name)
    char_info[name] = {"parts": parts, "pool": pool, "head": head}
    print("cast", name, len(parts), "parts, face pool", {k: len(v) for k, v in pool.items()})

# ------------------------------------------------------------------ 별 효과 풀
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
sp = N.new("ShaderNodeSeparateXYZ")
L.new(tc.outputs["Generated"], sp.inputs["Vector"])
inv = N.new("ShaderNodeMapRange")
inv.inputs["To Min"].default_value = 1.0
inv.inputs["To Max"].default_value = 0.0
L.new(sp.outputs["Z"], inv.inputs["Value"])
emt = N.new("ShaderNodeEmission")
emt.inputs["Color"].default_value = (1.0, 0.75, 0.35, 1)
emt.inputs["Strength"].default_value = 2.5
trp = N.new("ShaderNodeBsdfTransparent")
mixs = N.new("ShaderNodeMixShader")
L.new(inv.outputs["Result"], mixs.inputs["Fac"])
L.new(trp.outputs["BSDF"], mixs.inputs[1])
L.new(emt.outputs["Emission"], mixs.inputs[2])
L.new(mixs.outputs["Shader"], o.inputs["Surface"])
TAIL_MAT.surface_render_method = "BLENDED"
star_mesh = make_sphere("star")
star_mesh.materials.append(STAR_MAT)
tail_mesh = bpy.data.meshes.new("tail")
bm = bmesh.new()
bmesh.ops.create_cone(bm, cap_ends=False, segments=10, radius1=0.5, radius2=0.06, depth=1.0)
bm.to_mesh(tail_mesh)
bm.free()
for p in tail_mesh.polygons:
    p.use_smooth = True
tail_mesh.materials.append(TAIL_MAT)
pool_n = max((len(s["decl"]) for s in shots), default=0)
fx_col = col_for("StarFX")
star_names, tail_names = [], []
for j in range(pool_n):
    s = bpy.data.objects.new(f"fx_star{j}", star_mesh)
    tl = bpy.data.objects.new(f"fx_tail{j}", tail_mesh)
    s.hide_render = tl.hide_render = True
    fx_col.objects.link(s)
    fx_col.objects.link(tl)
    star_names.append(s.name)
    tail_names.append(tl.name)
print("star pool", pool_n)

# ------------------------------------------------------------------ 카메라
cam_d = bpy.data.cameras.new("FilmCam")
cam_d.sensor_fit = "HORIZONTAL"
cam_d.clip_start = 0.1
cam_d.clip_end = 6000
cam_d.dof.use_dof = True
cam_d.dof.aperture_fstop = 16
cam = bpy.data.objects.new("FilmCam", cam_d)
scene.collection.objects.link(cam)
scene.camera = cam
fill_d = bpy.data.lights.new("CamFill", "AREA")
fill_d.energy, fill_d.size, fill_d.color = 220, 4, (0.85, 0.9, 1.0)
fill_d.use_custom_distance, fill_d.cutoff_distance, fill_d.use_shadow = True, 22, False
fill = bpy.data.objects.new("CamFill", fill_d)
fill.parent = cam
fill.location = (2.5, 1.8, 0.5)
col_for("Lights").objects.link(fill)

# 표정 파츠가 실행 중에 바꿔 끼울 재질을 미리 만들어 둠
get_mat("Neon", False, True)
get_mat("SmoothPlastic", False, True)

# ------------------------------------------------------------------ 데이터 저장
data = {
    "shots": shots,
    "chars": char_info,
    "stars": star_names,
    "tails": tail_names,
    "dyn": {k: [o.name for o in v] for k, v in dyn_objs.items()},
    "lights": {k: [o.name for o in v] for k, v in light_groups.items()},
}
with open(OUT_DATA, "wb") as f:
    pickle.dump(data, f, protocol=4)
scene["film_data"] = OUT_DATA

# ------------------------------------------------------------------ 렌더 설정
total = shots[-1]["start"] + shots[-1]["count"]
scene.render.engine = "BLENDER_EEVEE"
ee = scene.eevee
ee.taa_render_samples = 48
ee.use_shadows = True
ee.shadow_pool_size = "1024"
ee.shadow_ray_count = 2
ee.shadow_step_count = 8
ee.use_raytracing = True
ee.use_fast_gi = True
scene.render.use_motion_blur = True
scene.render.motion_blur_shutter = 0.5
scene.render.motion_blur_position = "START"
scene.render.resolution_x, scene.render.resolution_y = 1080, 1920
scene.render.resolution_percentage = 100
scene.render.fps = 30
scene.frame_start, scene.frame_end = 1, total
scene.render.filepath = os.path.join(FRAMES_DIR, "f")
scene.render.image_settings.file_format = "PNG"
scene.render.use_overwrite = False      # 중간에 멈춰도 이어서 렌더
scene.render.use_placeholder = True
try:
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
except Exception as e:
    print("color mgmt:", e)
scene.view_settings.exposure = 0.4
try:
    ng = bpy.data.node_groups.new("FilmComp", "CompositorNodeTree")
    ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    rl = ng.nodes.new("CompositorNodeRLayers")
    gl = ng.nodes.new("CompositorNodeGlare")
    go = ng.nodes.new("NodeGroupOutput")
    for nm, val in (("Type", "Bloom"), ("Quality", "High"), ("Threshold", 1.0), ("Strength", 0.55), ("Size", 0.8)):
        gl.inputs[nm].default_value = val
    ng.links.new(rl.outputs["Image"], gl.inputs["Image"])
    ng.links.new(gl.outputs["Image"], go.inputs[0])
    scene.compositing_node_group = ng
except Exception as e:
    print("compositor:", e)

# 실행 스크립트를 블렌드 안에도 넣어 둠 (창으로 열어 볼 때 자동 실행 허용하면 움직임)
if os.path.exists(RUNTIME):
    txt = bpy.data.texts.new("film_runtime.py")
    txt.from_string(open(RUNTIME, encoding="utf-8").read())
    txt.use_module = True
os.makedirs(FRAMES_DIR, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print("SAVED", OUT_BLEND, "objects", len(scene.objects), "frames", total)
