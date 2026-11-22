# -*- coding: utf-8 -*-
"""
合并电气部件到主模型，并输出 3D 布局预览
  - 读 _blender/out/ag1_model.json（机体）
  - 读 电气/elec_parts.json
  - 合并 -> _blender/out/ag1_model_full.json
  - 预览 -> images/ag1/elec_layout.png
"""
import os, json, math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

ROOT = os.environ.get("AG1_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAIN = os.path.join(ROOT, "_blender", "out", "ag1_model.json")
ELEC = os.path.join(ROOT, "反重力的真实物理模型", "电气", "elec_parts.json")
DETAIL = os.path.join(ROOT, "_blender", "out", "body_detail.json")
INTERNAL = os.path.join(ROOT, "_blender", "out", "internal_detail.json")
FULL = os.path.join(ROOT, "_blender", "out", "ag1_model_full.json")
IMG = os.path.join(ROOT, "反重力的真实物理模型", "images", "ag1", "elec_layout.png")

for fp in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"):
    if os.path.exists(fp):
        font_manager.fontManager.addfont(fp)
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=fp).get_name()
        break
plt.rcParams["axes.unicode_minus"] = False

# 壳体参数（与 build_ag1_cutaway.py 一致）
HX, HY, HZ = 1.62, 1.86, 0.52
COIL_R = 1.15


def load(p):
    with open(p, encoding="utf-8") as f:
        d = json.load(f)
    return d["parts"] if isinstance(d, dict) else d


def tri_count(p):
    return len(p.get("i", [])) // 3


def main():
    main_parts = load(MAIN)
    elec_parts = load(ELEC)
    print("机体 %d 部件 / %d 三角" %
          (len(main_parts), sum(tri_count(p) for p in main_parts)))
    print("电气 %d 部件 / %d 三角" %
          (len(elec_parts), sum(tri_count(p) for p in elec_parts)))

    # ---- 干涉检查（粗）：电气 bbox 与线圈环半径 ----
    print("\n=== 电气布局半径检查（线圈环 R=%.2f m）===" % COIL_R)
    warn = 0
    for p in elec_parts:
        bb = p.get("bbox")
        if not bb:
            continue
        rmax = 0.0
        for (x, y) in ((bb[0], bb[1]), (bb[0], bb[4]), (bb[3], bb[1]), (bb[3], bb[4])):
            rmax = max(rmax, math.hypot(x, y))
        # 壳体椭球检查
        ok = (rmax / HX) ** 2 < 1.0 if HX == HY else True
        if rmax > COIL_R - 0.02 and p["name"].startswith(("PCB_", "E_", "RACK_")):
            print("  ⚠ %-18s rmax=%.3f m  (线圈环 %.2f)" % (p["name"], rmax, COIL_R))
            warn += 1
    if warn == 0:
        print("  全部电气件在线圈环内侧 ✓")

    # 壳体内检查
    print("\n=== 壳体内检查 (椭球 %.2f x %.2f x %.2f) ===" % (HX, HY, HZ))
    out_cnt = 0
    for p in elec_parts:
        bb = p.get("bbox")
        if not bb:
            continue
        worst = 0.0
        for i in range(8):
            x = bb[0] if i & 1 else bb[3]
            y = bb[1] if i & 2 else bb[4]
            z = bb[2] if i & 4 else bb[5]
            worst = max(worst, (x / HX) ** 2 + (y / HY) ** 2 + (z / HZ) ** 2)
        if worst > 1.0:
            out_cnt += 1
            if out_cnt <= 8:
                print("  ⚠ %-18s 椭球值=%.2f" % (p["name"], worst))
    print("  超出壳体部件数: %d" % out_cnt)

    # ---- 合并 ----
    n0 = len(main_parts)
    for p in main_parts:
        if "grp" not in p or not p["grp"]:
            p["grp"] = "body"
    detail_parts = load(DETAIL) if os.path.exists(DETAIL) else []
    if detail_parts:
        print("外壳细节 %d 部件 / %d 三角" %
              (len(detail_parts), sum(tri_count(p) for p in detail_parts)))
    internal_parts = load(INTERNAL) if os.path.exists(INTERNAL) else []
    if internal_parts:
        print("内部细节 %d 部件 / %d 三角" %
              (len(internal_parts), sum(tri_count(p) for p in internal_parts)))
    allp = main_parts + detail_parts + internal_parts + elec_parts
    with open(FULL, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"parts": allp}, f, ensure_ascii=False)
    tot = sum(tri_count(p) for p in allp)
    print("\n合并 -> %s" % FULL)
    print("  部件 %d -> %d (+%d)，三角 %d，大小 %.2f MB" %
          (n0, len(allp), len(elec_parts), tot, os.path.getsize(FULL) / 1048576))

    # ---- 3D 预览 ----
    fig = plt.figure(figsize=(11, 9))
    ax = fig.add_subplot(111, projection="3d")
    # 壳体线框
    u = np.linspace(0, 2 * np.pi, 40)
    v = np.linspace(0, np.pi, 20)
    xs = HX * np.outer(np.cos(u), np.sin(v))
    ys = HY * np.outer(np.sin(u), np.sin(v))
    zs = HZ * np.outer(np.ones_like(u), np.cos(v))
    ax.plot_wireframe(xs, ys, zs, color="#b0b8c0", lw=0.35, alpha=0.35)
    # 线圈环
    th = np.linspace(0, 2 * np.pi, 120)
    ax.plot(COIL_R * np.cos(th), COIL_R * np.sin(th), np.full_like(th, -0.02),
            color="#e67e22", lw=1.2, alpha=0.8)
    # 电气 bbox 线框
    color_map = {"pcb": "#1f5c3a", "comp": "#2c3e50", "rack": "#7f8c8d", "harness": "#c0392b"}
    for p in elec_parts:
        bb = p.get("bbox")
        if not bb:
            continue
        g = p.get("grp", "comp")
        c = color_map.get(g, "#444")
        x0, y0, z0, x1, y1, z1 = bb
        # 12 条棱
        for (a, b2) in [((x0, y0, z0), (x1, y0, z0)), ((x1, y0, z0), (x1, y1, z0)),
                        ((x1, y1, z0), (x0, y1, z0)), ((x0, y1, z0), (x0, y0, z0)),
                        ((x0, y0, z1), (x1, y0, z1)), ((x1, y0, z1), (x1, y1, z1)),
                        ((x1, y1, z1), (x0, y1, z1)), ((x0, y1, z1), (x0, y0, z1)),
                        ((x0, y0, z0), (x0, y0, z1)), ((x1, y0, z0), (x1, y0, z1)),
                        ((x1, y1, z0), (x1, y1, z1)), ((x0, y1, z0), (x0, y1, z1))]:
            ax.plot([a[0], b2[0]], [a[1], b2[1]], [a[2], b2[2]], color=c, lw=0.5, alpha=0.7)

    ax.set_xlabel("X (m)"); ax.set_ylabel("Y (m)"); ax.set_zlabel("Z (m)")
    ax.set_title("AG-1 电气系统布局（俯视透视）\n绿=PCB  深蓝=器件  灰=机架  红=线束  橙=线圈环")
    try:
        ax.set_box_aspect((HX, HY, HZ))
    except Exception:
        pass
    ax.view_init(elev=28, azim=-58)
    fig.savefig(IMG, dpi=140)
    plt.close(fig)
    print("-> %s" % IMG)


if __name__ == "__main__":
    main()
