# -*- coding: utf-8 -*-
"""
AG-1 百万零件体系（mass parts）
================================
汽车 1~3 万件、A380 约 400 万件——其中绝大多数是紧固件与标准件。
本模块用「零件族 + 参数化分布」的方式，把 AG-1 从 563 个独立部件
扩展到百万级零件，且文件只增加几 KB（算法即数据）。

设计要点
--------
1. 每个族（family）只存：几何键、数量、分布参数、材质。
2. 分布算法写成**解析式**（无随机数或固定种子），Python 与 JS 各实现一遍,
   两端结果一致 → Blender 渲染图与浏览器交互页看到的是同一台机器。
3. 几何用极低模（铆钉 12 三角、瓦片 2 三角），靠数量而非单件精度堆真实感。
4. Blender 渲染时降采样（只画一部分），因为屏幕上铆钉只有 1~2 像素。
"""
import math
import numpy as np

HX, HY, HZ = 1.62, 1.86, 0.52


# ============================================================
# 1. 共享几何（低模，单位 mm，原点在底面中心，+Z 为外法线）
# ============================================================
def _disk(r, h, seg=4, taper=0.55):
    """锥台：底面 r，顶面 r*taper，高 h，seg 边"""
    vs = []
    for k in range(seg):
        a = 2 * math.pi * k / seg + math.pi / seg
        vs.append((r * math.cos(a), r * math.sin(a), 0.0))
    for k in range(seg):
        a = 2 * math.pi * k / seg + math.pi / seg
        vs.append((r * taper * math.cos(a), r * taper * math.sin(a), h))
    ts = []
    # 侧面
    for k in range(seg):
        k2 = (k + 1) % seg
        ts.append((k, k2, seg + k2))
        ts.append((k, seg + k2, seg + k))
    # 顶盖
    for k in range(1, seg - 1):
        ts.append((seg, seg + k, seg + k + 1))
    return vs, ts


def _quad(w, d):
    """平面方片（贴面），朝 +Z"""
    hw, hd = w * 0.5, d * 0.5
    return ([(-hw, -hd, 0.0), (hw, -hd, 0.0), (hw, hd, 0.0), (-hw, hd, 0.0)],
            [(0, 1, 2), (0, 2, 3)])


def _hexhead(r=5.0, h=3.0, shank_r=2.0, shank_h=8.0):
    """六角头螺栓：头 6 边 + 杆"""
    vs, ts = [], []
    for k in range(6):
        a = 2 * math.pi * k / 6
        vs.append((r * math.cos(a), r * math.sin(a), 0.0))
    for k in range(6):
        a = 2 * math.pi * k / 6
        vs.append((r * math.cos(a), r * math.sin(a), h))
    for k in range(6):
        k2 = (k + 1) % 6
        ts.append((k, k2, 6 + k2))
        ts.append((k, 6 + k2, 6 + k))
    for k in range(1, 5):
        ts.append((6, 6 + k, 6 + k + 1))
    # 杆（4 边）
    b = len(vs)
    for k in range(4):
        a = 2 * math.pi * k / 4 + math.pi / 4
        vs.append((shank_r * math.cos(a), shank_r * math.sin(a), -shank_h))
    for k in range(4):
        a = 2 * math.pi * k / 4 + math.pi / 4
        vs.append((shank_r * math.cos(a), shank_r * math.sin(a), 0.0))
    for k in range(4):
        k2 = (k + 1) % 4
        ts.append((b + k, b + k2, b + 4 + k2))
        ts.append((b + k, b + 4 + k2, b + 4 + k))
    return vs, ts


def _ring(r=3.0, t=1.0, seg=6):
    """扁平垫圈（环片）"""
    vs = []
    for k in range(seg):
        a = 2 * math.pi * k / seg
        vs.append((r * math.cos(a), r * math.sin(a), 0.0))
    for k in range(seg):
        a = 2 * math.pi * k / seg
        vs.append(((r - t) * math.cos(a), (r - t) * math.sin(a), 0.0))
    ts = []
    for k in range(seg):
        k2 = (k + 1) % seg
        ts.append((k, k2, seg + k2))
        ts.append((k, seg + k2, seg + k))
    return vs, ts


GEOMS = {}


def _reg(name, vt):
    vs, ts = vt
    flat = []
    for t in ts:
        flat.extend(t)
    GEOMS[name] = {"v": [round(c, 4) for v in vs for c in v], "i": flat}


_reg("rivet", _disk(2.1, 1.3, 4, 0.6))          # 4 边铆钉头 12 三角
_reg("rivet_l", _disk(3.4, 1.6, 5, 0.6))        # 大铆钉
_reg("tile", _quad(17.0, 17.0))                 # 隔热瓦 2 三角
_reg("strand", _quad(3.0, 3.0))                 # 线股截面片
_reg("bolt", _hexhead(5.2, 3.2, 2.4, 9.0))      # M8 螺栓
_reg("washer", _ring(5.6, 1.3, 6))              # 垫圈
_reg("nut", _ring(5.0, 3.0, 6))                 # 螺母
_reg("solder", _disk(1.1, 0.7, 4, 0.4))         # 焊点
_reg("tooth", _quad(3.2, 9.0))                  # 散热齿片
_reg("bracket", _quad(16.0, 16.0))              # 角片
_reg("led", _disk(1.6, 0.8, 4, 0.5))            # 指示灯
_reg("screw", _disk(1.8, 1.1, 4, 0.5))          # 小螺钉


# ============================================================
# 2. 分布算法
# ============================================================
def sph(theta, phi, k=1.0):
    """椭球表面点（phi=pi/2 为赤道）"""
    return (HX * k * math.sin(phi) * math.cos(theta),
            HY * k * math.sin(phi) * math.sin(theta),
            HZ * k * math.cos(phi))


def snorm(theta, phi):
    p = sph(theta, phi)
    n = (p[0] / (HX * HX), p[1] / (HY * HY), p[2] / (HZ * HZ))
    m = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2) or 1.0
    return (n[0] / m, n[1] / m, n[2] / m)


def ell_circ(a, b):
    """椭圆周长（Ramanujan 近似）"""
    return math.pi * (3 * (a + b) - math.sqrt((3 * a + b) * (a + 3 * b)))


def gen_shell_rivets(pitch, k, phi0, phi1, stagger=True):
    """
    沿椭球表面按近似等面积分布铆钉。
    pitch: 单位 m 的弧长间距
    k    : 半径系数（1.0=外蒙皮，0.97=内衬）
    返回 numpy 数组 (N,6): x,y,z,nx,ny,nz
    """
    out = []
    # 总子午弧长
    Np = 4000
    arclen = 0.0
    prev = None
    for i in range(Np + 1):
        phi = phi0 + (phi1 - phi0) * i / Np
        p = sph(0.0, phi, k)
        if prev is not None:
            arclen += math.hypot(p[0] - prev[0], p[2] - prev[2])
        prev = p
    nrows = max(2, int(arclen / pitch))
    for r in range(nrows + 1):
        t = r / nrows
        phi = phi0 + (phi1 - phi0) * t
        a = HX * k * math.sin(phi)
        b = HY * k * math.sin(phi)
        circ = ell_circ(a, b)
        n = max(3, int(circ / pitch))
        off = 0.5 if (stagger and r % 2) else 0.0
        for j in range(n):
            th = 2 * math.pi * (j + off) / n
            p = sph(th, phi, k)
            nn = snorm(th, phi)
            out.append((p[0], p[1], p[2], nn[0], nn[1], nn[2]))
    return np.array(out, dtype=np.float32)


def gen_ring_rivets(radius_k, z_list, pitch, count_per_ring=None, k_scale=None):
    """沿水平环分布的铆钉（周向框）"""
    out = []
    for z, kx in z_list:
        kk = kx
        a = HX * kk * math.sqrt(max(0.0, 1 - (z / HZ) ** 2))
        b = HY * kk * math.sqrt(max(0.0, 1 - (z / HZ) ** 2))
        circ = ell_circ(a, b)
        n = count_per_ring or max(8, int(circ / pitch))
        for j in range(n):
            th = 2 * math.pi * j / n
            x = a * math.cos(th)
            y = b * math.sin(th)
            nx, ny, nz = x / (HX * HX), y / (HY * HY), z / (HZ * HZ)
            m = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            out.append((x, y, z, nx / m, ny / m, nz / m))
    return np.array(out, dtype=np.float32)


def gen_coil_strands(n_turns, seg_per_turn, radius_k, z0, dz, turns_r):
    """线圈利兹线股：每圈沿圆周均匀铺 seg_per_turn 段"""
    out = []
    for i in range(n_turns):
        z = z0 + (i - (n_turns - 1) * 0.5) * dz
        for j in range(seg_per_turn):
            th = 2 * math.pi * j / seg_per_turn
            x = HX * radius_k * math.cos(th)
            y = HY * radius_k * math.sin(th)
            out.append((x, y, z, 0.0, 0.0, 1.0))
    return np.array(out, dtype=np.float32)


def gen_harness_clamps(harness_pts, spacing, strands):
    """线束沿线卡/线股：沿折线每 spacing 米放一簇"""
    out = []
    for pts, r in harness_pts:
        for i in range(len(pts) - 1):
            a = np.array(pts[i]); b = np.array(pts[i + 1])
            L = float(np.linalg.norm(b - a))
            if L < 1e-6:
                continue
            n = max(1, int(L / spacing))
            for j in range(n):
                t = (j + 0.5) / n
                p = a + (b - a) * t
                d = (b - a) / L
                for s in range(strands):
                    ang = 2 * math.pi * s / strands
                    # 垂直于走向的圆截面
                    up = np.array([0.0, 0.0, 1.0])
                    if abs(float(np.dot(d, up))) > 0.95:
                        up = np.array([1.0, 0.0, 0.0])
                    u = np.cross(d, up); u /= (np.linalg.norm(u) or 1)
                    w = np.cross(d, u)
                    off = u * (r * math.cos(ang)) + w * (r * math.sin(ang))
                    q = p + off
                    out.append((q[0], q[1], q[2], d[0], d[1], d[2]))
    return np.array(out, dtype=np.float32) if out else np.zeros((0, 6), np.float32)


# ============================================================
# 3. 族清单
# ============================================================
def build_families():
    """返回 (families, geoms)。数量为设计目标，实际由生成函数决定。"""
    fams = []
    keep = {}

    def add(fid, geo, gen, params, color, metal, rough, emit=None, es=0.0, note=""):
        fams.append({
            "id": fid, "geo": geo, "gen": gen, "params": params,
            "color": color, "metal": metal, "rough": rough,
            "emit": emit, "es": es, "note": note,
        })
        keep[geo] = GEOMS[geo]

    D2R = math.radians

    # ---- 1. 外蒙皮铆钉：间距 9.2 mm，φ 6°~174° ----
    add("rivet_out", "rivet", "shell",
        {"pitch": 0.0086, "k": 1.0005, "phi0": D2R(6), "phi1": D2R(174), "stagger": 1},
        [0.62, 0.65, 0.70], 1.0, 0.30, note="外蒙皮铆钉")

    # ---- 2. 内衬板铆钉：k=0.988 ----
    add("rivet_inner", "rivet", "shell",
        {"pitch": 0.0118, "k": 0.9885, "phi0": D2R(10), "phi1": D2R(170), "stagger": 1},
        [0.55, 0.57, 0.62], 1.0, 0.34, note="内衬板铆钉")

    # ---- 3. 隔热瓦：15.8 mm 分块 ----
    add("tile", "tile", "shell",
        {"pitch": 0.0135, "k": 0.992, "phi0": D2R(8), "phi1": D2R(172), "stagger": 1},
        [0.80, 0.74, 0.62], 0.15, 0.72, note="隔热瓦")

    # ---- 3b. 面板缝两侧铆钉 ----
    add("rivet_seam", "rivet", "seams",
        {"phis": [D2R(18), D2R(42), D2R(62), D2R(78)],
         "meridians": 8, "pitch": 0.013, "rows": 3, "gap": 0.026},
        [0.50, 0.53, 0.58], 1.0, 0.36, note="面板缝铆钉")

    # ---- 4. 结构框铆钉：周向框 12 圈 ----
    zl = []
    for i in range(12):
        z = 0.34 - i * 0.062
        zl.append((z, 0.965))
    add("rivet_frame", "rivet_l", "ring",
        {"rings": zl, "pitch": 0.026},
        [0.58, 0.60, 0.66], 1.0, 0.32, note="结构框铆钉")

    # ---- 5. 线圈线股：30 圈 × 每圈 2400 段 ----
    add("coil_strand", "strand", "coil",
        {"turns": 30, "seg": 2400, "radius_k": 0.700, "z0": 0.062, "dz": 0.0085},
        [0.72, 0.45, 0.18], 1.0, 0.28, note="线圈利兹线股")

    # ---- 6. 紧固件组：螺栓 + 螺母 + 2 垫圈 ----
    nodes = []
    for i in range(16):
        a = 2 * math.pi * i / 16
        nodes.append((HX * 0.955 * math.cos(a), HY * 0.955 * math.sin(a), -0.055))
        nodes.append((HX * 0.78 * math.cos(a), HY * 0.78 * math.sin(a), -0.02))
        nodes.append((HX * 0.62 * math.cos(a), HY * 0.62 * math.sin(a), 0.012))
    add("bolt", "bolt", "nodes", {"nodes": nodes, "per_node": 40, "ring": 0.030},
        [0.60, 0.63, 0.68], 1.0, 0.26, note="结构螺栓")
    add("nut", "nut", "nodes", {"nodes": nodes, "per_node": 40, "ring": 0.030, "dz": -0.008},
        [0.58, 0.61, 0.66], 1.0, 0.30, note="螺母")
    add("washer", "washer", "nodes",
        {"nodes": nodes, "per_node": 80, "ring": 0.030, "dz": 0.036},
        [0.66, 0.69, 0.74], 1.0, 0.24, note="垫圈")

    # ---- 7. 散热齿片 ----
    fins = []
    for i in range(26):
        x = -0.19 + i * (0.38 / 25)
        fins.append((0.58 + x, 0.50, 0.030))
    add("tooth_inv", "tooth", "fins",
        {"row": fins, "per": 260, "span": 0.27},
        [0.68, 0.71, 0.76], 1.0, 0.28, note="逆变器散热齿")

    # ---- 8. 底部格栅齿 ----
    gr = []
    for i in range(6):
        a = 2 * math.pi * i / 6
        gr.append((HX * 0.62 * math.cos(a), HY * 0.62 * math.sin(a), -0.40))
    add("tooth_grille", "tooth", "grille",
        {"centers": gr, "rows": 26, "cols": 14, "dw": 0.011, "dd": 0.016},
        [0.30, 0.32, 0.36], 0.7, 0.48, note="底部格栅")

    # ---- 8b. 地板格栅条 ----
    fl = []
    for i in range(4):
        a = math.pi / 4 + i * math.pi / 2
        for r in (0.30, 0.42, 0.54):
            fl.append((HX * r * math.cos(a), HY * r * math.sin(a), -0.150))
    add("tooth_floor", "tooth", "grille",
        {"centers": fl, "rows": 22, "cols": 30, "dw": 0.014, "dd": 0.012},
        [0.42, 0.45, 0.50], 0.8, 0.45, note="地板格栅条")

    # ---- 8c. 线束扎带 ----
    add("zip", "screw", "node_fan",
        {"count": 48000, "r0": 0.55, "r1": 1.05, "z0": -0.35, "z1": 0.03, "seed": 9911},
        [0.18, 0.18, 0.20], 0.1, 0.62, note="线束扎带")

    # ---- 8d. 液压/冷却管卡 ----
    add("clamp_hyd", "screw", "node_fan",
        {"count": 15000, "r0": 0.70, "r1": 1.02, "z0": -0.28, "z1": -0.10, "seed": 3355},
        [0.55, 0.58, 0.63], 1.0, 0.34, note="管路卡箍")

    # ---- 8e. 绝缘子串 ----
    add("insulator", "screw", "node_fan",
        {"count": 20000, "r0": 0.45, "r1": 0.95, "z0": -0.26, "z1": 0.04, "seed": 6600},
        [0.86, 0.88, 0.92], 0.1, 0.35, note="绝缘子串")

    # ---- 8f. 传感器 ----
    add("sensor", "led", "node_fan",
        {"count": 10000, "r0": 0.40, "r1": 1.00, "z0": -0.30, "z1": 0.06, "seed": 1212},
        [0.20, 0.60, 0.95], 0.1, 0.32, emit=[0.15, 0.55, 0.95], es=1.6, note="传感器")

    # ---- 8g. 单股导线（线束内部导体）----
    add("wire_single", "strand", "node_fan",
        {"count": 50000, "r0": 0.52, "r1": 1.04, "z0": -0.32, "z1": 0.04, "seed": 8080},
        [0.30, 0.24, 0.18], 0.9, 0.36, note="单股导线")

    # ---- 9. PCB 焊点 ----
    add("solder", "solder", "pcb_pads",
        {"grid": 0.0028},
        [0.72, 0.74, 0.78], 0.35, 0.20, note="PCB 焊点")

    # ---- 10. 结构角片 / 支架 ----
    add("bracket", "bracket", "node_fan",
        {"count": 45000, "r0": 0.58, "r1": 0.99, "z0": -0.16, "z1": 0.02, "seed": 20261122},
        [0.34, 0.37, 0.43], 0.9, 0.42, note="结构角片")

    # ---- 11. 杂件（销/垫片/弹簧圈）----
    add("misc", "screw", "node_fan",
        {"count": 80000, "r0": 0.50, "r1": 1.00, "z0": -0.30, "z1": 0.05, "seed": 777},
        [0.60, 0.63, 0.68], 1.0, 0.30, note="杂项紧固件")

    # ---- 12. 指示灯 ----
    add("led", "led", "ring",
        {"rings": [(0.30, 0.86), (0.24, 0.88), (0.18, 0.90)], "pitch": 0.085},
        [0.25, 0.95, 0.45], 0.0, 0.20, emit=[0.20, 0.95, 0.40], es=2.2, note="指示灯")

    # ---- 13. 铭牌螺钉 ----
    add("screw", "screw", "node_fan",
        {"count": 8000, "r0": 0.85, "r1": 1.02, "z0": -0.10, "z1": 0.06, "seed": 4242},
        [0.70, 0.73, 0.78], 1.0, 0.24, note="铭牌螺钉")

    return fams, keep


# ============================================================
# 4. 生成实例（供 Blender 渲染 / 统计）
# ============================================================
def gen_instances(fam):
    g = fam["gen"]
    p = fam["params"]
    if g == "shell":
        return gen_shell_rivets(p["pitch"], p["k"], p["phi0"], p["phi1"], bool(p["stagger"]))
    if g == "ring":
        return gen_ring_rivets(p.get("radius_k", 1.0), p["rings"], p["pitch"])
    if g == "coil":
        return gen_coil_strands(p["turns"], p["seg"], p["radius_k"], p["z0"], p["dz"], p["turns"])
    if g == "nodes":
        out = []
        for (cx, cy, cz) in p["nodes"]:
            n = p["per_node"]
            ring = p.get("ring", 0.03)
            dz = p.get("dz", 0.0)
            for j in range(n):
                a = 2 * math.pi * j / n
                out.append((cx + ring * math.cos(a), cy + ring * math.sin(a), cz + dz,
                            0.0, 0.0, 1.0))
        return np.array(out, dtype=np.float32)
    if g == "fins":
        out = []
        for (cx, cy, cz) in p["row"]:
            n = p["per"]
            for j in range(n):
                t = (j / (n - 1.0)) - 0.5
                out.append((cx, cy + t * p["span"], cz, 0.0, 1.0, 0.0))
        return np.array(out, dtype=np.float32)
    if g == "grille":
        out = []
        for (cx, cy, cz) in p["centers"]:
            for r in range(p["rows"]):
                for c in range(p["cols"]):
                    out.append((cx + (c - p["cols"] / 2) * p["dw"],
                                cy + (r - p["rows"] / 2) * p["dd"], cz,
                                0.0, 0.0, 1.0))
        return np.array(out, dtype=np.float32)
    if g == "pcb_pads":
        # 7 块板 × 网格，位置从电气规格读会循环依赖，这里用固定布局近似
        out = []
        boards = [(-0.62, 0.52, 0.42, 0.30), (0.58, 0.50, 0.38, 0.28),
                  (0.58, 0.12, 0.18, 0.12), (-0.60, -0.10, 0.24, 0.16),
                  (-0.60, -0.46, 0.20, 0.14), (0.60, -0.20, 0.16, 0.11),
                  (0.0, -0.62, 0.12, 0.30)]
        st = p["grid"] * 3
        for (bx, by, bw, bh) in boards:
            nx = int(bw / st)
            ny = int(bh / st)
            for i in range(nx):
                for j in range(ny):
                    out.append((bx - bw / 2 + (i + 0.5) * st,
                                by - bh / 2 + (j + 0.5) * st, -0.04,
                                0.0, 0.0, 1.0))
        return np.array(out, dtype=np.float32)
    if g == "seams":
        # 面板缝两侧铆钉：环向缝 + 经向缝，各排列 rows 排
        out = []
        pitch = p["pitch"]
        rows = p["rows"]
        gap = p["gap"]
        for phi in p["phis"]:
            a = HX * math.sin(phi)
            b = HY * math.sin(phi)
            circ = ell_circ(a, b)
            n = max(8, int(circ / pitch))
            for r in range(rows):
                dphi = (r - (rows - 1) / 2.0) * (gap / 1.75)
                ph = phi + dphi
                if not (0.03 < ph < math.pi - 0.03):
                    continue
                for j in range(n):
                    th = 2 * math.pi * j / n
                    q = sph(th, ph, 0.9995)
                    nn = snorm(th, ph)
                    out.append((q[0], q[1], q[2], nn[0], nn[1], nn[2]))
        # 经向缝
        M = p["meridians"]
        Nphi = 240
        for m in range(M):
            th0 = 2 * math.pi * m / M + math.pi / M
            for i in range(Nphi):
                ph = math.radians(12) + (math.radians(168) - math.radians(12)) * i / Nphi
                for r in range(rows):
                    dth = (r - (rows - 1) / 2.0) * (gap / max(0.05, HX * math.sin(ph)))
                    th = th0 + dth
                    q = sph(th, ph, 0.9995)
                    nn = snorm(th, ph)
                    out.append((q[0], q[1], q[2], nn[0], nn[1], nn[2]))
        return np.array(out, dtype=np.float32)
    if g == "node_fan":
        # 确定性伪随机（LCG），两端一致
        out = []
        s = int(p["seed"])
        n = int(p["count"])
        for k in range(n):
            s = (16807 * s) % 2147483647
            u1 = s / 2147483647.0
            s = (16807 * s) % 2147483647
            u2 = s / 2147483647.0
            s = (16807 * s) % 2147483647
            u3 = s / 2147483647.0
            th = 2 * math.pi * u1
            rk = p["r0"] + (p["r1"] - p["r0"]) * u2
            zz = p["z0"] + (p["z1"] - p["z0"]) * u3
            lim = math.sqrt(max(0.0, 1 - (zz / HZ) ** 2))
            if rk > lim * 0.94:
                rk = lim * 0.94
            out.append((HX * rk * math.cos(th), HY * rk * math.sin(th), zz,
                        0.0, 0.0, 1.0))
        return np.array(out, dtype=np.float32)
    return np.zeros((0, 6), np.float32)


def harvest():
    """生成全部族并统计"""
    fams, geoms = build_families()
    total = 0
    rows = []
    for f in fams:
        inst = gen_instances(f)
        n = len(inst)
        total += n
        tri = len(geoms[f["geo"]]["i"]) // 3
        rows.append((f["id"], f["note"], n, tri, n * tri))
    return fams, geoms, total, rows


if __name__ == "__main__":
    fams, geoms, total, rows = harvest()
    print("%-14s %-18s %9s %5s %11s" % ("族", "说明", "数量", "单片", "三角"))
    print("-" * 66)
    tri_sum = 0
    for (fid, note, n, tri, tt) in rows:
        print("%-14s %-18s %9d %5d %11d" % (fid, note, n, tri, tt))
        tri_sum += tt
    print("-" * 66)
    print("零件总数 %d（+ 独立部件 563 = %d）" % (total, total + 563))
    print("总三角面 %d" % (tri_sum + 300119))
