# -*- coding: utf-8 -*-
"""
build_ag1_cutaway.py —— AG-1 结构剖视（真实机器结构 + 线路 + 原理所需的物理结构）
用法： blender -b -t 2 --python build_ag1_cutaway.py -- [w] [h] [samples] [view] [annot] [engine]
结构：
  A 承力骨架（环梁 / 8 根径向肋 / 中央承载筒 / 设备甲板）
  B 负质量核系统（真空腔 / 负质量核 / 6 组超导约束线圈 / 磁悬浮轴承 / 低温杜瓦 / 场整形环）
  C 能源（4 组电源柜 / 铜汇流排 / 配电箱）
  D 冷却（2 台泵 / 冷却回路管路）
  E 航电（计算单元 / 传感器接口）
  F 座舱（座椅 / 控制台 / 仪表板）
  G 推进（万向喷口 / 作动筒 / 工质管）
  H 线束（设备之间 + 卡箍）
外壳剖掉上半，便于看内部。
"""
import bpy, bmesh, math, random, os, sys
ROOT = os.environ.get("AG1_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mathutils import Vector, Matrix

argv = sys.argv
args = argv[argv.index("--") + 1:] if "--" in argv else []
EXPORT = (len(args) > 0 and args[0] == "export")
FULL = ("full" in args)
if EXPORT:
    RESX, RESY, SAMPLES, VIEW, ANNOT, ENGINE = 16, 16, 1, "hero", False, "eevee"
else:
    RESX = int(args[0]) if len(args) > 0 else 1400
    RESY = int(args[1]) if len(args) > 1 else 900
    SAMPLES = int(args[2]) if len(args) > 2 else 64
    VIEW = args[3] if len(args) > 3 else "hero"
    ANNOT = len(args) > 4 and args[4] == "annot"
    ENGINE = args[5] if len(args) > 5 else "eevee"
OUT = os.path.join(ROOT, "blender", "out")
os.makedirs(OUT, exist_ok=True)
OUTNAME = "ag1_cut_%s%s" % (VIEW, "_annot" if ANNOT else "")
random.seed(31)

# ---------------- 基础 ----------------
bpy.ops.wm.read_factory_settings(use_empty=True)

CJK = None
for _p in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"):
    try:
        CJK = bpy.data.fonts.load(_p); break
    except Exception:
        CJK = None

def mat(n, c, metal=0.0, rough=0.5, emit=None, es=0.0, alpha=1.0):
    m = bpy.data.materials.new(n); m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*c, 1.0)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rough
    if emit:
        b.inputs["Emission"].default_value = (*emit, 1.0)
        b.inputs["Emission Strength"].default_value = es
    if alpha < 1.0:
        b.inputs["Alpha"].default_value = alpha
        m.blend_method = 'BLEND'
    return m

def hs(n, c, metal=1.0, rough=0.35, bump=0.12, scale=90, dirt=0.10):
    m = mat(n, c, metal, rough)
    N = m.node_tree.nodes; L = m.node_tree.links
    bsdf = N.get("Principled BSDF")
    tc = N.new("ShaderNodeTexCoord")
    nz = N.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = scale
    nz.inputs["Detail"].default_value = 10.0
    L.new(tc.outputs["Object"], nz.inputs["Vector"])
    bp = N.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = bump
    bp.inputs["Distance"].default_value = 0.010
    L.new(nz.outputs["Fac"], bp.inputs["Height"])
    L.new(bp.outputs["Normal"], bsdf.inputs["Normal"])
    rg = N.new("ShaderNodeValToRGB")
    rg.color_ramp.elements[0].color = (max(0.02, rough*0.65),)*3 + (1.0,)
    rg.color_ramp.elements[1].color = (min(1.0, rough*1.4),)*3 + (1.0,)
    L.new(nz.outputs["Fac"], rg.inputs["Fac"])
    L.new(rg.outputs["Color"], bsdf.inputs["Roughness"])
    mx = N.new("ShaderNodeMixRGB"); mx.blend_type = 'MULTIPLY'
    mx.inputs["Color1"].default_value = (*c, 1.0)
    mx.inputs["Color2"].default_value = (0.4, 0.4, 0.42, 1.0)
    L.new(nz.outputs["Fac"], mx.inputs["Fac"])
    L.new(mx.outputs["Color"], bsdf.inputs["Base Color"])
    return m

def apply(ob):
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

def bev(ob, w=0.008, seg=2):
    md = ob.modifiers.new("b", 'BEVEL'); md.width = w; md.segments = seg
    md.limit_method = 'ANGLE'; md.angle_limit = math.radians(40)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier=md.name)

def smooth(ob, d=34):
    for p in ob.data.polygons: p.use_smooth = True
    ob.data.use_auto_smooth = True; ob.data.auto_smooth_angle = math.radians(d)

def P(kind, loc=(0,0,0), rot=(0,0,0), **k):
    if kind == "sphere":
        bpy.ops.mesh.primitive_uv_sphere_add(radius=k.get("r",1), segments=k.get("s",32), ring_count=k.get("rc",18), location=loc, rotation=rot)
    elif kind == "cyl":
        bpy.ops.mesh.primitive_cylinder_add(radius=k.get("r",1), depth=k.get("h",1), vertices=k.get("v",28), location=loc, rotation=rot)
    elif kind == "cone":
        bpy.ops.mesh.primitive_cone_add(radius1=k.get("r",1), radius2=k.get("r2",0.0), depth=k.get("h",1), vertices=k.get("v",28), location=loc, rotation=rot)
    elif kind == "torus":
        bpy.ops.mesh.primitive_torus_add(major_radius=k["R"], minor_radius=k.get("r",0.04), major_segments=k.get("s1",56), minor_segments=k.get("s2",10), location=loc, rotation=rot)
    elif kind == "box":
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
        ob = bpy.context.object; ob.scale = (k["sx"], k["sy"], k["sz"]); apply(ob); return ob
    return bpy.context.object

def M(ob, m):
    ob.data.materials.clear(); ob.data.materials.append(m)

def rod(a, b, r, m, v=14):
    """两点之间的圆柱杆件（用于支柱 / 活塞杆 / 销轴 / 连杆）"""
    a = Vector(a); b = Vector(b); dd = b - a; L = dd.length
    if L < 1e-6:
        return None
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=L, vertices=v,
                                        location=(a + b) / 2)
    o = bpy.context.object
    o.rotation_euler = dd.to_track_quat('Z', 'Y').to_euler()
    M(o, m)
    return o

def pin(center, axis, half_len, r, m, v=12):
    """铰链销轴：沿 axis 方向的短圆柱"""
    c = Vector(center); ax = Vector(axis).normalized()
    return rod(c - ax * half_len, c + ax * half_len, r, m, v)

# ---------------- 材质 ----------------
M_SHELL = hs("shell",  (0.10, 0.11, 0.16), 1.0, 0.34, 0.14, 70)
M_FRAME = hs("frame",  (0.22, 0.23, 0.27), 1.0, 0.28, 0.10, 110)
M_DECK  = hs("deck",   (0.07, 0.08, 0.10), 0.9, 0.45, 0.10, 130)
M_STEEL = hs("steel",  (0.58, 0.61, 0.66), 1.0, 0.22, 0.07, 160)
M_COPPER= hs("copper", (0.80, 0.42, 0.16), 1.0, 0.26, 0.08, 120)
M_DARK  = mat("dark",  (0.02, 0.022, 0.028), 0.6, 0.65)
M_CORE  = mat("core",  (0.55, 0.28, 1.0), 0.1, 0.10, (0.45, 0.16, 1.0), 5.0)
M_GLASS = mat("glass", (0.30, 0.62, 0.85), 0.05, 0.04, alpha=0.22)
M_LED   = mat("led",   (1.0, 0.85, 0.55), 0.0, 0.3, (1.0, 0.72, 0.35), 10.0)
M_LEDG  = mat("ledg",  (0.25, 1.0, 0.45), 0.0, 0.3, (0.25, 1.0, 0.45), 9.0)
M_LEDR  = mat("ledr",  (1.0, 0.15, 0.15), 0.0, 0.3, (1.0, 0.15, 0.15), 9.0)
M_CABLE = hs("cable",  (0.72, 0.58, 0.20), 0.7, 0.38, 0.05, 200)

HX, HY, HZ = 1.62, 1.86, 0.52

# ---------------- A 承力骨架 ----------------
# 外壳（剖掉上半，留碗底）
shell = P("sphere", r=1.0, s=72, rc=44)
shell.scale = (HX, HY, HZ); apply(shell)
if not EXPORT and not FULL:
    me = shell.data
    bm = bmesh.new(); bm.from_mesh(me)
    kill = [f for f in bm.faces if f.calc_center_median().z > 0.035]
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    bm.to_mesh(me); bm.free()
    me.update()
smooth(shell, 60); M(shell, M_SHELL)
bev(shell, 0.004, 1)

# 剖切边缘加强环
rim = P("torus", R=1.0, r=0.022, loc=(0,0,0.05), s1=128, s2=8)
rim.scale = (HX*1.0, HY*1.0, 1.0); apply(rim); M(rim, M_FRAME)

# 主承力环梁
beam = P("torus", R=1.0, r=0.075, loc=(0,0,-0.02), s1=96, s2=14)
beam.scale = (HX*0.965, HY*0.965, 1.0); apply(beam); M(beam, M_FRAME); bev(beam,0.006)

# ---------------- U1 高压高频线圈环（原理核心：巨大的环形绕组）----------------
# 全部藏在外壳内部：半径系数 < 1，且减小圈间距，避免堆叠高度顶出壳体
COIL_N = 30
COIL_R = 0.70          # 线圈半径系数（相对 HX/HY）
COIL_PITCH = 0.0085    # 相邻圈间距
COIL_Z = 0.062
coil_parts = []
for i in range(COIL_N):
    off = (i - (COIL_N - 1) / 2.0) * COIL_PITCH
    t = P("torus", R=1.0, r=0.0125, loc=(0, 0, COIL_Z + off), s1=128, s2=6)
    t.scale = (HX * COIL_R, HY * COIL_R, 1.0); apply(t)
    t.name = "coil_turn_%02d" % i
    M(t, M_COPPER)
    coil_parts.append(t)
# 陶瓷绝缘子
for i in range(12):
    a = i * 2 * math.pi / 12
    ins = P("cyl", r=0.019, h=0.098, loc=(math.cos(a) * HX * 0.735, math.sin(a) * HY * 0.735, COIL_Z), v=8)
    ins.name = "coil_ins_%02d" % i
    M(ins, M_DARK)
    coil_parts.append(ins)
# 支撑托架
for i in range(6):
    a = i * 2 * math.pi / 6 + 0.30
    br = P("box", sx=0.10, sy=0.042, sz=0.048,
           loc=(math.cos(a) * HX * 0.672, math.sin(a) * HY * 0.672, COIL_Z - 0.058), rot=(0, 0, a))
    br.name = "coil_brk_%d" % i
    M(br, M_FRAME)
    coil_parts.append(br)
for _o in coil_parts:
    _o["mech"] = "spin_coil"
    _o["pivot"] = (0.0, 0.0, 0.0)

# ---------------- U2 内旋转环（带 12 片叶片）----------------
inner_parts = []
ir = P("torus", R=0.86, r=0.020, loc=(0, 0, 0.140), s1=96, s2=8)
ir.name = "inner_ring"; M(ir, M_STEEL); inner_parts.append(ir)
for i in range(12):
    a = i * 2 * math.pi / 12
    vn = P("box", sx=0.30, sy=0.028, sz=0.045,
           loc=(math.cos(a) * 0.70, math.sin(a) * 0.70, 0.140), rot=(0, 0, a))
    vn.name = "inner_vane_%02d" % i
    M(vn, M_COPPER); inner_parts.append(vn)
for _o in inner_parts:
    _o["mech"] = "spin_inner"
    _o["pivot"] = (0.0, 0.0, 0.140)

# ---------------- U3 中央桅杆 + 顶部旋转体 ----------------
mast_parts = []
mm = P("cyl", r=0.028, h=0.60, loc=(0, 0, 0.33), v=12)
mm.name = "mast_rod"; M(mm, M_STEEL); mast_parts.append(mm)
for i in range(4):
    a = i * math.pi / 2 + math.pi / 4
    arm = P("box", sx=0.24, sy=0.020, sz=0.020,
            loc=(math.cos(a) * 0.12, math.sin(a) * 0.12, 0.585), rot=(0, 0, a))
    arm.name = "mast_arm_%d" % i
    M(arm, M_FRAME); mast_parts.append(arm)
mt = P("cyl", r=0.080, h=0.028, loc=(0, 0, 0.645), v=20)
mt.name = "mast_top"; M(mt, M_STEEL); mast_parts.append(mt)
mb = P("sphere", r=0.030, loc=(0, 0, 0.672), s=16, rc=10)
mb.name = "mast_beacon"; M(mb, M_LEDR); mast_parts.append(mb)
for _o in mast_parts:
    _o["mech"] = "spin_mast"
    _o["pivot"] = (0.0, 0.0, 0.0)

# ---------------- U4 底部发射环（等离子辉光）----------------
em = P("torus", R=0.56, r=0.022, loc=(0, 0, -0.33), s1=72, s2=8)
em.name = "emitter_ring"; M(em, M_LEDG)
em2 = P("torus", R=0.38, r=0.014, loc=(0, 0, -0.345), s1=56, s2=6)
em2.name = "emitter_ring2"; M(em2, M_CORE)


# 8 根径向肋
ribs = []
for i in range(8):
    a = i*2*math.pi/8
    ln = 1.30
    r = P("box", sx=ln, sy=0.09, sz=0.075, loc=(math.cos(a)*ln*0.5, math.sin(a)*ln*0.5, -0.10), rot=(0,0,a))
    M(r, M_FRAME); ribs.append(r)

# 中央承载筒
hub = P("cyl", r=0.56, h=0.46, loc=(0,0,-0.10), v=48); M(hub, M_FRAME); bev(hub,0.008)

# 设备甲板（两层）
d1 = P("cyl", r=1.42, h=0.022, loc=(0,0,-0.155), v=72); M(d1, M_DECK)
d2 = P("cyl", r=0.86, h=0.020, loc=(0,0,0.045), v=56); M(d2, M_DECK)

# ============ 可收放起落架（三节鱼竿式伸缩 + 折叠）============
# 为什么这么设计：腿展开要 1.5 m 才够落地，但机身内部舱高只有约 1 m，
# 任何整体转动都会让腿横穿核舱。鱼竿式伸缩杆先把 3 节缩回 0.52 m，
# 再整体向外翻 57 度平贴到壳体内侧，既不穿设备也不露在外面。
def ell_r(a):
    """椭圆壳体在方位角 a 处的极半径"""
    ca, sa = math.cos(a), math.sin(a)
    return 1.0 / math.sqrt((ca / HX) ** 2 + (sa / HY) ** 2)

def shell_hit(p0, p1):
    """线段 p0(壳内) -> p1(壳外) 与椭球壳的交点（二分）"""
    def f(p):
        return (p.x / HX) ** 2 + (p.y / HY) ** 2 + (p.z / HZ) ** 2 - 1.0
    lo, hi = 0.0, 1.0
    for _ in range(30):
        mid = (lo + hi) * 0.5
        if f(p0 + (p1 - p0) * mid) < 0.0: lo = mid
        else: hi = mid
    return p0 + (p1 - p0) * lo

# ---- 加载真实零件（step.parts 开源标准件，glTF）----
ASSET_DIR = os.path.join(ROOT, "blender", "assets")

def load_real_part(fname, size_m, loc, aim, nm, mech=None, pivot=None, thick=1.0):
    """导入 glb → 合并 → 缩放到最长边 size_m → 长轴对齐 aim → 移到 loc"""
    import mathutils
    path = os.path.join(ASSET_DIR, fname)
    if not os.path.exists(path):
        print("MISSING ASSET", path)
        return None
    before = set(o.name for o in bpy.data.objects)
    try:
        bpy.ops.import_scene.gltf(filepath=path)
    except Exception as e:
        print("GLB FAIL", fname, e)
        return None
    new = [o for o in bpy.data.objects if o.name not in before and o.type == 'MESH']
    if not new:
        return None
    bpy.ops.object.select_all(action='DESELECT')
    for o in new:
        o.select_set(True)
    bpy.context.view_layer.objects.active = new[0]
    if len(new) > 1:
        bpy.ops.object.join()
    ob = bpy.context.object
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    # 缩放到目标尺寸（按最长边）
    dim = ob.dimensions
    longest = max(dim.x, dim.y, dim.z)
    if longest <= 0:
        return None
    k = size_m / longest
    ob.scale = (k, k * thick, k * thick)
    apply(ob)
    # 长轴（X）对齐 aim
    ob.rotation_euler = Vector(aim).normalized().to_track_quat('X', 'Z').to_euler()
    bpy.context.view_layer.update()
    # 平移到目标点
    vs = [ob.matrix_world @ mathutils.Vector(c) for c in ob.bound_box]
    cen = sum(vs, mathutils.Vector((0, 0, 0))) / 8.0
    ob.location += (Vector(loc) - cen)
    bpy.context.view_layer.update()
    ob.name = nm
    if mech:
        ob["mech"] = mech
        ob["link"] = "outer"
        ob["pivot"] = (round(pivot.x, 3), round(pivot.y, 3), round(pivot.z, 3))
        ob["knee"] = (0.0, 0.0, 0.0)
        ob["dir"] = (round(Vector(aim).normalized().x, 4), round(Vector(aim).normalized().y, 4), round(Vector(aim).normalized().z, 4))
        ob["tele"] = [0, 0.0]
    return ob

def load_stl_part(fname, size_m, loc, aim, nm, mech=None, pivot=None, thick=1.0, matl=None):
    """导入真实 STEP 转出的 STL → 合并 → 按最长边缩放 → 长轴对齐 → 定位"""
    import mathutils
    path = os.path.join(ASSET_DIR, "step", fname)
    if not os.path.exists(path):
        print("MISSING STL", path)
        return None
    before = set(o.name for o in bpy.data.objects)
    try:
        bpy.ops.import_mesh.stl(filepath=path)
    except Exception as e:
        print("STL FAIL", fname, e)
        return None
    new = [o for o in bpy.data.objects if o.name not in before and o.type == 'MESH']
    if not new:
        return None
    bpy.ops.object.select_all(action='DESELECT')
    for o in new:
        o.select_set(True)
    bpy.context.view_layer.objects.active = new[0]
    if len(new) > 1:
        bpy.ops.object.join()
    ob = bpy.context.object
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    d = ob.dimensions
    longest = max(d.x, d.y, d.z)
    if longest <= 0:
        return None
    k = size_m / longest
    ob.scale = (k, k * thick, k * thick)
    apply(ob)
    ob.rotation_euler = Vector(aim).normalized().to_track_quat('Z', 'Y').to_euler()
    bpy.context.view_layer.update()
    vs = [ob.matrix_world @ mathutils.Vector(c) for c in ob.bound_box]
    cen = sum(vs, mathutils.Vector((0, 0, 0))) / 8.0
    ob.location += (Vector(loc) - cen)
    bpy.context.view_layer.update()
    ob.name = nm
    for p in ob.data.polygons:
        p.use_smooth = False
    M(ob, matl or M_STEEL)
    if mech:
        ob["mech"] = mech
        ob["link"] = "outer"
        ob["pivot"] = (round(pivot.x, 3), round(pivot.y, 3), round(pivot.z, 3))
        ob["knee"] = (0.0, 0.0, 0.0)
        dvn = Vector(aim).normalized()
        ob["dir"] = (round(dvn.x, 4), round(dvn.y, 4), round(dvn.z, 4))
        ob["tele"] = [0, 0.0]
    return ob

GROUND_Z = -1.06
LEG_MAX = 1.20          # 三节全伸出的总长
TEL1 = 0.40             # 中筒缩回行程
TEL2 = 0.80             # 内杆缩回行程（含脚垫）

for i in range(3):
    a = i * 2 * math.pi / 3 + math.pi / 2
    ux, uy = math.cos(a), math.sin(a)
    R = ell_r(a)
    rad = Vector((ux, uy, 0.0))          # 径向（水平）
    tan = Vector((-uy, ux, 0.0))         # 切向（销轴 / 门铰轴）
    mech = "gear%d" % i

    H = rad * (R * 0.42) + Vector((0, 0, -0.30))          # 髋铰（壳内）
    DROP = GROUND_Z - H.z
    HORZ = math.sqrt(max(0.01, LEG_MAX ** 2 - DROP ** 2))
    F = H + rad * HORZ + Vector((0, 0, DROP))             # 脚落点
    dv = (F - H).normalized()                             # 腿轴向

    # ---- 舱门整流罩（静态件，罩住穿出点）----
    S = shell_hit(H, F)
    cowl = P("cone", r=0.125, r2=0.108, h=0.048, loc=S - dv * 0.006, v=18)
    cowl.rotation_euler = dv.to_track_quat('Z', 'Y').to_euler()
    cowl.name = "gear%d_cowl" % i
    cowl["mech"] = "gear%d" % i; cowl["link"] = "cowl"
    cowl["pivot"] = (round(H.x, 3), round(H.y, 3), round(H.z, 3))
    cowl["dir"] = (round(dv.x, 4), round(dv.y, 4), round(dv.z, 4))
    cowl["tele"] = [0, 0.0]
    M(cowl, M_FRAME)
    cowl_fl = P("torus", R=0.108, r=0.009, loc=S + dv * 0.016, s1=22, s2=6)
    cowl_fl.rotation_euler = dv.to_track_quat('Z', 'Y').to_euler()
    cowl_fl.name = "gear%d_cowl_fl" % i
    cowl_fl["mech"] = "gear%d" % i; cowl_fl["link"] = "cowl"
    cowl_fl["pivot"] = (round(H.x, 3), round(H.y, 3), round(H.z, 3))
    cowl_fl["dir"] = (round(dv.x, 4), round(dv.y, 4), round(dv.z, 4))
    cowl_fl["tele"] = [0, 0.0]
    M(cowl_fl, M_DARK)

    q = dv.to_track_quat('Z', 'Y').to_euler()   # 沿腿轴的旋转

    def tag(o, link, tele=None, name=None):
        o["mech"] = mech
        o["link"] = link
        o["pivot"] = (round(H.x, 3), round(H.y, 3), round(H.z, 3))
        o["knee"] = (0.0, 0.0, 0.0)
        o["dir"] = (round(dv.x, 4), round(dv.y, 4), round(dv.z, 4))
        o["tele"] = list(tele) if tele else [0, 0.0]
        if name:
            o.name = "gear%d_%s" % (i, name)
        return o

    # ================= 第 1 节：外筒（固定）=================
    k = 0
    tag(rod(H + dv * 0.02, H + dv * 0.44, 0.078, M_FRAME), "outer", None,
        "outer_tube")
    # 外筒加强箍
    for t in (0.12, 0.34):
        g = P("torus", R=0.086, r=0.012, loc=H + dv * t, s1=28, s2=6)
        g.rotation_euler = q
        tag(M(g, M_STEEL) or g, "outer", None, "outer_ring_%d" % k); k += 1
    # 两侧导轨条
    for s in (-1, 1):
        gd = P("box", sx=0.020, sy=0.030, sz=0.38,
               loc=H + dv * 0.22 + tan * (0.072 * s), rot=(0, 0, a))
        gd.rotation_euler = dv.to_track_quat('Z', 'Y').to_euler()
        tag(M(gd, M_STEEL) or gd, "outer", None, "outer_rail_%d" % s)
    # 髋双耳片 + 销轴
    for s in (-1, 1):
        ear = P("box", sx=0.150, sy=0.026, sz=0.150,
                loc=H + tan * (0.068 * s), rot=(0, 0, a))
        tag(M(ear, M_FRAME) or ear, "outer", None, "hip_ear_%d" % s)
    tag(pin(H, tan, 0.115, 0.030, M_STEEL), "outer", None, "hip_pin")

    # ================= 第 2 节：中筒（可伸缩）=================
    tag(rod(H + dv * 0.40, H + dv * 0.84, 0.058, M_STEEL), "mid", (1, TEL1),
        "mid_tube")
    ms = P("torus", R=0.064, r=0.010, loc=H + dv * 0.82, s1=24, s2=6)
    ms.rotation_euler = q
    tag(M(ms, M_COPPER) or ms, "mid", (1, TEL1), "mid_seal")

    # ================= 第 3 节：内杆（可伸缩，带脚）=================
    tag(rod(H + dv * 0.80, H + dv * 1.20, 0.042, M_STEEL), "inner", (2, TEL2),
        "inner_rod")
    for t in (0.88, 1.02):
        pr = P("torus", R=0.048, r=0.009, loc=H + dv * t, s1=22, s2=6)
        pr.rotation_euler = q
        tag(M(pr, M_COPPER) or pr, "inner", (2, TEL2), "inner_piston_%d" % int(t * 100))
    # 脚垫 + 橡胶圈 + 支撑肋
    pad = P("cyl", r=0.140, h=0.040, loc=(F.x, F.y, GROUND_Z + 0.020), v=28)
    tag(M(pad, M_DARK) or pad, "inner", (2, TEL2), "foot_pad")
    ring = P("torus", R=0.140, r=0.016, loc=(F.x, F.y, GROUND_Z + 0.008), s1=40, s2=8)
    tag(M(ring, M_COPPER) or ring, "inner", (2, TEL2), "foot_ring")
    for k2 in range(3):
        aa = k2 * 2 * math.pi / 3 + a
        rb = P("box", sx=0.050, sy=0.020, sz=0.105,
               loc=(F.x + math.cos(aa) * 0.088, F.y + math.sin(aa) * 0.088, GROUND_Z + 0.062),
               rot=(0, 0, aa))
        tag(M(rb, M_STEEL) or rb, "inner", (2, TEL2), "foot_rib_%d" % k2)
    # 脚垫与内杆的连接锥
    fc = P("cone", r=0.075, r2=0.045, h=0.10, loc=F - dv * 0.05, v=16)
    fc.rotation_euler = q
    tag(M(fc, M_FRAME) or fc, "inner", (2, TEL2), "foot_cone")

    # ================= 真实件（STEP 转换）=================
    # 氮气弹簧：全程贴着外筒做减震（美森 MQQ150-025，放大到 0.28 m）
    load_stl_part("gas_spring.stl", 0.28, H + dv * 0.34 + tan * 0.135,
                  dv, "gear%d_gasspring" % i, mech="gear%d" % i, pivot=H, thick=1.6)
    # 法兰轴承座：套在髋销轴上（粤隆达 FA G3BLA）
    load_stl_part("fa_g3bla.stl", 0.135, H - tan * 0.105,
                  tan, "gear%d_flange" % i, mech="gear%d" % i, pivot=H, matl=M_FRAME)
    # 传动小齿轮 + 紧固螺栓（枫信 GB_T12369 / 工业熊 ASME）
    load_stl_part("drive_gbt.stl", 0.075, H + dv * 0.86 + tan * 0.105,
                  dv, "gear%d_gear" % i, mech="gear%d" % i, pivot=H, matl=M_COPPER)
    load_stl_part("fastener_asme.stl", 0.085, H + dv * 0.12 + tan * 0.145,
                  dv, "gear%d_bolt" % i, mech="gear%d" % i, pivot=H)
    # 支架连接件（诺瑞朗）
    load_stl_part("norulan.stl", 0.10, H + dv * 0.58 - tan * 0.115,
                  dv, "gear%d_bracket" % i, mech="gear%d" % i, pivot=H, matl=M_FRAME)

    # ================= 舱门（2 片，铰接在穿出点两侧）================
    for sgn, tg in ((-1, "L"), (1, "R")):
        Hinge = S + tan * (0.215 * sgn)
        door = P("box", sx=0.46, sy=0.285, sz=0.026,
                 loc=Hinge - tan * (0.142 * sgn) - dv * 0.010, rot=(0, 0, a))
        M(door, M_FRAME); bev(door, 0.004)
        rib = P("box", sx=0.40, sy=0.034, sz=0.034,
                loc=Hinge - tan * (0.142 * sgn) - dv * 0.032, rot=(0, 0, a))
        M(rib, M_STEEL)
        # 门外表面一道铜饰条，收起关闭时能一眼看到"舱门"
        strip = P("box", sx=0.42, sy=0.020, sz=0.008,
                  loc=Hinge - tan * (0.142 * sgn) + dv * 0.006, rot=(0, 0, a))
        M(strip, M_COPPER)
        for o, nm in ((door, "plate"), (rib, "rib"), (strip, "strip")):
            o.name = "gear%d_door%s_%s" % (i, tg, nm)
            o["mech"] = "gear%d_door%s" % (i, tg)
            o["pivot"] = (round(Hinge.x, 3), round(Hinge.y, 3), round(Hinge.z, 3))
            o["knee"] = (0.0, 0.0, 0.0)
            o["link"] = "door"


# ---------------- B 负质量核系统 ----------------
CORE_Z = 0.035
# 低温杜瓦（外层）
dewar = P("cyl", r=0.56, h=0.52, loc=(0,0,CORE_Z), v=56); M(dewar, M_GLASS); bev(dewar,0.01)
dw_lid = P("torus", R=0.56, r=0.035, loc=(0,0,CORE_Z+0.26), s1=64, s2=10); M(dw_lid, M_FRAME)
dw_bot = P("torus", R=0.56, r=0.035, loc=(0,0,CORE_Z-0.26), s1=64, s2=10); M(dw_bot, M_FRAME)
# 真空腔（玻璃）
vac = P("sphere", r=0.46, loc=(0,0,CORE_Z), s=40, rc=24); M(vac, M_GLASS)
# 负质量核
core = P("sphere", r=0.255, loc=(0,0,CORE_Z), s=40, rc=24); M(core, M_CORE)
# 6 组超导约束线圈（环绕核）
coils = []
for i, z in enumerate((-0.24, -0.14, -0.04, 0.06, 0.16, 0.26)):
    c = P("torus", R=0.40, r=0.024, loc=(0,0,CORE_Z+z), s1=56, s2=10)
    M(c, M_COPPER); coils.append(c)
# 场整形环（2）
for z in (-0.30, 0.32):
    f = P("torus", R=0.50, r=0.018, loc=(0,0,CORE_Z+z), s1=64, s2=8)
    M(f, M_LEDG)
# 磁悬浮轴承（4 个，赤道 + 两极）
bear = []
for i in range(4):
    a = i*math.pi/2
    b = P("torus", R=0.315, r=0.020, loc=(math.cos(a)*0.315, math.sin(a)*0.315, CORE_Z), s1=32, s2=8)
    M(b, M_STEEL); bear.append(b)
# 冷头 / 低温管路
for i in range(4):
    a = i*math.pi/2 + math.pi/4
    p = P("cyl", r=0.035, h=0.34, loc=(math.cos(a)*0.62, math.sin(a)*0.62, CORE_Z-0.02), v=12)
    M(p, M_STEEL)

# 核舱支撑柱（4 根，顶住环梁）
for i in range(4):
    a = i * math.pi / 2
    col = P("box", sx=0.075, sy=0.075, sz=0.30,
            loc=(math.cos(a) * 1.30, math.sin(a) * 1.30, 0.12), rot=(0, 0, a))
    M(col, M_STEEL)

# ---------------- C 能源 ----------------
pw = []
for i in range(4):
    a = i*math.pi/2 + math.pi/4
    x, y = math.cos(a)*1.02, math.sin(a)*1.02
    box = P("box", sx=0.38, sy=0.26, sz=0.22, loc=(x, y, -0.10), rot=(0,0,a))
    M(box, M_FRAME); bev(box, 0.008); pw.append(box)
# 电池格纹
    for k in range(3):
        g = P("box", sx=0.30, sy=0.02, sz=0.03, loc=(x, y, -0.10 + (k-1)*0.06), rot=(0,0,a))
        M(g, M_DARK); pw.append(g)
# 主汇流排（铜，从中心到 4 个电源柜）
bus = []
for i in range(4):
    a = i*math.pi/2 + math.pi/4
    b = P("box", sx=0.72, sy=0.075, sz=0.02, loc=(math.cos(a)*0.66, math.sin(a)*0.66, -0.035), rot=(0,0,a))
    M(b, M_COPPER); bus.append(b)
# 配电箱（2）
for i, (x, y) in enumerate(((0.42, -0.55), (-0.42, -0.55))):
    jb = P("box", sx=0.20, sy=0.16, sz=0.14, loc=(x, y, -0.04))
    M(jb, M_FRAME); bev(jb, 0.005)
    led = P("sphere", r=0.022, loc=(x, y, 0.045), s=14, rc=8); M(led, M_LEDG)

# ---------------- D 冷却 ----------------
pumps = []
for i, (x, y) in enumerate(((1.12, -0.32), (-1.12, -0.32))):
    p = P("cyl", r=0.115, h=0.24, loc=(x, y, -0.03), rot=(math.radians(90),0,0), v=20)
    M(p, M_STEEL); pumps.append(p)
    t = P("torus", R=0.125, r=0.016, loc=(x, y, 0.10), s1=28, s2=8); M(t, M_COPPER)

# ---------------- E 航电 ----------------
for i, (x, y) in enumerate(((0.55, -0.85), (0.0, -0.95))):
    a = P("box", sx=0.26, sy=0.20, sz=0.16, loc=(x, y, -0.03))
    M(a, M_FRAME); bev(a, 0.006)
    for k in range(3):
        l = P("sphere", r=0.014, loc=(x-0.08+k*0.08, y+0.10, 0.055), s=10, rc=6)
        M(l, M_LED if k%2 else M_LEDG)

# ---------------- F 座舱 ----------------
seat = P("box", sx=0.32, sy=0.34, sz=0.16, loc=(0, -1.18, 0.02)); M(seat, M_DARK)
back = P("box", sx=0.34, sy=0.06, sz=0.26, loc=(0, -1.02, 0.10)); M(back, M_DARK)
con = P("box", sx=0.46, sy=0.12, sz=0.12, loc=(0, -1.40, 0.00)); M(con, M_FRAME)
panel = P("box", sx=0.44, sy=0.05, sz=0.16, loc=(0, -1.46, 0.14), rot=(math.radians(-20),0,0)); M(panel, M_FRAME)
for k in range(4):
    scr = P("box", sx=0.075, sy=0.008, sz=0.055, loc=(-0.15+k*0.10, -1.485, 0.155), rot=(math.radians(-20),0,0))
    M(scr, M_LEDG)

# ---------------- G 推进 ----------------
for sgn in (-1, 1):
    x = sgn*1.34
    pod = P("sphere", r=1.0, s=28, rc=16); pod.scale=(0.28,0.56,0.20); apply(pod); pod.location=(x,0,-0.04)
    M(pod, M_FRAME); bev(pod,0.008)
    sh = P("torus", R=0.185, r=0.026, loc=(x, 0, -0.22), s1=40, s2=10); M(sh, M_FRAME)
    inn = P("cone", r=0.155, r2=0.09, h=0.12, loc=(x, 0, -0.27), rot=(math.pi,0,0), v=32); M(inn, M_DARK)
    gl = P("sphere", r=0.11, loc=(x, 0, -0.285), s=18, rc=10); gl.scale=(1,1,0.3); apply(gl); M(gl, M_CORE)
    for _o, _n in ((sh, "shroud"), (inn, "inner"), (gl, "glow")):
        _o.name = "nozzle%d_%s" % (sgn, _n)
        _o["mech"] = "nozzle%d" % sgn
        _o["pivot"] = (round(x, 3), 0.0, -0.16)
    for k in range(3):
        a = k*2*math.pi/3
        act = P("cyl", r=0.016, h=0.10, loc=(x+math.cos(a)*0.17, math.sin(a)*0.17, -0.20), v=10); M(act, M_STEEL)

# ---------------- 线束（真实走向 + 卡箍） ----------------
def cable(name, pts, rad=0.012, m=M_CABLE):
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions='3D'
    cu.bevel_depth = rad; cu.bevel_resolution = 3; cu.resolution_u = 6
    sp = cu.splines.new('BEZIER'); sp.bezier_points.add(len(pts)-1)
    for i,p in enumerate(pts):
        sp.bezier_points[i].co = p
        sp.bezier_points[i].handle_left_type='AUTO'; sp.bezier_points[i].handle_right_type='AUTO'
    ob = bpy.data.objects.new(name, cu); bpy.context.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob; ob.select_set(True)
    bpy.ops.object.convert(target='MESH'); ob = bpy.context.object
    M(ob, m)
    return ob

# 电源柜 -> 配电箱
for sgn, ex in ((-1, (-1.02,0.0)), (1, (1.02,0.0))):
    cable("bus_L%d" % sgn, [(sgn*0.72, -0.72, -0.05), (sgn*0.55, -0.62, -0.02), (sgn*0.42, -0.55, 0.02)], 0.010)
# 配电箱 -> 航电
cable("av1", [(0.42,-0.55,0.02), (0.46,-0.70,0.03), (0.55,-0.85,0.02)], 0.008)
cable("av2", [(-0.42,-0.55,0.02), (-0.30,-0.78,0.03), (0.0,-0.95,0.02)], 0.008)
# 航电 -> 座舱
cable("ck1", [(0.55,-0.85,0.03), (0.25,-1.02,0.06), (0.0,-1.16,0.02)], 0.008)
# 核 -> 电源柜（主馈线）
for i in range(4):
    a = i*math.pi/2 + math.pi/4
    cable("feed%d" % i, [(math.cos(a)*0.60, math.sin(a)*0.60, CORE_Z),
                          (math.cos(a)*0.85, math.sin(a)*0.85, -0.05),
                          (math.cos(a)*1.02, math.sin(a)*1.02, -0.10)], 0.014)
# 冷却回路
cable("cool_L", [(0.60,0.0,CORE_Z-0.18), (0.95,-0.10,-0.10), (1.12,-0.32,0.0)], 0.016, M_STEEL)
cable("cool_R", [(-0.60,0.0,CORE_Z-0.18), (-0.95,-0.10,-0.10), (-1.12,-0.32,0.0)], 0.016, M_STEEL)
# 核 -> 喷口（作动 / 工质）
for sgn in (-1, 1):
    cable("thr%d" % sgn, [(sgn*0.30, 0.10, CORE_Z), (sgn*0.85, 0.16, -0.02), (sgn*1.30, 0.10, -0.16)], 0.011)

# 线束卡箍
cl = []
for pts in ([(0.42,-0.55,0.02),(0.46,-0.70,0.03),(0.55,-0.85,0.02)],
            [(-0.42,-0.55,0.02),(-0.30,-0.78,0.03),(0.0,-0.95,0.02)]):
    for t in (0.35, 0.7):
        seg = 0 if t < 0.5 else 1
        lt = t*2 if t < 0.5 else (t-0.5)*2
        a = Vector(pts[seg]); b = Vector(pts[seg+1])
        p = a.lerp(b, lt)
        o = P("box", sx=0.036, sy=0.036, sz=0.018, loc=(p.x,p.y,p.z)); M(o, M_DARK); cl.append(o)

# ---------------- 可选的收起姿态（渲染收放对比图用）----------------
# 与 three.js 完全一致的顺序：先把伸缩节缩回 -> 再整体绕髋铰翻转
FOLDED = ("folded" in args)
FOLD_ANG = -0.68        # 恰好把腿转到水平，贴壳体底面内侧；再多就会顶到电源柜
if FOLDED:
    GEAR_ROT = {}
    for _i in range(3):
        _a = _i * 2 * math.pi / 3 + math.pi / 2
        _R = ell_r(_a)
        _rad = Vector((math.cos(_a), math.sin(_a), 0.0))
        _tan = Vector((-math.sin(_a), math.cos(_a), 0.0))
        GEAR_ROT[_i] = (_rad * (_R * 0.42) + Vector((0, 0, -0.30)), _tan)

    def _rot_about(pt, axis, ang):
        Tm = Matrix.Translation(pt)
        return Tm @ Matrix.Rotation(ang, 4, axis) @ Tm.inverted()

    for ob in list(bpy.data.objects):
        if ob.type != 'MESH':
            continue
        _mech = ob.get("mech") or ""
        if not _mech.startswith("gear"):
            continue
        _link = ob.get("link") or ""
        if _link in ("door", "cowl"):
            continue
        _i = int(_mech[4])
        _H, _tan = GEAR_ROT[_i]
        _tele = list(ob.get("tele") or (0, 0.0))
        _dir = list(ob.get("dir") or (0, 0, 0))
        M4 = Matrix.Identity(4)
        if int(_tele[0]) > 0 and (abs(_dir[0]) + abs(_dir[1]) + abs(_dir[2])) > 1e-6:
            M4 = Matrix.Translation(Vector(_dir) * (-float(_tele[1])))
        M4 = _rot_about(_H, _tan, FOLD_ANG) @ M4
        ob.matrix_world = M4 @ ob.matrix_world
    bpy.context.view_layer.update()

# ---------------- 爆炸视图（可选，args 里带 explode 或 explode=1.5）----------------
EXPLODE = 0.0
for _a in args:
    if _a == "explode":
        EXPLODE = 1.0
    elif _a.startswith("explode="):
        try:
            EXPLODE = float(_a.split("=")[1])
        except Exception:
            pass

if EXPLODE > 0:
    for ob in list(bpy.data.objects):
        if ob.type != 'MESH' or ob.name == 'ground':
            continue
        vs = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        c = sum(vs, Vector((0, 0, 0))) / 8.0
        span = max((max(v[i] for v in vs) - min(v[i] for v in vs)) for i in range(3))
        mech = ob.get("mech") or ""
        rr = math.hypot(c.x, c.y)
        if span > 2.5:                                  # 外壳 / 主梁
            dirv = Vector((0, 0, 1)); amt = 0.55
        elif mech.startswith("gear"):                    # 起落架沿腿轴散开
            d = ob.get("dir")
            dirv = Vector((d[0], d[1], d[2])).normalized() if d else Vector((c.x, c.y, -1)).normalized()
            amt = 0.50
        elif c.z > 0.02 and rr < 0.80:                   # 核系统向上
            dirv = Vector((0, 0, 1)); amt = 0.85
        elif c.z < -0.12:                                 # 底部设备向下外
            dirv = Vector((c.x / max(rr, 1e-6), c.y / max(rr, 1e-6), -0.5)).normalized()
            amt = 0.60
        else:                                             # 其余径向散开
            dirv = Vector((0, 0, 1)) if rr < 1e-6 else Vector((c.x / rr, c.y / rr, 0.25)).normalized()
            amt = 0.65
        ob.location += dirv * (amt * EXPLODE)
    bpy.context.view_layer.update()

# ---------------- 世界 / 灯光 ----------------
w = bpy.data.worlds.new("W"); bpy.context.scene.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.010, 0.013, 0.022, 1)

def light(loc, e, size=6.0, c=(1,1,1)):
    bpy.ops.object.light_add(type='AREA', location=loc)
    L = bpy.context.object; L.data.energy = e; L.data.size = size; L.data.color = c
    L.rotation_euler = (Vector((0,0,-0.05)) - L.location).to_track_quat('-Z','Y').to_euler()

light((4.6,-5.2,6.4), 2600, 8, (1.0,0.96,0.92))
light((-5.8,-1.4,2.6), 900, 9, (0.52,0.64,1.0))
light((0.8,6.0,3.6), 1200, 7, (1.0,0.80,0.95))
light((0,-0.6,-4.6), 320, 9, (0.55,0.65,1.0))

bpy.ops.mesh.primitive_plane_add(size=60, location=(0,0,-1.085))
gp = bpy.context.object; gp.name = "ground"
M(gp, mat("ground", (0.008,0.010,0.015), 0.35, 0.78))

# ---------------- 相机（自动取景） ----------------
def bbox():
    mn = Vector((1e9,1e9,1e9)); mx = Vector((-1e9,-1e9,-1e9))
    for o in bpy.data.objects:
        if o.name == 'ground' or o.type not in ('MESH','FONT'): continue
        for c in o.bound_box:
            wv = o.matrix_world @ Vector(c)
            for i in range(3):
                if wv[i] < mn[i]: mn[i] = wv[i]
                if wv[i] > mx[i]: mx[i] = wv[i]
    return mn, mx

mn, mx = bbox(); ctr = (mn+mx)*0.5
DIRS = {"hero": Vector((0.66,-0.70,0.16)), "top": Vector((0.0,0.001,1.0)),
        "front": Vector((0.02,-1.0,0.26)), "side": Vector((1.0,-0.02,0.24)),
        "cut": Vector((0.60,-0.64,0.66)), "cutside": Vector((1.0,-0.30,0.52))}
d = DIRS.get(VIEW, DIRS["hero"]).normalized()
fwd = (-d).normalized(); wu = Vector((0,0,1))
if abs(fwd.dot(wu)) > 0.98: wu = Vector((0,1,0))
right = fwd.cross(wu).normalized(); up2 = right.cross(fwd).normalized()
hx = hy = 0.0
for ix in (mn.x,mx.x):
    for iy in (mn.y,mx.y):
        for iz in (mn.z,mx.z):
            v = Vector((ix,iy,iz)) - ctr
            hx = max(hx, abs(v.dot(right))); hy = max(hy, abs(v.dot(up2)))

LENS = 55.0
fovx = 2*math.atan(18.0/LENS); asp = RESX/float(RESY)
fovy = 2*math.atan(math.tan(fovx*0.5)/asp)
bpy.ops.object.camera_add(location=ctr + d*10)
cam = bpy.context.object; cam.data.lens = LENS; cam.data.sensor_fit = 'HORIZONTAL'
if VIEW == "hero":
    cam.data.type = 'PERSP'
    dist = max(hx/math.tan(fovx*0.5), hy/math.tan(fovy*0.5)) * (1.10 if ANNOT else 1.02)
else:
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = 2*max(hx, hy*asp) * (1.10 if ANNOT else 1.02)
    dist = (hx+hy)*3+5
cam.location = ctr + d*dist
cam.rotation_euler = (ctr - cam.location).to_track_quat('-Z','Y').to_euler()
bpy.context.scene.camera = cam

# ---------------- 标注 ----------------
if ANNOT:
    MT = mat("t", (1,1,1), 0, .5, (1,1,1), 6)
    MD = mat("d", (.35,.75,1), 0, .5, (.25,.65,1), 5)
    def line(a,b,r=0.004,m=MD):
        a=Vector(a); b=Vector(b); dd=b-a; L=dd.length
        if L<1e-6: return
        bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=L, vertices=8, location=(a+b)/2)
        o=bpy.context.object; o.rotation_euler=dd.to_track_quat('Z','Y').to_euler(); M(o,m)
    def txt(s, loc, size=.115, m=None):
        bpy.ops.object.text_add(location=loc); t=bpy.context.object
        t.data.body=s; t.data.size=size; t.data.align_x='CENTER'; t.data.align_y='CENTER'
        if CJK: t.data.font = CJK
        t.rotation_euler=bpy.context.scene.camera.rotation_euler.copy(); M(t, m or MT)
    def call(s,p,lead,size=.11):
        a=Vector(p); b=a+Vector(lead); line(a,b,.0035,MT); txt(s,b+Vector((0,0,.05)),size,MT)

    call("负质量核（真空腔内）",(0,0,CORE_Z),(0.0,0.0,0.62),.105)
    call("超导约束线圈 x6",(0.40,0,CORE_Z+0.10),(0.60,0.32,0.44))
    call("磁悬浮轴承 x4",(0.315,0,CORE_Z),(0.56,-0.32,0.10))
    call("低温杜瓦",(-0.60,0,CORE_Z+0.10),(-0.70,-0.10,0.34))
    call("承力环梁",(1.56,0,-0.02),(0.62,0.42,0.10))
    call("电源柜 x4",(0.72,0.72,-0.10),(0.08,0.52,0.46))
    call("主汇流排（铜）",(0.40,0.66,-0.035),(0.02,0.22,0.30))
    call("配电箱",(0.42,-0.55,-0.04),(0.10,-0.30,0.34))
    call("航电单元",(0.0,-0.95,-0.03),(-0.54,-0.18,0.36))
    call("冷却泵",(1.12,-0.32,-0.03),(0.28,-0.64,0.22))
    call("座舱",(0,-1.18,0.02),(-0.60,-0.34,0.16))
    call("万向主喷口",(1.34,0,-0.27),(0.64,-0.54,-0.02))
    call("设备甲板",(-1.20,-0.40,-0.155),(-0.30,-0.20,0.30))

    bpy.context.view_layer.update()
    mn2, mx2 = bbox(); ctr2 = (mn2+mx2)*0.5
    hx2 = hy2 = 0.0
    for ix in (mn2.x,mx2.x):
        for iy in (mn2.y,mx2.y):
            for iz in (mn2.z,mx2.z):
                v = Vector((ix,iy,iz)) - ctr2
                hx2 = max(hx2, abs(v.dot(right))); hy2 = max(hy2, abs(v.dot(up2)))
    dist2 = max(hx2/math.tan(fovx*0.5), hy2/math.tan(fovy*0.5)) * 1.02
    cam.location = ctr2 + d*dist2
    cam.rotation_euler = (ctr2 - cam.location).to_track_quat('-Z','Y').to_euler()
    for o in bpy.data.objects:
        if o.type == 'FONT':
            o.rotation_euler = cam.rotation_euler.copy()

# ---------------- 导出 JSON（给 three.js 用）----------------
if EXPORT:
    import json as _json
    parts = []
    for ob in bpy.data.objects:
        if ob.type != 'MESH' or ob.name == 'ground':
            continue
        me = ob.to_mesh()
        me.calc_loop_triangles()
        mw = ob.matrix_world
        nmat = mw.to_3x3().inverted().transposed()
        V = []; Nn = []; I = []
        for vv in me.vertices:
            pp = mw @ vv.co
            V += [round(pp.x, 4), round(pp.y, 4), round(pp.z, 4)]
            nn = (nmat @ vv.normal).normalized()
            Nn += [round(nn.x, 3), round(nn.y, 3), round(nn.z, 3)]
        for tr in me.loop_triangles:
            I += [tr.vertices[0], tr.vertices[1], tr.vertices[2]]
        mat = ob.data.materials[0] if ob.data.materials else None
        base = [0.6, 0.6, 0.6]; metal = 0.0; rough = 0.5; emit = [0, 0, 0]; es = 0.0; alpha = 1.0
        if mat and mat.use_nodes:
            b = mat.node_tree.nodes.get("Principled BSDF")
            if b:
                base = list(b.inputs["Base Color"].default_value)[:3]
                metal = float(b.inputs["Metallic"].default_value)
                rough = float(b.inputs["Roughness"].default_value)
                emit = list(b.inputs["Emission"].default_value)[:3]
                es = float(b.inputs["Emission Strength"].default_value)
                alpha = float(b.inputs["Alpha"].default_value)
        parts.append({
            "name": ob.name,
            "v": V, "n": Nn, "i": I,
            "color": [round(c, 4) for c in base],
            "metal": round(metal, 3), "rough": round(rough, 3),
            "emit": [round(c, 4) for c in emit], "es": round(es, 2),
            "alpha": round(alpha, 3),
            "bbox": [round(x, 3) for x in
                     [min(V[0::3]), min(V[1::3]), min(V[2::3]),
                      max(V[0::3]), max(V[1::3]), max(V[2::3])]],
            "mech": (ob.get("mech") or ""),
            "pivot": list(ob.get("pivot") or (0, 0, 0)),
            "link": (ob.get("link") or ""),
            "knee": list(ob.get("knee") or (0, 0, 0)),
            "tq": list(ob.get("tq") or (0, 0, 0)),
            "dir": list(ob.get("dir") or (0, 0, 0)),
            "tele": list(ob.get("tele") or (0, 0.0)),
        })
        ob.to_mesh_clear()
    out = os.path.join(OUT, "ag1_model.json")
    with open(out, "w", encoding="utf-8") as f:
        _json.dump({"parts": parts}, f, ensure_ascii=False, separators=(",", ":"))
    print("EXPORTED", out, "parts", len(parts),
          "tris", sum(len(p["i"]) // 3 for p in parts),
          "size_kb", round(os.path.getsize(out) / 1024, 1))
    raise SystemExit(0)

# ---------------- 渲染 ----------------
sc = bpy.context.scene
if ENGINE == "eevee":
    sc.render.engine = 'BLENDER_EEVEE'
    sc.eevee.taa_render_samples = SAMPLES
    sc.eevee.use_gtao = True
    sc.eevee.use_ssr = True
    sc.eevee.use_bloom = True
    sc.eevee.bloom_threshold = 1.4
    sc.eevee.bloom_intensity = 0.02
else:
    sc.render.engine = 'CYCLES'; sc.cycles.samples = SAMPLES; sc.cycles.use_denoising = True
sc.render.resolution_x = RESX; sc.render.resolution_y = RESY
sc.view_settings.view_transform = 'Filmic'
sc.render.filepath = os.path.join(OUT, OUTNAME + ".png")
bpy.ops.render.render(write_still=True)
print("DONE", sc.render.filepath, "engine", ENGINE)

