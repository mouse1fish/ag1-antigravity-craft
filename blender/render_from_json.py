# -*- coding: utf-8 -*-
"""
从 ag1_model_full.json 重建场景并渲染（Blender 3.5 + EEVEE）
用法:
  blender -b -t 2 --python render_from_json.py -- <json> <outdir> <tag>
可选环境变量: RESX/RESY/SAMPLES/VIEWS
"""
import bpy, os, sys, json, math, bmesh
ROOT = os.environ.get("AG1_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mathutils import Vector

argv = sys.argv
if "--" in argv:
    argv = argv[argv.index("--") + 1:]
else:
    argv = []

JSON = argv[0] if len(argv) > 0 else os.path.join(ROOT, "blender", "out", "ag1_model_full.json")
OUTDIR = argv[1] if len(argv) > 1 else os.path.join(ROOT, "blender", "out")
TAG = argv[2] if len(argv) > 2 else "ag1full"

RESX = int(os.environ.get("RESX", "1600"))
RESY = int(os.environ.get("RESY", "1100"))
SAMPLES = int(os.environ.get("SAMPLES", "32"))
VIEWS = os.environ.get("VIEWS", "hero,top,elec,cut").split(",")
CUT = os.environ.get("CUT", "0") == "1"
CUT_Z = float(os.environ.get("CUT_Z", "0.035"))
SM_ANGLE = float(os.environ.get("SM_ANGLE", "33"))
SUPPRESS = [x for x in os.environ.get("SUPPRESS", "").split(",") if x]

# ---------------- 清场 ----------------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

# ---------------- 中文字体 ----------------
CJK = None
for fp in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"):
    if os.path.exists(fp):
        try:
            CJK = bpy.data.fonts.load(fp)
            break
        except Exception:
            pass

# ---------------- 材质 ----------------
MATS = {}
def get_mat(color, metal, rough, emit, es, alpha):
    key = (tuple(round(c, 3) for c in color), round(metal, 2), round(rough, 2),
           tuple(round(c, 3) for c in emit), round(es, 1), round(alpha, 2))
    if key in MATS:
        return MATS[key]
    m = bpy.data.materials.new("m_%d" % len(MATS))
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*[min(1, max(0, c)) for c in color], 1)
    b.inputs["Metallic"].default_value = min(1, max(0, metal))
    b.inputs["Roughness"].default_value = min(1, max(0, rough))
    try:
        b.inputs["Emission"].default_value = (*[min(1, max(0, c)) for c in emit], 1)
        b.inputs["Emission Strength"].default_value = max(0, es)
    except Exception:
        pass
    if alpha < 0.999:
        b.inputs["Alpha"].default_value = alpha
        m.blend_method = 'BLEND'
    MATS[key] = m
    return m

# ---------------- 载入部件 ----------------
print("LOAD", JSON)
with open(JSON, encoding="utf-8") as f:
    data = json.load(f)
parts = data["parts"] if isinstance(data, dict) else data
print("PARTS", len(parts))

objs = []
for p in parts:
    v = p["v"]; idx = p["i"]
    if not v or not idx:
        continue
    n = len(v) // 3
    verts = [(v[3 * i], v[3 * i + 1], v[3 * i + 2]) for i in range(n)]
    faces = [(idx[3 * i], idx[3 * i + 1], idx[3 * i + 2]) for i in range(len(idx) // 3)]
    me = bpy.data.meshes.new(p["name"][:60])
    me.from_pydata(verts, [], faces)
    me.validate()
    me.update()
    ob = bpy.data.objects.new(p["name"][:60], me)
    sc.collection.objects.link(ob)
    ob["grp"] = p.get("grp") or "body"
    # 材质
    col = p.get("color") or [0.6, 0.6, 0.6]
    if isinstance(col, str):
        # hex
        h = col.lstrip("#")
        col = [int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255]
    em = p.get("emit") or [0, 0, 0]
    ob.data.materials.append(get_mat(col, p.get("metal", 0) or 0,
                                     p.get("rough", 0.5) or 0.5,
                                     em if isinstance(em, list) else [0, 0, 0],
                                     p.get("es", 0) or 0, p.get("alpha", 1) or 1))
    # 平滑着色（auto smooth 保留棱角）
    for poly in me.polygons:
        poly.use_smooth = True
    try:
        me.use_auto_smooth = True
        me.auto_smooth_angle = math.radians(SM_ANGLE)
    except Exception:
        pass
    # 剖切：外壳类部件删掉上半
    base = p["name"].split(".")[0]
    if CUT and base in ("Sphere", "shell", "hull", "Hull"):
        bm = bmesh.new()
        bm.from_mesh(me)
        kill = [f for f in bm.faces if f.calc_center_median().z > CUT_Z]
        bmesh.ops.delete(bm, geom=kill, context='FACES')
        bm.to_mesh(me)
        bm.free()
        me.update()
    objs.append(ob)

print("OBJ", len(objs))

# ---------------- 百万零件（实例族，可选）----------------
MASS = os.environ.get("MASS", "0") == "1"
MASS_DENSITY = float(os.environ.get("MASS_DENSITY", "0.30"))
if MASS:
    try:
        _here = os.path.dirname(os.path.abspath(__file__))
        if _here not in sys.path:
            sys.path.insert(0, _here)
        import massmesh
        mobjs, mparts, mtris = massmesh.build_all(MASS_DENSITY, sc.collection)
        objs.extend(mobjs)
        print("MASS_PARTS", mparts, "MASS_TRIS", mtris)
    except Exception as e:
        import traceback
        print("MASS FAIL", e)
        traceback.print_exc()

# ---------------- 世界与灯光 ----------------
world = bpy.data.worlds.new("W")
sc.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.012, 0.016, 0.024, 1)
bg.inputs[1].default_value = 1.0

def add_light(loc, energy, size, color):
    bpy.ops.object.light_add(type='AREA', location=loc)
    L = bpy.context.object
    L.data.energy = energy
    L.data.size = size
    L.data.color = color
    d = Vector((0, 0, 0)) - Vector(loc)
    L.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()

add_light((-5.0, -3.2, 3.4), 520, 7, (0.62, 0.74, 1.0))
add_light((4.6, 3.0, 3.0), 340, 6, (0.95, 0.9, 1.0))
add_light((0.4, -5.6, 1.6), 180, 6, (0.55, 0.8, 1.0))
add_light((0, 0, -4.4), 90, 8, (0.5, 0.62, 1.0))

# 地面
bpy.ops.mesh.primitive_plane_add(size=64, location=(0, 0, -1.12))
gp = bpy.context.object
gm = bpy.data.materials.new("ground")
gm.use_nodes = True
gb = gm.node_tree.nodes.get("Principled BSDF")
gb.inputs["Base Color"].default_value = (0.008, 0.010, 0.016, 1)
gb.inputs["Roughness"].default_value = 0.8
gb.inputs["Metallic"].default_value = 0.25
gp.data.materials.append(gm)

# ---------------- 包围盒 ----------------
def bbox_all():
    mn = Vector((1e9, 1e9, 1e9)); mx = Vector((-1e9, -1e9, -1e9))
    for o in objs:
        if o.type != 'MESH':
            continue
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            for i in range(3):
                mn[i] = min(mn[i], w[i]); mx[i] = max(mx[i], w[i])
    return mn, mx

MN, MX = bbox_all()
CTR = (MN + MX) * 0.5
print("BBOX", tuple(round(x, 3) for x in MN), tuple(round(x, 3) for x in MX))

# ---------------- 渲染配置 ----------------
sc.render.engine = 'BLENDER_EEVEE'
sc.eevee.taa_render_samples = SAMPLES
try:
    sc.eevee.use_gtao = True
    sc.eevee.use_ssr = True
    sc.eevee.use_bloom = True
    sc.eevee.bloom_threshold = 1.3
    sc.eevee.bloom_intensity = 0.03
except Exception:
    pass
sc.render.resolution_x = RESX
sc.render.resolution_y = RESY
sc.render.film_transparent = False
sc.view_settings.view_transform = 'Filmic'

LENS = 52.0
fovx = 2 * math.atan(18.0 / LENS)
asp = RESX / float(RESY)
fovy = 2 * math.atan(math.tan(fovx * 0.5) / asp)

VIEW_DIRS = {
    "hero":  (Vector((0.70, -0.66, 0.22)), 1.12, "persp"),
    "top":   (Vector((0.02, -0.02, 1.0)), 1.06, "ortho"),
    "front": (Vector((0.04, -1.0, 0.22)), 1.08, "ortho"),
    "side":  (Vector((1.0, -0.02, 0.20)), 1.08, "ortho"),
    "elec":  (Vector((0.52, -0.60, 0.66)), 0.42, "persp"),
    "cut":   (Vector((0.62, -0.62, 0.60)), 1.05, "persp"),
}
# 定点特写：name -> (target, dir, dist, lens)
FOCUS = {
    "pcb":   ((-0.62, 0.52, 0.00), (0.10, -0.22, 0.97), 0.55, 30.0),
    "pcb2":  ((0.58, 0.50, 0.00), (-0.10, -0.22, 0.97), 0.52, 30.0),
    "pcb3":  ((-0.60, -0.10, 0.06), (0.05, -0.16, 0.98), 0.34, 30.0),
    "pcbzoom": ((-0.71, 0.60, -0.04), (0.02, -0.10, 0.99), 0.24, 26.0),
    "pcbzoom2": ((0.60, 0.52, -0.04), (0.02, -0.10, 0.99), 0.22, 26.0),
    "gear":  ((0.86, -0.92, -0.62), (0.42, -0.74, 0.52), 1.45, 46.0),
    "conn":  ((0.0, -0.62, -0.02), (0.0, -0.55, 0.83), 0.55, 30.0),
    "inner": ((0.02, 0.02, -0.24), (0.42, -0.58, 0.70), 2.75, 52.0),
    "skin":  ((0.62, -0.30, 0.34), (0.42, -0.48, 0.77), 0.62, 42.0),
    "skin2": ((-0.35, 0.55, 0.30), (-0.20, 0.52, 0.83), 0.55, 42.0),
    "inner2": ((0.0, 0.45, -0.26), (0.18, -0.38, 0.91), 1.55, 40.0),
}
# 特写时隐藏的部件名前缀
HIDE_FOR_FOCUS = ("Sphere", "coil_turn", "coil_ins", "coil_brk", "beam", "rim",
                  "Torus", "inner", "mast")

bpy.ops.object.camera_add(location=(0, 0, 10))
cam = bpy.context.object
cam.data.lens = LENS
cam.data.sensor_fit = 'HORIZONTAL'
sc.camera = cam


def setup_cam(kind):
    # 特写类视角压低曝光，避免大面积漫反射过曝
    try:
        sc.view_settings.exposure = -0.10 if kind in ("pcb", "pcb2", "pcb3", "conn", "pcbzoom", "pcbzoom2") else 0.0
    except Exception:
        pass
    if kind in FOCUS:
        tgt, dr, dist, lens = FOCUS[kind]
        vd = Vector(dr).normalized()
        cam.data.type = 'PERSP'
        cam.data.lens = lens
        cam.location = Vector(tgt) + vd * dist
        cam.rotation_euler = (Vector(tgt) - cam.location).to_track_quat('-Z', 'Y').to_euler()
        bpy.context.view_layer.update()
        return
    cam.data.lens = LENS
    d, k, typ = VIEW_DIRS.get(kind, VIEW_DIRS["hero"])
    d = d.normalized()
    fwd = (-d).normalized()
    wu = Vector((0, 0, 1))
    if abs(fwd.dot(wu)) > 0.98:
        wu = Vector((0, 1, 0))
    right = fwd.cross(wu).normalized()
    up2 = right.cross(fwd).normalized()
    hx = hy = 0.0
    for ix in (MN.x, MX.x):
        for iy in (MN.y, MX.y):
            for iz in (MN.z, MX.z):
                v = Vector((ix, iy, iz)) - CTR
                hx = max(hx, abs(v.dot(right)))
                hy = max(hy, abs(v.dot(up2)))
    if typ == "ortho":
        cam.data.type = 'ORTHO'
        cam.data.ortho_scale = 2 * max(hx, hy * asp) * k
        dist = (hx + hy) * 3 + 6
    else:
        cam.data.type = 'PERSP'
        dist = max(hx / math.tan(fovx * 0.5), hy / math.tan(fovy * 0.5)) * k
    cam.location = CTR + d * dist
    cam.rotation_euler = (CTR - cam.location).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.view_layer.update()


for vk in VIEWS:
    if vk not in VIEW_DIRS and vk not in FOCUS:
        continue
    need_hide = vk in ("pcb", "pcb2", "pcb3", "conn", "pcbzoom", "pcbzoom2")
    for o in objs:
        if need_hide:
            g = o.get("grp") or "body"
            o.hide_render = g not in ("pcb", "comp", "rack")
        else:
            o.hide_render = any(o.name.startswith(sp) for sp in SUPPRESS)
    setup_cam(vk)
    out = os.path.join(OUTDIR, "%s_%s.png" % (TAG, vk))
    sc.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print("RENDERED", out)

print("ALL DONE")
