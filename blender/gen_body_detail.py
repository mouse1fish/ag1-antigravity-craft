# -*- coding: utf-8 -*-
"""
AG-1 外壳表面细节生成器
在椭球壳体上生成真实感的结构细节：
  - 环向面板缝（4 条纬度圈凹槽）
  - 径向分片缝（8 条经线凹槽）
  - 检修口盖板 + 沉头螺钉
  - 传感器窗口（顶部阵列）
  - 侧面标识铭牌
  - 底部推进器整流格栅
输出: body_detail.json（与 ag1_model.json 同格式）
"""
import os, sys, json, math

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out", "body_detail.json")

HX, HY, HZ = 1.62, 1.86, 0.52
CUT_Z = 0.035     # 上半壳剖切高度（细节只加在壳体外表面）


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

    def box_between(self, p0, p1, w, h, up):
        """沿 p0->p1 生成扁长方体（用于画凹槽/棱线）"""
        d = sub(p1, p0)
        L = mag(d)
        if L < 1e-9:
            return
        dn = scl(d, 1.0 / L)
        u = cross(dn, up)
        if mag(u) < 1e-9:
            return
        u = norm(u)
        wv = scl(u, w * 0.5)
        hv = scl(norm(cross(dn, u)), h * 0.5)
        c = scl(addv(p0, p1), 0.5)
        vs = []
        for sx in (-1, 1):
            for sy in (-1, 1):
                for sz in (-1, 1):
                    off = addv(addv(scl(dn, sz * L * 0.5), scl(wv, sx)), scl(hv, sy))
                    vs.append(addv(c, off))
        # 索引次序： (sx,sy,sz) = x + 2y + 4z
        ts = [(0, 2, 3), (0, 3, 1), (4, 5, 7), (4, 7, 6),
              (0, 1, 5), (0, 5, 4), (2, 6, 7), (2, 7, 3),
              (0, 4, 6), (0, 6, 2), (1, 3, 7), (1, 7, 5)]
        self.add(vs, ts)

    def cyl(self, cx, cy, cz, r, h, seg=10):
        vs = []
        for k in range(seg):
            a = 2 * math.pi * k / seg
            vs.append((cx + r * math.cos(a), cy + r * math.sin(a), cz))
        for k in range(seg):
            a = 2 * math.pi * k / seg
            vs.append((cx + r * math.cos(a), cy + r * math.sin(a), cz + h))
        ts = []
        for k in range(seg):
            k2 = (k + 1) % seg
            ts.append((k, k2, seg + k2))
            ts.append((k, seg + k2, seg + k))
        cb = len(vs); vs.append((cx, cy, cz))
        ct = len(vs); vs.append((cx, cy, cz + h))
        for k in range(seg):
            k2 = (k + 1) % seg
            ts.append((cb, k2, k))
            ts.append((ct, seg + k, seg + k2))
        self.add(vs, ts)

    def quad(self, p, nrm, u, w_, h_):
        """在点 p 上贴一片四边形（贴面薄板），法线朝外"""
        wv = scl(u, w_ * 0.5)
        vv = scl(norm(cross(nrm, u)), h_ * 0.5)
        v0 = sub(sub(p, wv), vv)
        v1 = sub(addv(p, wv), vv)
        v2 = addv(addv(p, wv), vv)
        v3 = addv(sub(p, wv), vv)
        self.add([v0, v1, v2, v3], [(0, 1, 2), (0, 2, 3)])

    def has(self):
        return len(self.v) > 0


def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def addv(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def scl(a, k): return (a[0] * k, a[1] * k, a[2] * k)
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def mag(a): return math.sqrt(dot(a, a))
def norm(a):
    m = mag(a) or 1.0
    return (a[0] / m, a[1] / m, a[2] / m)


def surf(theta, phi, k=1.0):
    """椭球表面点（theta 方位角，phi 极角，phi=pi/2 赤道）"""
    return (HX * k * math.sin(phi) * math.cos(theta),
            HY * k * math.sin(phi) * math.sin(theta),
            HZ * k * math.cos(phi))


def snorm(theta, phi):
    """椭球面法线"""
    p = surf(theta, phi)
    n = (p[0] / (HX * HX), p[1] / (HY * HY), p[2] / (HZ * HZ))
    return norm(n)


def part(name, mb, color, metal=1.0, rough=0.4, emit=None, es=0.0, inv=False):
    if not mb.has():
        return None
    if inv:
        # 面法线朝内翻转
        mb.i = [(a, c, b) for (a, b, c) in mb.i]
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
        "grp": "detail",
    }


def main():
    parts = []

    # ---------- 1. 环向面板缝（纬度圈凹槽）----------
    mb = MB()
    for phi_d in (18, 42, 62, 78):     # 上半壳 4 圈
        phi = math.radians(phi_d)
        N = 128
        for i in range(N):
            t0 = 2 * math.pi * i / N
            t1 = 2 * math.pi * (i + 1) / N
            p0 = surf(t0, phi, 0.9975)
            p1 = surf(t1, phi, 0.9975)
            mb.box_between(p0, p1, 0.012, 0.008, snorm((t0 + t1) / 2, phi))
    p = part("shellseam_ring", mb, [0.045, 0.050, 0.062], 1.0, 0.45)
    parts.append(p)

    # ---------- 2. 径向分片缝（经线凹槽）----------
    mb = MB()
    for k in range(8):
        th = k * 2 * math.pi / 8 + math.pi / 8
        N = 40
        for i in range(N):
            f0 = math.radians(10 + 80 * i / N)
            f1 = math.radians(10 + 80 * (i + 1) / N)
            p0 = surf(th, f0, 0.9975)
            p1 = surf(th, f1, 0.9975)
            mb.box_between(p0, p1, 0.010, 0.007, (0, 0, 1))
    p = part("shellseam_radial", mb, [0.045, 0.050, 0.062], 1.0, 0.45)
    parts.append(p)

    # ---------- 3. 检修口盖板 + 沉头螺钉 ----------
    for k in range(6):
        th = k * 2 * math.pi / 6 + math.pi / 6
        phi = math.radians(50)
        c = surf(th, phi, 1.010)
        n = snorm(th, phi)
        up = (0, 0, 1)
        u = norm(cross(up, n))
        if mag(u) < 0.1:
            u = (1, 0, 0)
        mb = MB()
        # 盖板轮廓（略高于壳面）
        for (dw, dh) in ((0.19, 0.14),):
            mb.quad(c, n, u, dw, dh)
        p = part("panel_%d" % k, mb, [0.115, 0.125, 0.15], 1.0, 0.36)
        parts.append(p)
        # 螺钉 x4
        mb2 = MB()
        vv = norm(cross(n, u))
        for (a, b) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            sp = addv(c, addv(scl(u, a * 0.072), scl(vv, b * 0.048)))
            mb2.quad(sp, n, u, 0.020, 0.020)
        p = part("panel_screw_%d" % k, mb2, [0.62, 0.66, 0.72], 1.0, 0.22)
        parts.append(p)

    # ---------- 4. 顶部传感器窗口阵列 ----------
    mb = MB()
    for ring, (phi_d, cnt, rad) in enumerate(((10, 6, 0.028), (20, 12, 0.022), (30, 12, 0.018))):
        phi = math.radians(phi_d)
        for i in range(cnt):
            th = i * 2 * math.pi / cnt + ring * 0.26
            c = surf(th, phi, 1.004)
            n = snorm(th, phi)
            u = norm(cross((0, 0, 1), n)) if abs(n[2]) < 0.99 else (1, 0, 0)
            mb.quad(c, n, norm(u), rad * 2, rad * 2)
    p = part("sensor_window", mb, [0.10, 0.55, 0.75], 0.2, 0.12,
             emit=[0.16, 0.72, 0.95], es=3.0)
    parts.append(p)

    # ---------- 5. 侧面标识铭牌 ----------
    for k in range(3):
        th = k * 2 * math.pi / 3 + math.pi / 2
        phi = math.radians(64)
        c = surf(th, phi, 1.006)
        n = snorm(th, phi)
        u = norm(cross((0, 0, 1), n))
        mb = MB()
        mb.quad(c, n, u, 0.20, 0.062)
        p = part("nameplate_%d" % k, mb, [0.72, 0.74, 0.78], 0.9, 0.28)
        parts.append(p)

    # ---------- 6. 底部推进整流格栅（赤道下方 6 组）----------
    for k in range(6):
        th = k * 2 * math.pi / 6
        phi = math.radians(112)
        c = surf(th, phi, 0.998)
        n = snorm(th, phi)
        u = norm(cross((0, 0, 1), n))
        vv = norm(cross(n, u))
        mb = MB()
        for j in range(7):
            d = (j - 3) * 0.045
            sp = addv(c, scl(vv, d))
            mb.quad(sp, n, u, 0.26, 0.020)
        p = part("grille_%d" % k, mb, [0.06, 0.065, 0.078], 0.6, 0.5)
        parts.append(p)

    parts = [p for p in parts if p]
    tri = sum(len(p["i"]) // 3 for p in parts)
    print("外壳细节部件 %d 个，三角 %d" % (len(parts), tri))
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"parts": parts}, f, ensure_ascii=False)
    print("-> %s (%.1f KB)" % (OUT, os.path.getsize(OUT) / 1024))


if __name__ == "__main__":
    main()
