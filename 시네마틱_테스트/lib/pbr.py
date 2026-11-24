"""PBR 재질 (Principled BSDF + Poly Haven 맵: Base Color / Normal / Roughness / Displacement(범프) / ARM).

- 반복 티 감추기: 큰 노이즈로 색·거칠기 흔들기 + (detile=True) 같은 텍스처를 회전·이동한 두 번째 샘플과 노이즈로 섞기
- 오염(grime): 월드 높이 기준으로 바닥 근처를 어둡고 축축하게 (벽 아래 흙·이끼)
- EEVEE/Cycles 공통으로 동작하는 노드만 사용 (엔진을 바꿔도 색감 유지)
"""
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import assets  # noqa: E402

_IMG = {}


def img(path, noncolor=False):
    key = (path, noncolor)
    if key not in _IMG:
        im = bpy.data.images.load(path, check_existing=True)
        if noncolor:
            im.colorspace_settings.name = "Non-Color"
        _IMG[key] = im
    return _IMG[key]


class NB:
    def __init__(self, mat):
        self.nt = mat.node_tree
        self.N, self.L = self.nt.nodes, self.nt.links
        self.x = 0

    def n(self, t, **kw):
        nd = self.N.new(t)
        for k, v in kw.items():
            if k.startswith("i_"):
                key = k[2:].replace("_", " ")
                nd.inputs[key].default_value = v
            else:
                setattr(nd, k, v)
        return nd

    def ln(self, a, b):
        self.L.new(a, b)

    def math(self, op, a, b=None, clamp=False):
        m = self.n("ShaderNodeMath", operation=op, use_clamp=clamp)
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                m.inputs[i].default_value = v
            else:
                self.ln(v, m.inputs[i])
        return m.outputs[0]

    def mix(self, fac, a, b, blend="MIX", dtype="RGBA"):
        m = self.n("ShaderNodeMix", data_type=dtype, blend_type=blend)
        idx = {"RGBA": (6, 7, 2), "FLOAT": (2, 3, 2), "VECTOR": (4, 5, 1)}[dtype]
        for sock, v in ((m.inputs[0], fac), (m.inputs[idx[0]], a), (m.inputs[idx[1]], b)):
            if isinstance(v, (int, float)):
                sock.default_value = v
            elif isinstance(v, tuple):
                sock.default_value = v
            else:
                self.ln(v, sock)
        out = {"RGBA": 2, "FLOAT": 0, "VECTOR": 1}[dtype]
        return m.outputs[out]


def new_mat(name):
    # 같은 이름이 있어도 지우지 않음 (지우면 이미 붙은 오브젝트가 재질을 잃어 하얗게 나옴) -> 블렌더가 .001 붙임
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m


def _coord(b, coord, tile, rot=0.0, offset=(0, 0, 0)):
    tc = b.n("ShaderNodeTexCoord")
    mp = b.n("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1 / tile, 1 / tile, 1 / tile)
    mp.inputs["Rotation"].default_value = (0, 0, rot)
    mp.inputs["Location"].default_value = offset
    b.ln(tc.outputs["UV" if coord == "UV" else "Object"], mp.inputs["Vector"])
    return mp.outputs[0]


def _sample(b, aid, vec, key, noncolor, box=False):
    e = assets.catalog()[aid]
    if key not in e["files"]:
        return None
    t = b.n("ShaderNodeTexImage", image=img(assets.path(aid, key), noncolor))
    if box:
        t.projection, t.projection_blend = "BOX", 0.25
    b.ln(vec, t.inputs["Vector"])
    return t


def texset(b, aid, tile, coord="UV", detile=False, rot=0.0):
    """-> dict(color, rough, normal_color, disp) 소켓"""
    box = coord != "UV"
    v1 = _coord(b, coord, tile, rot)
    out = {}
    s = {k: _sample(b, aid, v1, k, k != "diff", box) for k in ("diff", "rough", "nor_gl", "disp", "arm")}
    if detile:
        v2 = _coord(b, coord, tile * 1.37, rot + 1.1, (0.37, 0.71, 0))
        s2 = {k: _sample(b, aid, v2, k, k != "diff", box) for k in ("diff", "rough", "disp")}
        nz = b.n("ShaderNodeTexNoise", i_Scale=0.08 / tile * 10, i_Detail=2.0)
        b.ln(_coord(b, coord, 1.0), nz.inputs["Vector"])
        mask = b.n("ShaderNodeMapRange", i_From_Min=0.42, i_From_Max=0.58)
        b.ln(nz.outputs["Fac"], mask.inputs["Value"])
        f = mask.outputs[0]
        out["color"] = b.mix(f, s["diff"].outputs[0], s2["diff"].outputs[0])
        if s["rough"] and s2["rough"]:
            out["rough"] = b.mix(f, s["rough"].outputs[0], s2["rough"].outputs[0], dtype="FLOAT")
        if s["disp"] and s2["disp"]:
            out["disp"] = b.mix(f, s["disp"].outputs[0], s2["disp"].outputs[0], dtype="FLOAT")
    out.setdefault("color", s["diff"].outputs[0])
    if "rough" not in out:
        if s["rough"]:
            out["rough"] = s["rough"].outputs[0]
        elif s["arm"]:
            sep = b.n("ShaderNodeSeparateColor")
            b.ln(s["arm"].outputs[0], sep.inputs[0])
            out["rough"] = sep.outputs[1]
    if s["nor_gl"]:
        out["normal_color"] = s["nor_gl"].outputs[0]
    if "disp" not in out and s["disp"]:
        out["disp"] = s["disp"].outputs[0]
    return out


def finish(b, color, rough, normal_color=None, disp=None, normal_str=1.0, bump=0.25, bump_dist=0.03,
           metal=0.0, spec=0.5, coat=0.0, emission=None, emit_str=0.0, alpha=None):
    bs = b.N.get("Principled BSDF")
    b.ln(color, bs.inputs["Base Color"])
    if rough is not None:
        if isinstance(rough, (int, float)):
            bs.inputs["Roughness"].default_value = rough
        else:
            b.ln(rough, bs.inputs["Roughness"])
    bs.inputs["Metallic"].default_value = metal
    nrm = None
    if normal_color is not None:
        nm = b.n("ShaderNodeNormalMap", i_Strength=normal_str)
        b.ln(normal_color, nm.inputs["Color"])
        nrm = nm.outputs[0]
    if disp is not None and bump > 0:
        bp = b.n("ShaderNodeBump", i_Strength=bump, i_Distance=bump_dist)
        b.ln(disp, bp.inputs["Height"])
        if nrm is not None:
            b.ln(nrm, bp.inputs["Normal"])
        nrm = bp.outputs[0]
    if nrm is not None:
        b.ln(nrm, bs.inputs["Normal"])
    if coat:
        bs.inputs["Coat Weight"].default_value = coat
    if emission is not None:
        b.ln(emission, bs.inputs["Emission Color"]) if not isinstance(emission, tuple) else None
        if isinstance(emission, tuple):
            bs.inputs["Emission Color"].default_value = emission
        bs.inputs["Emission Strength"].default_value = emit_str
    if alpha is not None:
        bs.inputs["Alpha"].default_value = alpha
    return bs


def variation(b, color, tile, amount=0.18, hue=0.02, scale=0.15):
    """큰 얼룩 노이즈로 밝기·색 흔들기 (같은 무늬 반복이 덜 보임)"""
    nz = b.n("ShaderNodeTexNoise", i_Scale=scale, i_Detail=3.0, i_Roughness=0.6)
    tc = b.n("ShaderNodeTexCoord")
    b.ln(tc.outputs["Object"], nz.inputs["Vector"])
    hsv = b.n("ShaderNodeHueSaturation")
    b.ln(color, hsv.inputs["Color"])
    v = b.n("ShaderNodeMapRange", i_To_Min=1 - amount, i_To_Max=1 + amount)
    b.ln(nz.outputs["Fac"], v.inputs["Value"])
    b.ln(v.outputs[0], hsv.inputs["Value"])
    h = b.n("ShaderNodeMapRange", i_To_Min=0.5 - hue, i_To_Max=0.5 + hue)
    b.ln(nz.outputs["Fac"], h.inputs["Value"])
    b.ln(h.outputs[0], hsv.inputs["Hue"])
    return hsv.outputs[0]


def grime(b, color, rough, z0=0.0, height=1.2, dark=0.45, wet=0.25):
    """월드 z0~z0+height 사이 바닥 근처를 어둡고 덜 거칠게 (흙·물때). 노이즈로 경계 흔들기"""
    geo = b.n("ShaderNodeNewGeometry")
    sep = b.n("ShaderNodeSeparateXYZ")
    b.ln(geo.outputs["Position"], sep.inputs[0])
    nz = b.n("ShaderNodeTexNoise", i_Scale=1.6, i_Detail=4.0)
    b.ln(geo.outputs["Position"], nz.inputs["Vector"])
    zz = b.math("ADD", sep.outputs["Z"], b.math("MULTIPLY", nz.outputs["Fac"], height * 0.6))
    f = b.n("ShaderNodeMapRange", i_From_Min=z0 + height, i_From_Max=z0, interpolation_type="SMOOTHSTEP")
    b.ln(zz, f.inputs["Value"])
    fac = f.outputs[0]
    dk = b.mix(fac, color, (0.09, 0.075, 0.06, 1), blend="MULTIPLY")
    col2 = b.mix(b.math("MULTIPLY", fac, dark), color, dk)
    r2 = b.mix(b.math("MULTIPLY", fac, wet), rough, 0.35, dtype="FLOAT") if rough is not None else None
    return col2, r2


def tex_mat(name, aid, tile=2.0, coord="UV", tint=None, var=0.15, detile=False, normal_str=1.0, bump=0.3,
            bump_dist=0.04, rough_add=0.0, grime_z=None, grime_h=1.2, sat=1.0, gain=1.0):
    m = new_mat(name)
    b = NB(m)
    t = texset(b, aid, tile, coord, detile)
    col = t["color"]
    if tint is not None:
        col = b.mix(1.0, col, tuple(tint) + (1,), blend="MULTIPLY")
    if sat != 1.0 or gain != 1.0:
        hs = b.n("ShaderNodeHueSaturation", i_Saturation=sat, i_Value=gain)
        b.ln(col, hs.inputs["Color"])
        col = hs.outputs[0]
    if var:
        col = variation(b, col, tile, var)
    rough = t.get("rough")
    if rough is not None and rough_add:
        rough = b.math("ADD", rough, rough_add, clamp=True)
    if grime_z is not None:
        col, rough = grime(b, col, rough, grime_z, grime_h)
    finish(b, col, rough if rough is not None else 0.8, t.get("normal_color"), t.get("disp"), normal_str, bump, bump_dist)
    return m


def flat_mat(name, color, rough=0.5, metal=0.0, emit=None, emit_str=0.0, coat=0.0):
    m = new_mat(name)
    bs = m.node_tree.nodes["Principled BSDF"]
    bs.inputs["Base Color"].default_value = tuple(color) + (1,) if len(color) == 3 else color
    bs.inputs["Roughness"].default_value = rough
    bs.inputs["Metallic"].default_value = metal
    if coat:
        bs.inputs["Coat Weight"].default_value = coat
    if emit:
        bs.inputs["Emission Color"].default_value = tuple(emit) + (1,)
        bs.inputs["Emission Strength"].default_value = emit_str
    return m


def srgb(r, g, b):
    f = lambda c: ((c / 255 + 0.055) / 1.055) ** 2.4 if c / 255 > 0.04045 else c / 255 / 12.92
    return (f(r), f(g), f(b))
