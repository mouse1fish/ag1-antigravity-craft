# -*- coding: utf-8 -*-
"""
AG-1 内部细节生成器（第二轮：让剖视有真东西可看）
=================================================
补齐电气/机械链路里"模型上缺失但工程上必须有"的实体：

  1. XFMR-01  高压升压变压器（1:25，油浸罐 Φ280×320）
  2. HVPS-01  Cockcroft-Walton 倍压罐（Φ180×420，6 级绝缘堆）
  3. 桁架斜撑 ×16（中央承载筒 → 主环梁）
  4. 冷却分/集水器（进回环管 + 14 根支管 + 快插接头）
  5. 环梁节点 M16 螺栓阵列（真实螺栓几何）
  6. 设备舱隔墙 ×4
  7. 线缆桥架（沿环梁的弧形走线槽）
  8. 设备铭牌 / 警示标识 ×10

输出: internal_detail.json
"""
import os, sys, json, math

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out", "internal_detail.json")

HX, HY, HZ = 1.62, 1.86, 0.52


# ---------------------------------------------------------------- 向量工具
def add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def mul(a, k): return (a[0] * k, a[1] * k, a[2] * k)
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def crossv(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def mag(a): return math.sqrt(dot(a, a))
def unit(a):
    m = mag(a) or 1.0
    return (a[0] / m, a[1] / m, a[2] / m)


class MB:
    __slots__ = ("v", "i")

    def __init__(self):
        self.v = []
        self.i = []

    def add(self, vs, ts):
        b = len(self.v)
        self.v.extend(vs)
        for t in ts:
            self.i.append((t[0] + b, t[1] + b, t[2] + b))

    # ---- 沿任意轴的圆柱（含端盖）----
    def cyl(self, c0, c1, r, seg=16, cap=True, r1=None):
        a = sub(c1, c0)
        L = mag(a)
        if L < 1e-9:
            return
        ax = unit(a)
        up = (0, 0, 1) if abs(ax[2]) < 0.9 else (1, 0, 0)
        u = unit(crossv(ax, up))
        w = unit(crossv(ax, u))
        r1 = r if r1 is None else r1
        vs = []
        for k in range(seg):
            t = 2 * math.pi * k / seg
            d = add(mul(u, r * math.cos(t)), mul(w, r * math.sin(t)))
            vs.append(add(c0, d))
        for k in range(seg):
            t = 2 * math.pi * k / seg
            d = add(mul(u, r1 * math.cos(t)), mul(w, r1 * math.sin(t)))
            vs.append(add(c1, d))
        ts = []
        for k in range(seg):
            k2 = (k + 1) % seg
            ts.append((k, k2, seg + k2))
            ts.append((k, seg + k2, seg + k))
        if cap:
            b0 = len(vs); vs.append(c0)
            b1 = len(vs); vs.append(c1)
            for k in range(seg):
                k2 = (k + 1) % seg
                ts.append((b0, k2, k))
                ts.append((b1, seg + k, seg + k2))
        self.add(vs, ts)

    # ---- 沿任意轴的长方体（用局部基）----
    def box(self, c, ax, up_hint, w, d, h):
        """c 中心；ax 为"高 h"的方向；宽 w、深 d 在垂直于 ax 的平面内"""
        ax = unit(ax)
        up = up_hint
        if abs(dot(ax, unit(up))) > 0.97:
            up = (1, 0, 0)
        u = unit(crossv(ax, up))
        v = unit(crossv(ax, u))
        vs = []
        for sz in (-1, 1):
            for sy in (-1, 1):
                for sx in (-1, 1):
                    off = add(add(mul(u, sx * w * 0.5), mul(v, sy * d * 0.5)),
                              mul(ax, sz * h * 0.5))
                    vs.append(add(c, off))
        ts = [(0, 2, 3), (0, 3, 1), (4, 5, 7), (4, 7, 6),
              (0, 1, 5), (0, 5, 4), (2, 6, 7), (2, 7, 3),
              (0, 4, 6), (0, 6, 2), (1, 3, 7), (1, 7, 5)]
        self.add(vs, ts)

    # ---- 绕 Z 的圆弧管（用于环状集管/桥架）----
    def arc_tube(self, R, z, a0, a1, r, seg=40, rseg=8, zr=0.0):
        vs = []
        ts = []
        n = seg
        rings = []
        for k in range(n + 1):
            a = a0 + (a1 - a0) * k / n
            cxx, cyy = R * math.cos(a), R * math.sin(a)
            # 椭圆化
            tang = (-math.sin(a), math.cos(a), 0)
            rad = unit((math.cos(a), math.sin(a), 0))
            up = (0, 0, 1)
            ring = []
            for j in range(rseg):
                t = 2 * math.pi * j / rseg
                off = add(add(mul(rad, r * math.cos(t)), mul(up, r * math.sin(t))), (0, 0, 0))
                idx = len(vs)
                sc = (HX / 1.62, HY / 1.86, 1.0)
                vs.append((cxx * sc[0] + off[0], cyy * sc[1] + off[1], z + off[2]))
                ring.append(idx)
            rings.append(ring)
        for k in range(n):
            A, B = rings[k], rings[k + 1]
            for j in range(rseg):
                j2 = (j + 1) % rseg
                ts.append((A[j], B[j], B[j2]))
                ts.append((A[j], B[j2], A[j2]))
        self.add(vs, ts)

    # ---- 环形圈（沿 Z）----
    def ring(self, R, z, tube_r, seg=64, rseg=8, ry_scale=1.0):
        vs = []
        ts = []
        rings = []
        for k in range(seg):
            a = 2 * math.pi * k / seg
            cxx, cyy = R * math.cos(a), R * math.sin(a)
            rad = unit((math.cos(a), math.sin(a), 0))
            up = (0, 0, 1)
            ring = []
            for j in range(rseg):
                t = 2 * math.pi * j / rseg
                off = add(mul(rad, tube_r * math.cos(t)), mul(up, tube_r * math.sin(t)))
                idx = len(vs)
                vs.append((cxx + off[0], cyy * ry_scale + off[1], z + off[2]))
                ring.append(idx)
            rings.append(ring)
        for k in range(seg):
            A, B = rings[k], rings[(k + 1) % seg]
            for j in range(rseg):
                j2 = (j + 1) % rseg
                ts.append((A[j], B[j], B[j2]))
                ts.append((A[j], B[j2], A[j2]))
        self.add(vs, ts)

    # ---- 波纹管（带波纹的圆柱，变压器油箱）----
    def bellows(self, c0, c1, r, waves=8, amp=0.008, seg=16):
        a = sub(c1, c0)
        L = mag(a)
        ax = unit(a)
        up = (0, 0, 1) if abs(ax[2]) < 0.9 else (1, 0, 0)
        u = unit(crossv(ax, up))
        w = unit(crossv(ax, u))
        rings = []
        vs = []
        steps = waves * 4
        for k in range(steps + 1):
            t = k / steps
            rr = r + amp * math.sin(2 * math.pi * waves * t)
            c = add(c0, mul(a, t))
            ring = []
            for j in range(seg):
                ang = 2 * math.pi * j / seg
                d = add(mul(u, rr * math.cos(ang)), mul(w, rr * math.sin(ang)))
                idx = len(vs)
                vs.append(add(c, d))
                ring.append(idx)
            rings.append(ring)
        ts = []
        for k in range(steps):
            A, B = rings[k], rings[k + 1]
            for j in range(seg):
                j2 = (j + 1) % seg
                ts.append((A[j], B[j], B[j2]))
                ts.append((A[j], B[j2], A[j2]))
        self.add(vs, ts)

    def has(self):
        return len(self.v) > 0


# ---------------------------------------------------------------- 输出
def part(name, mb, color, metal=0.9, rough=0.4, emit=None, es=0.0, grp="internal"):
    if not mb.has():
        return None
    xs = [v[0] for v in mb.v]; ys = [v[1] for v in mb.v]; zs = [v[2] for v in mb.v]
    flat = []
    for t in mb.i:
        flat.extend(t)
    return {
        "name": name,
        "v": [round(c, 5) for vv in mb.v for c in vv],
        "n": [], "i": flat,
        "color": color, "metal": metal, "rough": rough,
        "emit": emit, "es": es, "alpha": 1.0,
        "bbox": [round(min(xs), 4), round(min(ys), 4), round(min(zs), 4),
                 round(max(xs), 4), round(max(ys), 4), round(max(zs), 4)],
        "mech": None, "pivot": None, "link": None, "knee": None,
        "tq": None, "dir": None, "tele": None,
        "grp": grp,
    }


def hexc(h):
    h = h.lstrip("#")
    return [round(int(h[0:2], 16) / 255.0, 4),
            round(int(h[2:4], 16) / 255.0, 4),
            round(int(h[4:6], 16) / 255.0, 4)]


def ell_r_z(z):
    """给定 z，椭球在当前高度的水平半径系数"""
    k = 1.0 - (z / HZ) ** 2
    if k <= 0:
        return 0.0, 0.0
    s = math.sqrt(k)
    return HX * s, HY * s


# ---------------------------------------------------------------- 主流程
def main():
    parts = []

    # ============ 1. XFMR-01 高压升压变压器 ============
    # 横放油浸罐：Φ0.28 × 长 0.32，位于 r=0.78, z=-0.30，切向放置
    tx, ty, tz = 0.78 * math.cos(1.9), 0.78 * math.sin(1.9), -0.30
    tdir = (-math.sin(1.9), math.cos(1.9), 0)      # 切向
    c0 = add((tx, ty, tz), mul(tdir, -0.16))
    c1 = add((tx, ty, tz), mul(tdir, 0.16))
    mb = MB()
    # 罐体（波纹散热片）
    mb.bellows(c0, c1, 0.135, waves=9, amp=0.006, seg=28)
    # 两端端盖
    mb.cyl(add(c0, mul(tdir, -0.022)), c0, 0.128, 28)
    mb.cyl(c1, add(c1, mul(tdir, 0.022)), 0.128, 28)
    # 底座脚
    for s in (-1, 1):
        mb.box(add((tx, ty, tz), mul(tdir, s * 0.11 - 0.0)) + (0,) * 0,
               (0, 0, 1), (1, 0, 0), 0.05, 0.16, 0.10)
    parts.append(part("XFMR_tank", mb, hexc("#3a3f47"), 0.85, 0.34))

    # 高压套管 ×2（顶部白色瓷套）
    mb = MB()
    for s in (-1, 1):
        base = add(add((tx, ty, tz), mul(tdir, s * 0.09)), (0, 0, 0.135))
        mb.cyl(base, add(base, (0, 0, 0.085)), 0.020, 14, r1=0.016)
        # 伞裙
        for j in range(3):
            zz = 0.018 + j * 0.022
            mb.cyl(add(base, (0, 0, zz)), add(base, (0, 0, zz + 0.006)), 0.030, 14)
    parts.append(part("XFMR_bushing", mb, hexc("#d8dce2"), 0.15, 0.32))

    # 油位计 + 铭牌
    mb = MB()
    mb.cyl(add((tx, ty, tz), (0, 0, 0.15)), add((tx, ty, tz), (0, 0, 0.19)), 0.014, 10)
    parts.append(part("XFMR_gauge", mb, hexc("#c8d2dc"), 0.2, 0.15,
                      emit=[0.35, 0.85, 0.45], es=1.4))

    # ============ 2. HVPS-01 CW 倍压罐 ============
    # 横放：Φ0.18 × 长 0.42，r=0.55, z=-0.36
    hx_, hy_, hz_ = 0.55 * math.cos(-0.9), 0.55 * math.sin(-0.9), -0.36
    hdir = (-math.sin(-0.9), math.cos(-0.9), 0)
    q0 = add((hx_, hy_, hz_), mul(hdir, -0.21))
    q1 = add((hx_, hy_, hz_), mul(hdir, 0.21))
    mb = MB()
    mb.cyl(q0, q1, 0.090, 24)
    for s in (-1, 1):
        end = add((hx_, hy_, hz_), mul(hdir, s * 0.21))
        mb.cyl(add(end, mul(hdir, -s * 0.012)), add(end, mul(hdir, s * 0.030)),
               0.080, 20, r1=0.050)
    parts.append(part("HVPS_tank", mb, hexc("#2a2f36"), 0.80, 0.38))

    # 6 级绝缘堆（罐顶一排瓷瓶）
    mb = MB()
    for i in range(6):
        base = add(add((hx_, hy_, hz_), mul(hdir, (i - 2.5) * 0.062)), (0, 0, 0.090))
        mb.cyl(base, add(base, (0, 0, 0.052)), 0.017, 12, r1=0.012)
        for j in range(2):
            zz = 0.012 + j * 0.016
            mb.cyl(add(base, (0, 0, zz)), add(base, (0, 0, zz + 0.005)), 0.024, 12)
    parts.append(part("HVPS_stack", mb, hexc("#e2e8ee"), 0.10, 0.30))

    # 高压输出套管（粗）
    mb = MB()
    bo = add(add((hx_, hy_, hz_), mul(hdir, 0.21)), (0, 0, 0.05))
    mb.cyl(bo, add(bo, mul(hdir, 0.10)), 0.026, 16, r1=0.020)
    parts.append(part("HVPS_out", mb, hexc("#f0f4f8"), 0.12, 0.28,
                      emit=[0.55, 0.75, 1.0], es=0.5))

    # ============ 3. 桁架斜撑 ×16 ============
    mb = MB()
    n_rib = 16
    for i in range(n_rib):
        a = 2 * math.pi * i / n_rib + math.pi / n_rib
        # 内端：中央承载筒外壁上方
        r_in = 0.57
        p_in = (r_in * math.cos(a), r_in * math.sin(a), -0.02)
        # 外端：主环梁内侧下方
        r_out = 0.940
        p_out = (HX * r_out * math.cos(a), HY * r_out * math.sin(a), -0.115)
        d = sub(p_out, p_in)
        L = mag(d)
        mid = mul(add(p_in, p_out), 0.5)
        mb.cyl(p_in, p_out, 0.013, 8)
        # 节点加强块
        mb.box(p_in, d, (0, 0, 1), 0.045, 0.045, 0.05)
        mb.box(p_out, d, (0, 0, 1), 0.045, 0.045, 0.05)
    parts.append(part("TRUSS_diag", mb, hexc("#2a3038"), 0.90, 0.38))

    # ============ 4. 冷却分/集水器 ============
    # 进液环管（R=0.72 系数，z=-0.20）+ 回液环管（z=-0.24）
    for ring_z, col, nm in ((-0.20, "#2980b9", "COOL_supply"),
                            (-0.245, "#c0392b", "COOL_return")):
        mb = MB()
        mb.ring(0.86, ring_z, 0.016, seg=72, rseg=8, ry_scale=1.148)
        # 14 根支管（沿径向短接）
        for i in range(14):
            a = 2 * math.pi * i / 14 + 0.1
            R0 = 0.72
            p0 = (HX * R0 * math.cos(a), HY * R0 * math.sin(a), ring_z)
            p1 = (HX * 0.86 * math.cos(a), HY * 0.86 * math.sin(a), ring_z)
            mb.cyl(p0, p1, 0.0075, 8)
            # 快插接头
            mb.cyl(add(p0, mul(unit(sub(p1, p0)), -0.012)),
                   add(p0, mul(unit(sub(p1, p0)), 0.014)), 0.014, 10)
        parts.append(part(nm, mb, hexc(col), 0.25, 0.42))

    # ============ 5. 环梁节点 M16 螺栓阵列 ============
    # 在 8 个径向肋与环梁交接处，各 3 颗
    mb = MB()
    for i in range(8):
        a = 2 * math.pi * i / 8
        cx = HX * 0.965 * math.cos(a)
        cy = HY * 0.965 * math.sin(a)
        tang = (-math.sin(a), math.cos(a), 0)
        rad = (math.cos(a), math.sin(a), 0)
        for j in (-1, 0, 1):
            base = add((cx, cy, -0.055), mul(tang, j * 0.055))
            mb.cyl(base, add(base, (0, 0, 0.020)), 0.024, 6)        # 六角头
            mb.cyl(add(base, (0, 0, -0.030)), base, 0.011, 10)      # 螺杆
            mb.cyl(add(base, (0, 0, 0.020)), add(base, (0, 0, 0.030)), 0.013, 10)  # 垫圈
    parts.append(part("BOLT_ring", mb, hexc("#9aa3ad"), 1.0, 0.28))

    # ============ 6. 设备舱隔墙 ============
    for i, a in enumerate((1.15, 2.85, 4.6, 5.9)):
        mb = MB()
        r0, r1 = 0.60, 0.96
        zt, zb = 0.02, -0.15
        p0 = (HX * r0 * math.cos(a), HY * r0 * math.sin(a), (zt + zb) / 2)
        p1 = (HX * r1 * math.cos(a), HY * r1 * math.sin(a), (zt + zb) / 2)
        L = mag(sub(p1, p0))
        # box(c, ax=长度方向, up_hint, w=切向厚, d=垂向高, h=长度)
        mb.box(mul(add(p0, p1), 0.5), unit(sub(p1, p0)), (0, 0, 1),
               0.016, 0.15, L)
        parts.append(part("BULKHEAD_%d" % i, mb, hexc("#1d2128"), 0.85, 0.45))

    # ============ 7. 线缆桥架（沿环梁 4 段弧形槽）============
    for i in range(4):
        a0 = i * math.pi / 2 + 0.12
        a1 = a0 + math.pi / 2 - 0.24
        mb = MB()
        # U 型槽：底板 + 两侧壁
        N = 20
        for k in range(N + 1):
            a = a0 + (a1 - a0) * k / N
            cxx = HX * 0.896 * math.cos(a)
            cyy = HY * 0.896 * math.sin(a)
            rad = unit((math.cos(a), math.sin(a), 0))
            tang = unit((-math.sin(a), math.cos(a), 0))
            # 底
            mb.box((cxx, cyy, -0.175), (0, 0, 1), tang, 0.10, 0.014, 0.012)
            # 两侧壁
            for s in (-1, 1):
                off = mul(rad, s * 0.05)
                mb.box((cxx + off[0], cyy + off[1], -0.170), (0, 0, 1), tang,
                       0.012, 0.012, 0.030)
        parts.append(part("TRAY_%d" % i, mb, hexc("#6b7480"), 0.90, 0.36))

    # ============ 8. 设备铭牌 / 警示标识 ============
    labels = [
        ("LBL_hv", 0.62, 1.05, -0.02, "#d02020"),
        ("LBL_cw", 0.50, -1.02, -0.36, "#d0a020"),
        ("LBL_xfmr", 0.86, -0.30, -0.16, "#20c060"),
        ("LBL_cool", -0.90, 0.42, -0.22, "#2080d0"),
    ]
    for nm, lx, ly, lz, col in labels:
        mb = MB()
        mb.box((lx, ly, lz), (0, 0, 1), (1, 0, 0), 0.10, 0.005, 0.028)
        parts.append(part(nm, mb, hexc(col), 0.05, 0.55,
                          emit=hexc(col), es=0.9))

    parts = [p for p in parts if p]
    tri = sum(len(p["i"]) // 3 for p in parts)
    print("内部细节部件 %d 个，三角 %d" % (len(parts), tri))

    # ---- 壳体内校验（逐顶点，不用 bbox 角点，避免环形件误报）----
    out_cnt = 0
    for p in parts:
        v = p["v"]
        worst = 0.0
        for i in range(0, len(v), 3):
            x, y, z = v[i], v[i + 1], v[i + 2]
            q = (x / HX) ** 2 + (y / HY) ** 2 + (z / HZ) ** 2
            if q > worst:
                worst = q
        if worst > 1.0:
            out_cnt += 1
            print("  WARN %-16s ell=%.3f" % (p["name"], worst))
    print("超出壳体部件: %d" % out_cnt)

    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"parts": parts}, f, ensure_ascii=False)
    print("-> %s (%.1f KB)" % (OUT, os.path.getsize(OUT) / 1024))


if __name__ == "__main__":
    main()
