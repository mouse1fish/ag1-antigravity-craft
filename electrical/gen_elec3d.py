# -*- coding: utf-8 -*-
"""
AG-1 电气 3D 几何生成器
从 ag1_elec_spec.py 生成与 ag1_model.json 同格式的电气部件：
  - 7 块 PCB（板体 + 丝印层 + 安装孔铜环）
  - 185 个器件（真实封装外形）
  - 铜排 / 散热器 / 水冷板
  - 板卡机架 / 导轨 / 支架
  - 高压线束 / 冷却管路 / 接地编织
输出: elec_parts.json  ->  由 merge 脚本并入 ag1_model.json
坐标系: Blender Z-up, 单位 m。
"""
import os, sys, json, math

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ag1_elec_spec as S

OUT = os.path.join(HERE, "elec_parts.json")

# ============================================================
# 网格构造
# ============================================================
class MB:
    __slots__ = ("v", "i")

    def __init__(self):
        self.v = []
        self.i = []

    def add(self, verts, tris):
        b = len(self.v)
        self.v.extend(verts)
        for t in tris:
            self.i.append((t[0] + b, t[1] + b, t[2] + b))

    # ---- 长方体（中心 + 尺寸），法线朝外 ----
    def box(self, cx, cy, cz, w, d, h):
        x0, x1 = cx - w / 2, cx + w / 2
        y0, y1 = cy - d / 2, cy + d / 2
        z0, z1 = cz - h / 2, cz + h / 2
        vs = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
              (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        ts = [(0, 3, 2), (0, 2, 1),   # bottom
              (4, 5, 6), (4, 6, 7),   # top
              (0, 1, 5), (0, 5, 4),   # front
              (2, 3, 7), (2, 7, 6),   # back
              (1, 2, 6), (1, 6, 5),   # right
              (3, 0, 4), (3, 4, 7)]   # left
        self.add(vs, ts)

    def box_minmax(self, x0, y0, z0, x1, y1, z1):
        self.box((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2,
                 abs(x1 - x0), abs(y1 - y0), abs(z1 - z0))

    # ---- 圆柱（沿 Z）----
    def cyl(self, cx, cy, z0, z1, r, seg=16, cap=True):
        vs = []
        for k in range(seg):
            a = 2 * math.pi * k / seg
            vs.append((cx + r * math.cos(a), cy + r * math.sin(a), z0))
        for k in range(seg):
            a = 2 * math.pi * k / seg
            vs.append((cx + r * math.cos(a), cy + r * math.sin(a), z1))
        ts = []
        for k in range(seg):
            k2 = (k + 1) % seg
            ts.append((k, k2, seg + k2))
            ts.append((k, seg + k2, seg + k))
        if cap:
            cb = len(vs)
            vs.append((cx, cy, z0))
            ct = len(vs)
            vs.append((cx, cy, z1))
            for k in range(seg):
                k2 = (k + 1) % seg
                ts.append((cb, k2, k))
                ts.append((ct, seg + k, seg + k2))
        self.add(vs, ts)

    # ---- 圆环（沿 Z，环形实体）----
    def torus(self, cx, cy, cz, od, idr, h, seg=20, seg2=8):
        ro, ri = od / 2, idr / 2
        vs = []
        for k in range(seg):
            a = 2 * math.pi * k / seg
            ca, sa = math.cos(a), math.sin(a)
            for j in range(seg2):
                b = 2 * math.pi * j / seg2
                rr = ri + (ro - ri) * (0.5 + 0.5 * math.cos(b))
                zz = cz + (h / 2) * math.sin(b)
                vs.append((cx + rr * ca, cy + rr * sa, zz))
        ts = []
        for k in range(seg):
            k2 = (k + 1) % seg
            for j in range(seg2):
                j2 = (j + 1) % seg2
                a0 = k * seg2 + j
                a1 = k * seg2 + j2
                b0 = k2 * seg2 + j
                b1 = k2 * seg2 + j2
                ts.append((a0, b0, b1))
                ts.append((a0, b1, a1))
        self.add(vs, ts)

    # ---- 管（沿折线）----
    def tube(self, pts, r, seg=10, cap=True):
        if len(pts) < 2:
            return
        vs, ts = [], []
        rings = []
        for n, p in enumerate(pts):
            # 切线
            if n == 0:
                tg = sub(pts[1], pts[0])
            elif n == len(pts) - 1:
                tg = sub(pts[-1], pts[-2])
            else:
                tg = sub(pts[n + 1], pts[n - 1])
            tg = norm(tg)
            # 正交基
            up = (0, 0, 1) if abs(tg[2]) < 0.9 else (1, 0, 0)
            u = norm(cross(tg, up))
            w = norm(cross(tg, u))
            ring = []
            for k in range(seg):
                a = 2 * math.pi * k / seg
                off = addv(addv(scl(u, r * math.cos(a)), scl(w, r * math.sin(a))), (0, 0, 0))
                idx = len(vs)
                vs.append((p[0] + off[0], p[1] + off[1], p[2] + off[2]))
                ring.append(idx)
            rings.append(ring)
        for n in range(len(rings) - 1):
            A, B = rings[n], rings[n + 1]
            for k in range(seg):
                k2 = (k + 1) % seg
                ts.append((A[k], B[k], B[k2]))
                ts.append((A[k], B[k2], A[k2]))
        if cap:
            for ring, flip in ((rings[0], True), (rings[-1], False)):
                c = len(vs)
                p = pts[0] if flip else pts[-1]
                vs.append(p)
                for k in range(seg):
                    k2 = (k + 1) % seg
                    if flip:
                        ts.append((c, ring[k], ring[k2]))
                    else:
                        ts.append((c, ring[k2], ring[k]))
        self.add(vs, ts)

    def has(self):
        return len(self.v) > 0


def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def addv(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def scl(a, k): return (a[0] * k, a[1] * k, a[2] * k)
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def norm(a):
    L = math.sqrt(dot(a, a)) or 1.0
    return (a[0] / L, a[1] / L, a[2] / L)


# ============================================================
# 材质色
# ============================================================
CLS_COLOR = {
    "HV":    ("#22242a", 0.45, 0.38),   # 高压器件：哑黑
    "IC":    ("#14151a", 0.10, 0.52),   # 芯片：哑黑
    "PASS":  ("#b8894f", 0.08, 0.60),   # 阻容：棕黄
    "ELEC":  ("#c9d2dc", 0.35, 0.42),   # 连接器：浅灰
    "BUS":   ("#b05a20", 1.00, 0.24),   # 铜排：紫铜
    "COOL":  ("#9aa4ae", 0.98, 0.28),   # 铝：金属
}
# 特殊器件外观覆盖（按封装名）
PKG_COLOR = {
    "rad_d35x50":  ("#8e99a4", 0.90, 0.32),   # 电解：铝壳
    "rad_d18x40":  ("#8e99a4", 0.90, 0.32),
    "rad_d10x20":  ("#8e99a4", 0.90, 0.32),
    "rad_d8x12":   ("#8e99a4", 0.90, 0.32),
    "snap_d30x45": ("#8e99a4", 0.90, 0.32),
    "film_42x30x22": ("#2e3138", 0.20, 0.42),
    "film_34x24x15": ("#2e3138", 0.20, 0.42),
    "film_28x20x13": ("#2e3138", 0.20, 0.42),
    "econodual_62x48": ("#0f1014", 0.06, 0.62),  # 功率模块：哑光黑塑
    "sot227":      ("#0f1014", 0.06, 0.62),
    "contactor_68": ("#131418", 0.06, 0.60),
    "contactor_50": ("#131418", 0.06, 0.60),
    "relay_28":    ("#15171c", 0.06, 0.60),
    "fuse_32x90":  ("#d8dce2", 0.85, 0.26),
    "fuse_22x58":  ("#d8dce2", 0.85, 0.26),
    "precharge_res": ("#8c9099", 0.85, 0.34),
    "ee85":  ("#3a3c42", 0.35, 0.42),
    "ee55":  ("#3a3c42", 0.35, 0.42),
    "ee33":  ("#3a3c42", 0.35, 0.42),
    "toroid_60": ("#4a3a24", 0.05, 0.55),    # 环形电感：漆包线棕
    "toroid_40": ("#4a3a24", 0.05, 0.55),
    "terminal_m8": ("#b05a20", 1.0, 0.24),
    "heatsink_400": ("#aab3bd", 0.96, 0.30),
    "coldplate_380": ("#aab3bd", 0.96, 0.30),
    "busbar_3x30": ("#b05a20", 1.0, 0.24),
    "rogowski_50": ("#33363c", 0.3, 0.45),
}
PCB_COLOR = {
    "PWR": "#123a26", "INV": "#0d0f13", "DRV": "#0f2a56",
    "CTL": "#0f1014", "SNS": "#123a26", "AUX": "#123a26", "COM": "#0d0f13",
}


# ============================================================
# 变换：板局部 mm -> 世界 m
# ============================================================
class Xf:
    def __init__(self, rack):
        self.px, self.py, self.pz = rack["pos"]
        self.rot = math.radians(rack["rot_deg"])
        self.c, self.s = math.cos(self.rot), math.sin(self.rot)

    def p(self, x, y, z):
        # (x,y) 为板上 mm 坐标（原点左下），转为相对板中心
        lx, ly = (x - self.hw), (y - self.hh)
        lx *= 0.001
        ly *= 0.001
        z *= 0.001
        wx = lx * self.c - ly * self.s
        wy = lx * self.s + ly * self.c
        return (self.px + wx, self.py + wy, self.pz + z)

    def set_center(self, w, h):
        self.hw, self.hh = w / 2, h / 2


def _hex2rgb(h):
    """#rrggbb -> [r,g,b] 0..1，与主模型 JSON 格式一致"""
    if not isinstance(h, str):
        return h
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return [round(int(h[0:2], 16) / 255.0, 4),
            round(int(h[2:4], 16) / 255.0, 4),
            round(int(h[4:6], 16) / 255.0, 4)]


def emit_part(name, mb, color, metal=0.3, rough=0.5, emit=None, es=0.0,
              alpha=1.0, extra=None, group="elec"):
    if not mb.has():
        return None
    # bbox
    xs = [v[0] for v in mb.v]; ys = [v[1] for v in mb.v]; zs = [v[2] for v in mb.v]
    bb = [min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)]
    flat = []
    for t in mb.i:
        flat.extend(t)
    p = {
        "name": name,
        "v": [round(x, 5) for vv in mb.v for x in vv],
        "n": [],
        "i": flat,
        "color": _hex2rgb(color),
        "metal": metal,
        "rough": rough,
        "emit": emit,
        "es": es,
        "alpha": alpha,
        "bbox": [round(x, 4) for x in bb],
        "mech": None, "pivot": None, "link": None, "knee": None,
        "tq": None, "dir": None, "tele": None,
        "grp": group,
    }
    if extra:
        p.update(extra)
    return p


# ============================================================
# 器件 3D
# ============================================================
def build_component(mb, xf, part):
    ref, pkg, val, x, y, rot, hx, cls = part
    pk = S.PACKAGES.get(pkg)
    if not pk:
        return
    k = pk["kind"]
    base_z = 0.0   # 板面
    col, met, rgh = CLS_COLOR.get(cls, CLS_COLOR["IC"])

    def P(lx, ly, lz):
        return xf.p(x + lx, y + ly, base_z + lz)

    # 旋转（绕器件自身 Z）
    ra = math.radians(rot)
    ca, sa = math.cos(ra), math.sin(ra)

    def R(lx, ly):
        return (lx * ca - ly * sa, lx * sa + ly * ca)

    if k == "mlcc":
        w, d, h = pk["w"], pk["d"], pk["h"]
        cx, cy = x, y
        mb.box(cx, cy, 0.5, w, d, h)
        # 两端电极
        for sx in (-1, 1):
            mb.box(cx + sx * w * 0.36, cy, 0.5, w * 0.28, d * 1.02, h * 1.05)
        return ("center", w, d, h)

    if k == "cyl":
        dia, h = pk["dia"], pk["h"]
        mb.cyl(0, 0, 0, h, dia / 2, 20)
        # 顶部铝壳标记
        mb.cyl(0, 0, h, h + h * 0.06, dia * 0.42, 18)
        return ("cyl", dia, dia, h)

    if k == "cyl_h":
        dia, L = pk["dia"], pk["len"]
        # 沿 X 卧放
        seg = 18
        vs, ts = [], []
        for kk in range(seg):
            a = 2 * math.pi * kk / seg
            for xx in (-L / 2, L / 2):
                vs.append((xx, dia / 2 * math.cos(a), dia / 2 * math.sin(a)))
        for kk in range(seg):
            k2 = (kk + 1) % seg
            ts.append((kk * 2, k2 * 2, k2 * 2 + 1))
            ts.append((kk * 2, k2 * 2 + 1, kk * 2 + 1))
        mb.add(vs, ts)
        # 两端引脚
        for sx in (-1, 1):
            mb.cyl(sx * (L / 2 + 3), 0, 0, 3.0, 1.0, 8)
        return ("cylh", L, dia, dia)

    if k in ("box", "module"):
        w, d, h = pk["w"], pk["d"], pk["h"]
        mb.box(0, 0, h / 2, w, d, h)
        # 顶部倒角台阶
        mb.box(0, 0, h + h * 0.03, w * 0.94, d * 0.94, h * 0.06)
        # 端子/引脚
        if k == "module":
            for sy in (-1, 1):
                mb.box(0, sy * (d / 2 + 1.5), 4, w * 0.7, 3.0, 8.0)
        return ("box", w, d, h)

    if k == "ee":
        w, d, h = pk["w"], pk["d"], pk["h"]
        # 骨架
        mb.box(0, 0, h / 2, w * 0.55, d * 0.55, h)
        # 两个 E 型磁芯（左右半）
        for sx in (-1, 1):
            mb.box(sx * w * 0.28, 0, h / 2, w * 0.42, d, h * 0.92)
            # 中柱
            mb.cyl(sx * w * 0.28, 0, 0, h * 1.02, d * 0.16, 12)
        # 绕组（简化：多圈凸环）
        for i in range(5):
            zz = h * (0.15 + 0.17 * i)
            mb.cyl(0, 0, zz, zz + h * 0.08, d * 0.30, 14)
        return ("ee", w, d, h * 1.05)

    if k == "toroid":
        od, idr, h = pk["od"], pk["id"], pk["h"]
        mb.torus(0, 0, h / 2, od, idr, h, 24, 8)
        # 绕组纹
        for i in range(18):
            a = 2 * math.pi * i / 18
            rr = (od + idr) / 4
            mb.box(rr * math.cos(a), rr * math.sin(a), h / 2, 2.2, 2.2, h * 1.15)
        return ("toroid", od, od, h)

    if k == "qfp":
        w, pin = pk["w"], pk["pin"]
        h = pk.get("h", 1.4)
        mb.box(0, 0, h / 2, w * 0.86, w * 0.86, h)
        # 四边引脚
        per = pin // 4
        step = w / (per + 1)
        for i in range(per):
            off = -w / 2 + step * (i + 1)
            for (dx, dy, lw, ld) in ((off, -w * 0.46, step * 0.42, 1.5),
                                     (w * 0.46, off, 1.5, step * 0.42),
                                     (-off, w * 0.46, step * 0.42, 1.5),
                                     (-w * 0.46, -off, 1.5, step * 0.42)):
                mb.box(dx, dy, h * 0.15, lw, ld, 0.35)
        return ("qfp", w, w, h)

    if k == "bga":
        w, d = pk["w"], pk["d"]
        h = pk.get("h", 1.5)
        mb.box(0, 0, h / 2 + 0.4, w, d, h)
        # 底部焊球阵列（简化 8x8）
        n = 8
        st = min(w, d) / (n + 1)
        for r in range(n):
            for c in range(n):
                mb.cyl(-w / 2 + st * (c + 1), -d / 2 + st * (r + 1), 0, 0.4, st * 0.28, 6)
        return ("bga", w, d, h)

    if k == "sot":
        w, d = pk["w"], pk["d"]
        h = pk.get("h", 2.4)
        mb.box(0, 0, h / 2, w * 0.78, d * 0.62, h)
        # 引脚
        if pkg in ("sot23",):
            for (px, py) in ((-w * 0.35, d * 0.42), (w * 0.35, d * 0.42), (0, -d * 0.42)):
                mb.box(px, py, 0.2, 0.7, 1.1, 0.4)
        else:
            n = 4 if pkg == "soic8" else 8
            pitch = 1.27
            for i in range(n):
                yy = (i - (n - 1) / 2) * pitch
                for sx in (-1, 1):
                    mb.box(sx * w * 0.52, yy, 0.25, 1.6, 0.55, 0.5)
        return ("sot", w, d, h)

    if k == "dsub":
        w, d, h = pk["w"], pk["d"], pk["h"]
        # D 形外壳
        mb.box(0, 0, h / 2, w, d, h)
        mb.box(0, -d * 0.62, h * 0.4, w * 0.66, d * 0.3, h * 0.6)
        return ("dsub", w, d, h)

    if k == "rj45":
        w, d, h = pk["w"], pk["d"], pk["h"]
        mb.box(0, 0, h / 2, w, d, h)
        # 卡口
        mb.box(0, -d * 0.48, h * 0.25, w * 0.62, d * 0.12, h * 0.5)
        return ("rj45", w, d, h)

    if k == "heatsink":
        w, d, h = pk["w"], pk["d"], pk["h"]
        fins, = (pk.get("fins", 20),)
        base = h * 0.22
        mb.box(0, 0, base / 2, w, d, base)
        fw = w / (fins * 2.1)
        for i in range(fins):
            fx = -w / 2 + (i + 0.5) * w / fins
            mb.box(fx, 0, base + (h - base) / 2, fw, d * 0.96, h - base)
        return ("heatsink", w, d, h)

    if k == "coldplate":
        w, d, h = pk["w"], pk["d"], pk["h"]
        mb.box(0, 0, h / 2, w, d, h)
        # 进出水口
        for sx in (-1, 1):
            mb.cyl(sx * w * 0.45, d * 0.42, h, h + 12, 5.0, 10)
        return ("coldplate", w, d, h)

    if k == "busbar":
        thk, wid = pk["thk"], pk["wid"]
        # 扁铜条（沿 X）
        mb.box(0, 0, thk / 2, 40.0, wid * 0.1, thk)
        return ("busbar", 40, wid * 0.1, thk)

    return ("box", 4, 4, 4)


# ============================================================
# 主流程
# ============================================================
def main():
    parts = []
    stats = {}

    for b in S.BOARDS:
        bid = b["id"]
        rack = S.RACKS[b["rack"]]
        xf = Xf(rack)
        xf.set_center(b["w"], b["h"])
        # 板体
        mb = MB()
        # 板上坐标（原点左下角，mm）
        cx, cy = b["w"] / 2, b["h"] / 2
        mb.box(cx, cy, b["t"] / 2, b["w"], b["h"], b["t"])
        # 安装孔铜环
        for (mx, my) in b["mounts"]:
            mb.cyl(mx, my, b["t"], b["t"] + 0.3, b["mount_r"] + 1.2, 12)
        _xf_mesh(mb, xf)
        p = emit_part("PCB_%s" % bid, mb, PCB_COLOR.get(bid, "#1f5c3a"),
                      0.05, 0.62, group="pcb")
        parts.append(p)

        # ---- 铜箔走线层（贴板面 +0.05 mm）----
        tr = _build_traces(b, S.PARTS.get(bid, []))
        if tr is not None:
            _xf_mesh(tr, xf)
            pt = emit_part("TRACE_%s" % bid, tr, "#b08d45", 0.90, 0.26, group="pcb")
            if pt:
                parts.append(pt)
        # ---- 丝印边框层（贴板面 +0.06 mm）----
        sk = MB()
        W2, H2 = b["w"], b["h"]
        m = 3.0
        for (x0, y0, x1, y1) in ((m, m, W2 - m, m + 0.5), (m, H2 - m - 0.5, W2 - m, H2 - m),
                                 (m, m, m + 0.5, H2 - m), (W2 - m - 0.5, m, W2 - m, H2 - m)):
            sk.box((x0 + x1) / 2, (y0 + y1) / 2, b["t"] + 0.06,
                   abs(x1 - x0), abs(y1 - y0), 0.04)
        # 板号丝印方块
        sk.box(m + 12, H2 - m - 5, b["t"] + 0.06, 20, 1.2, 0.04)
        _xf_mesh(sk, xf)
        ps = emit_part("SILK_%s" % bid, sk, "#e8eef4", 0.0, 0.55, group="pcb")
        if ps:
            parts.append(ps)

        # ---- 器件焊盘（沉金）----
        pd = _build_pads(b, S.PARTS.get(bid, []))
        if pd is not None:
            _xf_mesh(pd, xf)
            pp = emit_part("PAD_%s" % bid, pd, "#c8a24a", 1.0, 0.22, group="pcb")
            if pp:
                parts.append(pp)
        # ---- 缝合过孔阵列 ----
        vv = _build_vias(b, S.PARTS.get(bid, []))
        if vv is not None:
            _xf_mesh(vv, xf)
            pv = emit_part("VIA_%s" % bid, vv, "#b08d45", 0.95, 0.26, group="pcb")
            if pv:
                parts.append(pv)

        # 器件
        cnt = 0
        for part in S.PARTS.get(bid, []):
            ref, pkg, val, x, y, rot, hx, cls = part
            pk = S.PACKAGES.get(pkg)
            if not pk:
                continue
            # 器件必须落在板内（避免越界）
            if not (0 <= x <= b["w"] and 0 <= y <= b["h"]):
                continue
            col, met, rgh = CLS_COLOR.get(cls, CLS_COLOR["IC"])
            if pkg in PKG_COLOR:
                col, met, rgh = PKG_COLOR[pkg]
            mb2 = MB()
            # 用板局部坐标构建（器件中心放在 (x-W/2, y-H/2)）
            info = _build_comp_local(mb2, pk, pkg, rot, hx)
            if info is None:
                continue
            # 平移到器件位置（板上 mm 坐标）
            _translate(mb2, x, y, b["t"] + 0.112)
            # 变换到世界
            _xf_mesh(mb2, xf)
            nm = "E_%s_%s" % (bid, ref)
            pp = emit_part(nm, mb2, col, met, rgh, group="comp",
                           extra={"ref": ref, "val": val, "board": bid, "cls": cls})
            if pp:
                parts.append(pp)
                cnt += 1
        stats[bid] = cnt

    # 机架
    frame_parts = build_frames()
    parts.extend(frame_parts)

    # 线束
    harness_parts = build_harness()
    parts.extend(harness_parts)

    total_tri = sum(len(p["i"]) // 3 for p in parts)
    print("电气部件 %d 个，三角面 %d" % (len(parts), total_tri))
    for k, v in stats.items():
        print("  %-4s 器件 %d" % (k, v))
    print("  机架 %d, 线束 %d" % (len(frame_parts), len(harness_parts)))

    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"parts": parts}, f, ensure_ascii=False)
    print("-> %s (%.2f MB)" % (OUT, os.path.getsize(OUT) / 1048576))


def _build_traces(b, parts):
    """电源板风格铜皮走线：3 条主干 + 竖向馈线 + 器件分支"""
    if not parts:
        return None
    mb = MB()
    W, H, t = b["w"], b["h"], b["t"] + 0.05
    lines = [H * 0.18, H * 0.50, H * 0.82]
    for yy in lines:
        mb.box(W / 2, yy, t, W * 0.95, 3.2, 0.06)      # 主干铜皮条
    nv = max(3, int(W / 46))
    for i in range(nv):
        xx = W * 0.06 + i * (W * 0.88 / max(1, nv - 1))
        mb.box(xx, H / 2, t, 1.4, H * 0.95, 0.06)      # 竖向馈线
    for p in parts:
        x, y = p[3], p[4]
        ny = min(lines, key=lambda q: abs(q - y))
        if abs(y - ny) > 2.0:
            mb.box(x, (y + ny) / 2, t + 0.012, 1.0, abs(y - ny), 0.06)
    return mb


def _build_pads(b, parts):
    """器件焊盘（沉金）：按封装 pad 定义生成贴面铜片"""
    mb = MB()
    t = b["t"]
    for p in parts:
        ref, pkg, val, x, y, rot, hx, cls = p
        pk = S.PACKAGES.get(pkg)
        if not pk:
            continue
        pads = _pads_for(pkg, pk)
        for (pn, dx, dy, pw, ph, shape) in pads:
            # 焊盘沿各自方向外移，让它露出器件本体边缘
            sx = 1.45 if abs(dx) > 0.15 else 1.0
            sy = 1.45 if abs(dy) > 0.15 else 1.0
            cx, cy = x + dx * sx, y + dy * sy
            if shape in ("circle", "oval"):
                mb.cyl(cx, cy, t + 0.060, t + 0.105, max(pw, ph) * 0.5, 8)
            else:
                mb.box(cx, cy, t + 0.082, pw, ph, 0.045)
    return mb if mb.has() else None


def _build_vias(b, parts):
    """缝合过孔阵列：板边 1 排 + 内部稀疏网格，避开器件占位"""
    mb = MB()
    W, H, t = b["w"], b["h"], b["t"]
    occ = [(p[3], p[4], 7.0) for p in parts]

    def free(x, y):
        if x < 2.0 or y < 2.0 or x > W - 2.0 or y > H - 2.0:
            return False
        for (ox, oy, r) in occ:
            if abs(x - ox) < r and abs(y - oy) < r:
                return False
        return True

    def via(x, y):
        mb.cyl(x, y, t + 0.060, t + 0.100, 0.36, 8)

    # 板边单排
    m = 3.0
    step = 9.0
    x = m
    while x <= W - m:
        for yy in (m, H - m):
            if free(x, yy):
                via(x, yy)
        x += step
    y = m
    while y <= H - m:
        for xx in (m, W - m):
            if free(xx, y):
                via(xx, y)
        y += step
    # 内部网格
    g = 22.0
    x = 14.0
    while x < W - 10.0:
        y = 14.0
        while y < H - 10.0:
            if free(x, y):
                via(x, y)
            y += g
        x += g
    return mb if mb.has() else None


def _pads_for(pkg, pk):
    """与 gen_pcb.pads_for 同源：优先复用，失败则内置简化版"""
    try:
        import gen_pcb
        return gen_pcb.pads_for(pkg, pk)
    except Exception:
        k = pk["kind"]
        if k == "mlcc":
            px = pk["w"] * 0.5 - 0.25
            return [("1", -px, 0, pk["w"] * 0.5, pk["d"], "roundrect"),
                    ("2", px, 0, pk["w"] * 0.5, pk["d"], "roundrect")]
        if k == "cyl":
            d = pk["dia"]
            return [("1", -d * 0.25, 0, 1.2, 1.6, "oval"),
                    ("2", d * 0.25, 0, 1.2, 1.6, "oval")]
        if k == "cyl_h":
            L = pk["len"]
            return [("1", -L / 2, 0, 6.0, 6.0, "circle"),
                    ("2", L / 2, 0, 6.0, 6.0, "circle")]
        w = pk.get("w", 4.0)
        d = pk.get("d", 4.0)
        return [("1", -w * 0.35, -d * 0.35, 1.6, 1.6, "circle"),
                ("2", w * 0.35, -d * 0.35, 1.6, 1.6, "circle"),
                ("3", w * 0.35, d * 0.35, 1.6, 1.6, "circle"),
                ("4", -w * 0.35, d * 0.35, 1.6, 1.6, "circle")]


def _build_comp_local(mb, pk, pkg, rot, hx):
    """在器件局部坐标系构建（中心 0,0，底面 z=0），带 rot 旋转"""
    ra = math.radians(rot)
    ca, sa = math.cos(ra), math.sin(ra)
    # 用临时 MB 构建未旋转版本再旋转
    tmp = MB()
    k = pk["kind"]
    if k == "mlcc":
        w, d, h = pk["w"], pk["d"], pk["h"]
        tmp.box(0, 0, h / 2, w, d, h)
        for sx in (-1, 1):
            tmp.box(sx * w * 0.36, 0, h / 2 + 0.02, w * 0.3, d * 1.03, h * 1.06)
    elif k == "cyl":
        dia, h = pk["dia"], pk["h"]
        tmp.cyl(0, 0, 0, h, dia / 2, 20)
        tmp.cyl(0, 0, h, h * 1.05, dia * 0.4, 16)
    elif k == "cyl_h":
        dia, L = pk["dia"], pk["len"]
        seg = 18
        vs, ts = [], []
        for kk in range(seg):
            a = 2 * math.pi * kk / seg
            for xx in (-L / 2, L / 2):
                vs.append((xx, dia / 2 * math.cos(a), dia / 2 + dia / 2 * math.sin(a)))
        for kk in range(seg):
            k2 = (kk + 1) % seg
            ts.append((kk * 2, k2 * 2, k2 * 2 + 1))
            ts.append((kk * 2, k2 * 2 + 1, kk * 2 + 1))
        tmp.add(vs, ts)
    elif k in ("box", "module"):
        w, d, h = pk["w"], pk["d"], pk["h"]
        tmp.box(0, 0, h / 2, w, d, h)
        tmp.box(0, 0, h * 1.02, w * 0.95, d * 0.95, h * 0.05)
        if k == "module":
            for sy in (-1, 1):
                tmp.box(0, sy * (d / 2 + 1.5), 4, w * 0.66, 3.0, 7.0)
    elif k == "ee":
        w, d, h = pk["w"], pk["d"], pk["h"]
        tmp.box(0, 0, h / 2, w * 0.52, d * 0.52, h)
        for sx in (-1, 1):
            tmp.box(sx * w * 0.29, 0, h / 2, w * 0.42, d, h * 0.9)
        for i in range(5):
            zz = h * (0.14 + 0.17 * i)
            tmp.cyl(0, 0, zz, zz + h * 0.08, d * 0.29, 14)
    elif k == "toroid":
        od, idr, h = pk["od"], pk["id"], pk["h"]
        tmp.torus(0, 0, h / 2, od, idr, h, 24, 8)
    elif k == "qfp":
        w, pin = pk["w"], pk["pin"]
        h = pk.get("h", 1.4)
        tmp.box(0, 0, h / 2, w * 0.86, w * 0.86, h)
        per = pin // 4
        step = w / (per + 1)
        for i in range(per):
            off = -w / 2 + step * (i + 1)
            for (dx, dy, lw, ld) in ((off, -w * 0.45, step * 0.42, 1.4),
                                     (w * 0.45, off, 1.4, step * 0.42),
                                     (-off, w * 0.45, step * 0.42, 1.4),
                                     (-w * 0.45, -off, 1.4, step * 0.42)):
                tmp.box(dx, dy, 0.18, lw, ld, 0.36)
    elif k == "bga":
        w, d = pk["w"], pk["d"]
        h = pk.get("h", 1.5)
        tmp.box(0, 0, h / 2 + 0.4, w, d, h)
        n = 7
        st = min(w, d) / (n + 1)
        for r in range(n):
            for c in range(n):
                tmp.cyl(-w / 2 + st * (c + 1), -d / 2 + st * (r + 1), 0, 0.4, st * 0.3, 6)
    elif k == "sot":
        w, d = pk["w"], pk["d"]
        h = pk.get("h", 2.4)
        tmp.box(0, 0, h / 2, w * 0.78, d * 0.62, h)
        if pkg == "sot23":
            for (px, py) in ((-w * 0.35, d * 0.42), (w * 0.35, d * 0.42), (0, -d * 0.42)):
                tmp.box(px, py, 0.2, 0.7, 1.0, 0.4)
        else:
            n = 4 if pkg == "soic8" else 8
            for i in range(n):
                yy = (i - (n - 1) / 2) * 1.27
                for sx in (-1, 1):
                    tmp.box(sx * w * 0.52, yy, 0.25, 1.5, 0.55, 0.5)
    elif k in ("dsub", "rj45"):
        w, d, h = pk["w"], pk["d"], pk["h"]
        tmp.box(0, 0, h / 2, w, d, h)
        tmp.box(0, -d * 0.55, h * 0.35, w * 0.6, d * 0.2, h * 0.55)
    elif k == "heatsink":
        w, d, h = pk["w"], pk["d"], pk["h"]
        fins, = (pk.get("fins", 20),)
        base = h * 0.2
        tmp.box(0, 0, base / 2, w, d, base)
        for i in range(fins):
            fx = -w / 2 + (i + 0.5) * w / fins
            tmp.box(fx, 0, base + (h - base) / 2, w / (fins * 2.1), d * 0.96, h - base)
    elif k == "coldplate":
        w, d, h = pk["w"], pk["d"], pk["h"]
        tmp.box(0, 0, h / 2, w, d, h)
        for sx in (-1, 1):
            tmp.cyl(sx * w * 0.44, d * 0.40, h, h + 10, 4.5, 10)
    elif k == "busbar":
        thk, wid = pk["thk"], pk["wid"]
        tmp.box(0, 0, thk / 2, 45.0, 8.0, thk)
    else:
        tmp.box(0, 0, 1.0, 4, 4, 2)

    # 旋转
    if rot % 360 != 0:
        nv = []
        for (vx, vy, vz) in tmp.v:
            nv.append((vx * ca - vy * sa, vx * sa + vy * ca, vz))
        tmp.v = nv
    mb.v.extend(tmp.v)
    mb.i.extend([(a, b2, c) for (a, b2, c) in tmp.i])
    return True


def _translate(mb, dx, dy, dz):
    mb.v = [(x + dx, y + dy, z + dz) for (x, y, z) in mb.v]


def _xf_mesh(mb, xf):
    mb.v = [xf.p(x, y, z) for (x, y, z) in mb.v]


def build_frames():
    """板卡机架：4 根立柱 + 上下横梁 + 板卡导轨"""
    out = []
    for b in S.BOARDS:
        rack = S.RACKS[b["rack"]]
        xf = Xf(rack)
        xf.set_center(b["w"], b["h"])
        mb = MB()
        m = 8.0   # 边距
        W, H = b["w"] + 2 * m, b["h"] + 2 * m
        t = b["t"]
        ccx, ccy = b["w"] / 2, b["h"] / 2   # 板中心（板上 mm 坐标）
        # 四角立柱
        for sx in (-1, 1):
            for sy in (-1, 1):
                mb.box(ccx + sx * W / 2, ccy + sy * H / 2, -12, 10, 10, 30)
        # 上下导轨
        for sy in (-1, 1):
            mb.box(ccx, ccy + sy * H / 2, -2, W, 8, 6)
            mb.box(ccx, ccy + sy * H / 2, t + 2, W, 8, 6)
        # 板卡托条
        for sx in (-1, 1):
            mb.box(ccx + sx * W / 2, ccy, t / 2, 6, H, t + 4)
        _xf_mesh(mb, xf)
        p = emit_part("RACK_%s" % b["id"], mb, "#6e7b87", 0.85, 0.42, group="rack")
        if p:
            out.append(p)
    return out


def build_harness():
    """高压线束 / 冷却管 / 接地（机体坐标，按 RACKS 与线圈位置）"""
    out = []
    # 线圈环位置（与主模型一致：线圈半径 ~1.15 m，中心 z=-0.02）
    COIL_C = (0.0, 0.0, -0.02)
    COIL_R = 1.15

    def anchor(name):
        if "/" in name:
            board_id, comp = name.split("/")
            for b in S.BOARDS:
                if b["id"] == board_id:
                    rack = S.RACKS[b["rack"]]
                    xf = Xf(rack)
                    xf.set_center(b["w"], b["h"])
                    # 找器件位置
                    for p in S.PARTS.get(board_id, []):
                        if p[0] == comp:
                            return xf.p(p[3], p[4], b["t"] + 8)
                    return (rack["pos"][0], rack["pos"][1], rack["pos"][2])
        if name.startswith("COILRING"):
            ang = 1.1 if name.endswith("A") else -1.1
            return (COIL_R * math.cos(ang), COIL_R * math.sin(ang), COIL_C[2] + 0.16)
        if name.startswith("COOL"):
            return (0.0, -0.85, -0.10)
        if name.startswith("FRAME"):
            return (-0.55, -0.30, -0.42)
        return (0.0, 0.0, 0.0)

    for h in S.HARNESS:
        kind = h["kind"]
        kd = S.HARNESS_KINDS.get(kind, {"dia": 8.0, "color": "#888888"})
        a = anchor(h["from"])
        bpt = anchor(h["to"])
        r = kd["dia"] / 2 * 0.001
        # 生成带自然下垂的路径
        n = 7
        pts = []
        sag = 0.06 * math.dist(a, bpt)
        for i in range(n):
            t = i / (n - 1.0)
            x = a[0] + (bpt[0] - a[0]) * t
            y = a[1] + (bpt[1] - a[1]) * t
            z = a[2] + (bpt[2] - a[2]) * t - sag * math.sin(math.pi * t)
            pts.append((x, y, z))
        mb = MB()
        mb.tube(pts, r, 10, True)
        p = emit_part("HARN_%s" % h["id"], mb, kd["color"],
                      0.2 if kind != "ground" else 0.9,
                      0.45 if kind != "ground" else 0.3,
                      group="harness",
                      extra={"hkind": kind})
        if p:
            out.append(p)
    return out


if __name__ == "__main__":
    main()
