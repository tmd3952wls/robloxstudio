"""마을 조립: 거리(자갈길) + 집 배치(겹침 검사) + 광장 + 돌다리 + 강둑 석축 + 숲 + 소품 인스턴스.

Poly Haven 모델은 숨긴 컬렉션에 한 번만 불러오고 컬렉션 인스턴스로 반복 배치 (메모리 1회분).
나무는 지오메트리 노드 Instance on Points (크기·회전·종류 랜덤) -> 수천 그루도 가볍게.
"""
import math
import os
import random

import bpy
import numpy as np
from mathutils import Matrix, Vector

import assets
import buildings
import mesh as MS
import pbr


# ------------------------------------------------------------------ Poly Haven 모델 (인스턴스용)
_LIB = {}


def lib_collection():
    c = bpy.data.collections.get("_lib")
    if not c:
        c = bpy.data.collections.new("_lib")
        bpy.context.scene.collection.children.link(c)
        bpy.context.view_layer.layer_collection.children["_lib"].exclude = True
    return c


def load_model(aid, decimate=None):
    """gltf 를 한 번 불러와 컬렉션으로 보관. decimate(0~1) 면 폴리곤 줄이기 (큰 나무)"""
    if aid in _LIB:
        return _LIB[aid]
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=assets.path(aid, "gltf"))
    new = [o for o in bpy.data.objects if o not in before]
    col = bpy.data.collections.new("M_" + aid)
    lib_collection().children.link(col)
    for o in new:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        col.objects.link(o)
        if decimate and o.type == "MESH":
            md = o.modifiers.new("Dec", "DECIMATE")
            md.ratio = decimate
    _LIB[aid] = col
    return col


def instance(col, loc, rot_z=0.0, scale=1.0, name=None, parent_col=None):
    e = bpy.data.objects.new(name or ("I_" + col.name), None)
    e.instance_type, e.instance_collection = "COLLECTION", col
    e.location, e.rotation_euler, e.scale = loc, (0, 0, rot_z), (scale,) * 3
    (parent_col or bpy.context.scene.collection).objects.link(e)
    return e


# ------------------------------------------------------------------ 절차적 나무 (먼 숲용 LOD)
def conifer_mesh(seed, name):
    rnd = random.Random(seed)
    verts, faces = [], []
    def ring(z, r, n, jag):
        out = []
        for i in range(n):
            a = 2 * math.pi * i / n + rnd.uniform(-0.15, 0.15)
            rr = r * (1 + (jag if i % 2 else -jag) * rnd.uniform(0.5, 1))
            out.append((rr * math.cos(a), rr * math.sin(a), z + rnd.uniform(-0.1, 0.1) * r))
        return out
    # 줄기
    tv = len(verts)
    for z in (0, 2.5):
        for i in range(5):
            a = 2 * math.pi * i / 5
            verts.append((0.25 * math.cos(a), 0.25 * math.sin(a), z))
    for i in range(5):
        j = (i + 1) % 5
        faces.append((tv + i, tv + j, tv + 5 + j, tv + 5 + i))
    tiers = rnd.randint(5, 7)
    H = 1.6
    for t in range(tiers):
        r = 3.1 * (1 - t / tiers) + 0.4
        z0 = H + t * 1.55
        n = 10
        rg = ring(z0, r, n, 0.28)
        apex = (rnd.uniform(-0.1, 0.1), rnd.uniform(-0.1, 0.1), z0 + 2.6)
        b = len(verts)
        verts.extend(rg)
        verts.append(apex)
        for i in range(n):
            faces.append((b + i, b + (i + 1) % n, b + n))
        faces.append(tuple(b + i for i in reversed(range(n))))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    return me


def broadleaf_mesh(seed, name):
    rnd = random.Random(seed)
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.3, radius2=0.22, depth=3.0,
                          matrix=Matrix.Translation((0, 0, 1.5)))
    for k in range(rnd.randint(4, 7)):
        c = Vector((rnd.uniform(-1.6, 1.6), rnd.uniform(-1.6, 1.6), rnd.uniform(3.5, 6.0)))
        r = rnd.uniform(1.4, 2.3)
        g = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=r, matrix=Matrix.Translation(c))
        for v in g["verts"]:
            v.co += (v.co - c).normalized() * rnd.uniform(-0.35, 0.35) * r
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def foliage_mat(name, col, var=0.25):
    m = pbr.new_mat(name)
    b = pbr.NB(m)
    oi = b.n("ShaderNodeObjectInfo")
    nz = b.n("ShaderNodeTexNoise", i_Scale=1.3, i_Detail=8.0, i_Roughness=0.7)
    geo = b.n("ShaderNodeNewGeometry")
    b.ln(geo.outputs["Position"], nz.inputs["Vector"])
    base = b.mix(oi.outputs["Random"], tuple(c * (1 - var) for c in col) + (1,), tuple(min(1, c * (1 + var)) for c in col) + (1,))
    col2 = b.mix(nz.outputs["Fac"], (0.01, 0.015, 0.008, 1), base, blend="MIX")
    # 잎 덩어리 느낌: 노이즈 범프 강하게
    bp = b.n("ShaderNodeBump", i_Strength=0.9, i_Distance=0.3)
    b.ln(nz.outputs["Fac"], bp.inputs["Height"])
    bs = b.N["Principled BSDF"]
    b.ln(col2, bs.inputs["Base Color"])
    b.ln(bp.outputs[0], bs.inputs["Normal"])
    bs.inputs["Roughness"].default_value = 0.8
    bs.inputs["Subsurface Weight"].default_value = 0.15
    bs.inputs["Subsurface Radius"].default_value = (0.3, 0.6, 0.15)
    return m


def tree_variants():
    c = bpy.data.collections.get("_trees")
    if c:
        return c
    c = bpy.data.collections.new("_trees")
    lib_collection().children.link(c)
    fm = foliage_mat("Fol_conifer", pbr.srgb(46, 70, 40))
    bm_ = foliage_mat("Fol_broad", pbr.srgb(80, 105, 50))
    bark = pbr.flat_mat("Bark", pbr.srgb(70, 52, 40), 0.9)
    for i in range(4):
        me = conifer_mesh(100 + i, f"conifer{i}")
        me.materials.append(fm)
        ob = bpy.data.objects.new(f"conifer{i}", me)
        c.objects.link(ob)
    for i in range(2):
        me = broadleaf_mesh(200 + i, f"broad{i}")
        me.materials.append(bm_)
        ob = bpy.data.objects.new(f"broad{i}", me)
        c.objects.link(ob)
    return c


def tree_variants_town():
    """마을 안 활엽수 (가을빛 섞인 색 몇 가지)"""
    c = bpy.data.collections.get("_trees_town")
    if c:
        return c
    c = bpy.data.collections.new("_trees_town")
    lib_collection().children.link(c)
    cols = [pbr.srgb(62, 86, 42), pbr.srgb(80, 96, 44), pbr.srgb(112, 98, 46), pbr.srgb(55, 78, 40), pbr.srgb(120, 76, 42)]
    for i, col in enumerate(cols):
        me = broadleaf_mesh(300 + i, f"tbroad{i}")
        me.materials.append(foliage_mat(f"Fol_town{i}", col))
        c.objects.link(bpy.data.objects.new(f"tbroad{i}", me))
    return c


def scatter(points, col, name="Forest", scale_attr=None, rot_attr=None):
    """points: Nx3, scale_attr/rot_attr: N 배열. 지오메트리 노드로 컬렉션 안 하나를 골라 인스턴스"""
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(p) for p in points], [], [])
    if scale_attr is not None:
        a = me.attributes.new("sc", "FLOAT", "POINT"); a.data.foreach_set("value", np.asarray(scale_attr, np.float32))
    if rot_attr is not None:
        a = me.attributes.new("rz", "FLOAT", "POINT"); a.data.foreach_set("value", np.asarray(rot_attr, np.float32))
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ng = bpy.data.node_groups.new(name + "_GN", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, L = ng.nodes, ng.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    m2p = N.new("GeometryNodeMeshToPoints")
    ci = N.new("GeometryNodeCollectionInfo")
    ci.inputs["Collection"].default_value = col
    ci.inputs["Separate Children"].default_value = True
    ci.inputs["Reset Children"].default_value = True
    iop = N.new("GeometryNodeInstanceOnPoints")
    iop.inputs["Pick Instance"].default_value = True
    rnd = N.new("FunctionNodeRandomValue")
    rnd.data_type = "INT"
    rnd.inputs["Max"].default_value = len(col.objects) - 1
    sc = N.new("GeometryNodeInputNamedAttribute"); sc.data_type = "FLOAT"; sc.inputs["Name"].default_value = "sc"
    rz = N.new("GeometryNodeInputNamedAttribute"); rz.data_type = "FLOAT"; rz.inputs["Name"].default_value = "rz"
    cmb = N.new("ShaderNodeCombineXYZ")
    L.new(rz.outputs["Attribute"], cmb.inputs["Z"])
    L.new(gi.outputs[0], m2p.inputs["Mesh"])
    L.new(m2p.outputs["Points"], iop.inputs["Points"])
    L.new(ci.outputs[0], iop.inputs["Instance"])
    L.new(rnd.outputs[0], iop.inputs["Instance Index"])
    L.new(sc.outputs["Attribute"], iop.inputs["Scale"])
    L.new(cmb.outputs[0], iop.inputs["Rotation"])
    L.new(iop.outputs[0], go.inputs[0])
    md = ob.modifiers.new("GN", "NODES")
    md.node_group = ng
    return ob


# ------------------------------------------------------------------ 길·마을
def street_mat():
    if "Street" in bpy.data.materials:
        return bpy.data.materials["Street"]
    return pbr.tex_mat("Street", "cobblestone_floor_04", 2.2, var=0.2, detile=True, bump=0.8, bump_dist=0.05,
                       tint=pbr.srgb(175, 165, 155), sat=0.7)


def strip(pts, width, zf, name, mat, step_uv=1.0):
    """폴리라인을 따라 폭 width 의 띠 (자갈길·강둑)"""
    verts, faces, uvs = [], [], []
    acc = 0.0
    P = [Vector((p[0], p[1], 0)) for p in pts]
    for i, p in enumerate(P):
        t = (P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)]).normalized()
        n = Vector((-t.y, t.x, 0))
        if i:
            acc += (P[i] - P[i - 1]).length
        for s in (-1, 1):
            q = p + n * s * width / 2
            verts.append((q.x, q.y, zf(q.x, q.y)))
            uvs.append((s * width / 2, acc))
    for i in range(1, len(P)):
        k = 2 * i
        faces.append((k - 2, k - 1, k + 1, k))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    uvl = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            uvl.data[li].uv = uvs[me.loops[li].vertex_index]
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


class Town:
    def __init__(self, V, side, style, seed=1):
        self.V, self.side, self.style = V, side, style
        self.rnd = random.Random(seed)
        self.houses, self.info, self.occ = [], [], []
        self.col = bpy.data.collections.new(f"Town_{style}")
        bpy.context.scene.collection.children.link(self.col)

    def free(self, x, y, r):
        return all((x - a) ** 2 + (y - b) ** 2 > (r + rb) ** 2 for a, b, rb in self.occ)

    def place_row(self, pts, face_sign, setback, y_clip=None, floors=None, lit_p=0.3, max_n=999):
        """폴리라인 한쪽을 따라 집 줄 세우기. face_sign: 길 왼쪽(+1)/오른쪽(-1). 정면이 길을 봄"""
        P = [Vector((p[0], p[1], 0)) for p in pts]
        segs = [(P[i], P[i + 1]) for i in range(len(P) - 1)]
        n = 0
        for a, b in segs:
            L = (b - a).length
            t = (b - a).normalized()
            nrm = Vector((-t.y, t.x, 0)) * face_sign
            s = self.rnd.uniform(0, 2)
            while s < L - 3 and n < max_n:
                W = self.rnd.uniform(5.0, 7.6)
                D = self.rnd.uniform(5.8, 8.2)
                c = a + t * (s + W / 2) + nrm * (setback + D / 2 + self.rnd.uniform(0, 0.9))
                r = max(W, D) * 0.52
                if self.free(c.x, c.y, r) and self.V.D_at(c.x, c.y) > self.V.river_w / 2 + 9:
                    seed = self.rnd.randrange(1 << 30)
                    ob, info = buildings.house(seed, self.style, W=W, D=D, floors=floors, collection=self.col, lit_p=lit_p)
                    yaw = math.atan2(-nrm.y, -nrm.x) - math.pi / 2     # 집 정면(-Y) 이 길 쪽(-nrm)
                    ob.rotation_euler = (0, 0, yaw + self.rnd.uniform(-0.03, 0.03))
                    z = float(self.V.H(c.x, c.y))
                    ob.location = (c.x, c.y, z)
                    self.occ.append((c.x, c.y, r))
                    Mw = ob.matrix_world.copy()
                    Mw = Matrix.Translation((c.x, c.y, z)) @ Matrix.Rotation(yaw, 4, "Z")
                    info["world"] = {k: [tuple(Mw @ Vector(p)) for p in info[k]] for k in ("lanterns", "chimneys", "doors")}
                    info["center"] = (c.x, c.y, z)
                    info["yaw"] = yaw
                    self.houses.append(ob)
                    self.info.append(info)
                    n += 1
                s += W + self.rnd.uniform(0.25, 1.4)
        return n


def bridge(V, y, z_deck, name="Bridge", red_line=True):
    """돌 아치 다리 (교각 + 반원 아치 + 벽체 + 난간 + 가운데 붉은 선)"""
    st = pbr.tex_mat("Bridge_stone", "castle_wall_varriation", 2.0, tint=pbr.srgb(170, 162, 150), var=0.15, bump=0.7,
                     grime_z=V.water_z, grime_h=2.5)
    mb = MS.MB()
    xc = float(V.river_x(y))
    span = V.river_w + 30
    x0, x1 = xc - span / 2, xc + span / 2
    Wd = 7.0
    n_arch = 3
    pier = 3.2
    aw = (span - (n_arch + 1) * pier) / n_arch
    bot = V.water_z - 3.0
    # 교각
    for i in range(n_arch + 1):
        px = x0 + pier / 2 + i * (aw + pier)
        mb.box("s", (px, y, (bot + z_deck) / 2), (pier, Wd + 0.6, z_deck - bot))
        if 0 < i < n_arch:                                       # 물살 가르는 뾰족 기초
            for s in (-1, 1):
                mb.box("s", (px, y + s * (Wd / 2 + 0.9), (bot + V.water_z + 1.5) / 2), (pier * 0.72, pier * 0.72, V.water_z + 1.5 - bot),
                       MS.rotz(math.pi / 4))
    # 아치 + 벽체 (세로 띠로 채움)
    spring = V.water_z + 1.2
    for i in range(n_arch):
        ax0 = x0 + pier + i * (aw + pier)
        r = aw / 2
        cx = ax0 + r
        nstrip = 22
        for k in range(nstrip):
            xa = ax0 + aw * k / nstrip
            xb = ax0 + aw * (k + 1) / nstrip
            xm = (xa + xb) / 2
            za = spring + math.sqrt(max(r * r - (xm - cx) ** 2, 0)) * 0.8
            mb.box("s", (xm, y, (za + z_deck) / 2), (xb - xa + 0.01, Wd, z_deck - za))
        # 아치돌 테두리 (튀어나온 반원 띠)
        for k in range(18):
            a0 = math.pi * k / 18
            a1 = math.pi * (k + 1) / 18
            am = (a0 + a1) / 2
            px = cx - r * math.cos(am)
            pz = spring + r * math.sin(am) * 0.8
            L = r * (a1 - a0) * 1.05
            for s in (-1, 1):
                mb.box("s", (px, y + s * (Wd / 2 + 0.06), pz + 0.25), (L, 0.25, 0.65), MS.roty(-(am - math.pi / 2) * 0.9))
    # 상판·난간
    mb.box("s", (xc, y, z_deck + 0.15), (span + 6, Wd + 0.8, 0.3))
    for s in (-1, 1):
        mb.box("s", (xc, y + s * (Wd / 2 + 0.15), z_deck + 0.85), (span + 6, 0.45, 1.1))
        for k in range(14):
            px = x0 - 2 + (span + 4) * k / 13
            mb.box("s", (px, y + s * (Wd / 2 + 0.15), z_deck + 1.5), (0.6, 0.6, 0.25))
    mats = {"s": st}
    if red_line:
        mats["r"] = pbr.flat_mat("RedLine", (0.6, 0.02, 0.01), 0.5, emit=(1.0, 0.05, 0.02), emit_str=1.5)
        mb.box("r", (xc, y, z_deck + 0.31), (0.35, Wd - 0.2, 0.02))
    return mb.build(name, mats, bevel=0.04)


def quay(V, y0, y1, side, top_z, name):
    """강둑 석축 (마을 앞 강변)"""
    st = pbr.tex_mat("Quay_stone", "rustic_stone_wall", 2.4, tint=pbr.srgb(110, 104, 98), var=0.15, bump=0.6,
                     grime_z=V.water_z - 0.5, grime_h=2.0)
    mb = MS.MB()
    ys = np.arange(y0, y1, 3.0)
    for y in ys:
        x = float(V.river_x(y + 1.5)) + side * (V.river_w / 2 + 1.2)
        ang = math.atan(float(V.river_x(y + 3) - V.river_x(y)) / 3.0)
        mb.box("s", (x, y + 1.5, (V.water_z - 3 + top_z) / 2), (2.2, 3.05, top_z - V.water_z + 3), MS.rotz(-ang))
        mb.box("s", (x + side * 0.1, y + 1.5, top_z + 0.2), (2.6, 3.05, 0.4), MS.rotz(-ang))
    return mb.build(name, {"s": st}, bevel=0.03)
