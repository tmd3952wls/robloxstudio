"""조명·하늘·색관리·렌더 설정 (EEVEE / Cycles 공통 관리 -> 엔진 바꿔도 색감 같게).

preset(engine, quality): 'preview'(빠른 확인) / 'final'(최종)
"""
import math
import os
import sys

import bpy
from mathutils import Euler, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import assets  # noqa: E402


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    return sc


def world(hdri="kloofendal_48d_partly_cloudy_puresky", strength=1.0, rot_deg=0.0, sky_tint=None, sun_from_hdri=False):
    sc = bpy.context.scene
    w = bpy.data.worlds.new("World")
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    N, L = nt.nodes, nt.links
    for n in list(N):
        N.remove(n)
    out = N.new("ShaderNodeOutputWorld")
    bg = N.new("ShaderNodeBackground")
    env = N.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(assets.path(hdri, "hdr"), check_existing=True)
    tc = N.new("ShaderNodeTexCoord")
    mp = N.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (0, 0, math.radians(rot_deg))
    L.new(tc.outputs["Generated"], mp.inputs["Vector"])
    L.new(mp.outputs[0], env.inputs["Vector"])
    col = env.outputs["Color"]
    if sky_tint:
        mx = N.new("ShaderNodeMix")
        mx.data_type, mx.blend_type = "RGBA", "MULTIPLY"
        mx.inputs[0].default_value = 1.0
        L.new(col, mx.inputs[6])
        mx.inputs[7].default_value = tuple(sky_tint) + (1,)
        col = mx.outputs[2]
    L.new(col, bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength
    L.new(bg.outputs[0], out.inputs["Surface"])
    return w


def sun(elev_deg=28, azim_deg=135, energy=4.0, color=(1.0, 0.92, 0.82), angle_deg=1.2):
    ld = bpy.data.lights.new("Sun", "SUN")
    ld.energy, ld.color = energy, color
    ld.angle = math.radians(angle_deg)          # 부드러운 그림자 가장자리
    ob = bpy.data.objects.new("Sun", ld)
    bpy.context.scene.collection.objects.link(ob)
    # 태양이 (azim, elev) 방향에 있음 -> 빛은 반대로
    ob.rotation_euler = Euler((math.radians(90 - elev_deg), 0, math.radians(azim_deg + 90)), "XYZ")
    return ob


def point(name, loc, energy, color=(1.0, 0.6, 0.3), radius=0.1):
    ld = bpy.data.lights.new(name, "POINT")
    ld.energy, ld.color, ld.shadow_soft_size = energy, color, radius
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    bpy.context.scene.collection.objects.link(ob)
    return ob


def area(name, loc, target, energy, size=3.0, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy, ld.size, ld.color = energy, size, color
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    d = (Vector(target) - Vector(loc)).normalized()
    ob.rotation_euler = Vector((0, 0, -1)).rotation_difference(d).to_euler()
    bpy.context.scene.collection.objects.link(ob)
    return ob


def fog(lo, hi, density=0.004, color=(0.75, 0.8, 0.9), anisotropy=0.3, name="Fog"):
    """대기 원근감: 큰 상자 볼륨 (먼 산이 푸르스름하게 흐려짐)"""
    me = bpy.data.meshes.new(name)
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    me.from_pydata(v, [], f)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    pv = nt.nodes.new("ShaderNodeVolumePrincipled")
    pv.inputs["Density"].default_value = density
    pv.inputs["Color"].default_value = tuple(color) + (1,)
    pv.inputs["Anisotropy"].default_value = anisotropy
    # 높이에 따라 옅어지게 (골짜기에 깔리는 안개)
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sep.inputs[0])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = z0
    mr.inputs["From Max"].default_value = z1
    mr.inputs["To Min"].default_value = density * 2.2
    mr.inputs["To Max"].default_value = density * 0.25
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    nt.links.new(mr.outputs[0], pv.inputs["Density"])
    nt.links.new(pv.outputs[0], out.inputs["Volume"])
    me.materials.append(m)
    return ob


def camera(loc, look_at, lens=35, dof=None, fstop=4.0, name="Cam", sensor=36):
    cd = bpy.data.cameras.new(name)
    cd.lens, cd.sensor_width = lens, sensor
    cd.clip_start, cd.clip_end = 0.05, 20000
    ob = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    aim(ob, look_at)
    if dof:
        cd.dof.use_dof = True
        cd.dof.focus_distance = dof if isinstance(dof, (int, float)) else (Vector(dof) - Vector(loc)).length
        cd.dof.aperture_fstop = fstop
    bpy.context.scene.camera = ob
    return ob


def aim(ob, target, roll=0.0):
    d = Vector(target) - ob.location
    q = d.to_track_quat("-Z", "Y")
    ob.rotation_euler = q.to_euler()
    if roll:
        ob.rotation_euler.rotate_axis("Z", math.radians(roll))


def preset(engine="EEVEE", quality="final", samples=None, res=(1080, 1920), pct=100, motion_blur=False):
    sc = bpy.context.scene
    r = sc.render
    r.resolution_x, r.resolution_y, r.resolution_percentage = res[0], res[1], pct
    r.fps = 30
    r.image_settings.file_format = "PNG"
    vs = sc.view_settings
    vs.view_transform = "AgX"
    try:
        vs.look = "AgX - Medium High Contrast"
    except TypeError:
        try:
            vs.look = "Medium High Contrast"
        except TypeError:
            pass
    vs.exposure = 0.0
    r.use_motion_blur = motion_blur
    if engine.upper().startswith("EEVEE"):
        r.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE"
        ee = sc.eevee
        ee.taa_render_samples = samples or (64 if quality == "final" else 16)
        for k, v in (("use_raytracing", True), ("use_shadows", True), ("shadow_ray_count", 2), ("shadow_step_count", 8),
                     ("use_volumetric_shadows", True), ("volumetric_tile_size", "4"), ("volumetric_samples", 96),
                     ("use_gtao", True), ("gtao_distance", 1.5), ("fast_gi_method", "GLOBAL_ILLUMINATION"),
                     ("volumetric_end", 3000.0), ("clamp_surface_indirect", 10.0)):
            try:
                setattr(ee, k, v)
            except Exception:
                pass
        try:
            ee.ray_tracing_method = "SCREEN"
            ee.ray_tracing_options.resolution_scale = "1" if quality == "final" else "2"
            ee.ray_tracing_options.use_denoise = True
            ee.fast_gi_resolution = "2"
        except Exception:
            pass
        try:
            ee.shadow_resolution_scale = 1.0
        except Exception:
            pass
    else:
        r.engine = "CYCLES"
        cy = sc.cycles
        cy.device = "GPU"
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "OPTIX"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type == "OPTIX"
        cy.samples = samples or (128 if quality == "final" else 32)
        cy.use_denoising = True
        cy.denoiser = "OPTIX"
        cy.use_adaptive_sampling = True
        cy.max_bounces, cy.diffuse_bounces, cy.glossy_bounces, cy.transmission_bounces, cy.volume_bounces = 8, 3, 3, 6, 1
        cy.caustics_reflective = cy.caustics_refractive = False
        cy.blur_glossy = 1.0
        cy.volume_step_rate = 4.0
        cy.texture_limit_render = "4096"
    return sc
