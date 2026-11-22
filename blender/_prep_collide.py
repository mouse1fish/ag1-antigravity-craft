# -*- coding: utf-8 -*-
"""_prep_collide.py —— 预处理模型给 Bullet 碰撞检测用
读 ag1_model.json → 分类部件 → 对起落架应用"收起姿态" → 输出二进制 ag1_collide.bin
二进制格式（小端）：
  "AG1C" | uint32 count
  per part: uint32 nameLen, name, uint32 roleLen, role,
            uint32 vcount, float32[vcount*3], uint32 icount, uint32[icount]
"""
import json, struct, math, os
ROOT = os.environ.get("AG1_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collections import Counter

HX, HY, HZ = 1.62, 1.86, 0.52
FOLD_ANG = -0.68         # 与 Blender / three.js 一致的收起翻转角
JSON = os.path.join(ROOT, "blender", "out", "ag1_model.json")
BIN = os.path.join(ROOT, "blender", "out", "ag1_collide.bin")

J = json.load(open(JSON, encoding="utf-8"))


def ell_r(a):
    ca, sa = math.cos(a), math.sin(a)
    return 1.0 / math.sqrt((ca / HX) ** 2 + (sa / HY) ** 2)


def rot(p, pt, ax, ang):
    x, y, z = p[0] - pt[0], p[1] - pt[1], p[2] - pt[2]
    a0, a1, a2 = ax
    c, s = math.cos(ang), math.sin(ang)
    dot = a0 * x + a1 * y + a2 * z
    nx = x * c + (a1 * z - a2 * y) * s + a0 * dot * (1 - c)
    ny = y * c + (a2 * x - a0 * z) * s + a1 * dot * (1 - c)
    nz = z * c + (a0 * y - a1 * x) * s + a2 * dot * (1 - c)
    return (nx + pt[0], ny + pt[1], nz + pt[2])


GEAR = {}
for i in range(3):
    a = i * 2 * math.pi / 3 + math.pi / 2
    R = ell_r(a)
    rad = (math.cos(a), math.sin(a), 0.0)
    tan = (-math.sin(a), math.cos(a), 0.0)
    H = (rad[0] * R * 0.42, rad[1] * R * 0.42, -0.30)
    GEAR[i] = (H, tan)

CABLE_PREFIX = ("bus_", "av", "ck", "feed", "cool_", "thr")


def classify(part):
    n = part["name"]
    if n.startswith("gear"):
        return "gear"
    if n.startswith("Cone"):
        return "shell"          # 起落架舱口整流罩，与舱门本就是贴合关系
    if n.startswith(("coil_turn", "coil_ins", "coil_brk")):
        return "u1"
    if n.startswith("inner_"):
        return "u2"
    if n.startswith("mast_"):
        return "u3"
    if n.startswith("nozzle"):
        return "nozzle"
    if n.startswith(CABLE_PREFIX):
        return "cable"
    bb = part["bbox"]
    if (bb[3] - bb[0]) > 2.5 or (bb[4] - bb[1]) > 2.5:
        return "shell"
    return "equip"


parts = []
for p in J["parts"]:
    role = classify(p)
    vs, idx = p["v"], p["i"]
    mech = p.get("mech") or ""
    link = p.get("link") or ""
    pts = [(vs[k], vs[k + 1], vs[k + 2]) for k in range(0, len(vs), 3)]

    if role == "gear" and link not in ("door", "cowl") and mech[:4] == "gear":
        i = int(mech[4])
        H, tan = GEAR[i]
        # 1) 先按 tele 缩回
        tele = p.get("tele") or [0, 0.0]
        dv = p.get("dir") or [0, 0, 0]
        if int(tele[0]) > 0:
            off = float(tele[1])
            pts = [(q[0] - dv[0] * off, q[1] - dv[1] * off, q[2] - dv[2] * off)
                   for q in pts]
        # 2) 再整体绕髋铰翻转
        pts = [rot(q, H, tan, FOLD_ANG) for q in pts]

    parts.append({"name": p["name"], "role": role, "pts": pts, "idx": idx})

active = {"gear", "equip", "u1", "u2", "u3", "nozzle"}
out = [x for x in parts if x["role"] in active]

with open(BIN, "wb") as f:
    f.write(b"AG1C")
    f.write(struct.pack("<I", len(out)))
    for x in out:
        nb, rb = x["name"].encode("utf-8"), x["role"].encode("utf-8")
        f.write(struct.pack("<I", len(nb))); f.write(nb)
        f.write(struct.pack("<I", len(rb))); f.write(rb)
        f.write(struct.pack("<I", len(x["pts"])))
        flat = [c for q in x["pts"] for c in q]
        f.write(struct.pack("<%df" % len(flat), *flat))
        f.write(struct.pack("<I", len(x["idx"])))
        f.write(struct.pack("<%dI" % len(x["idx"]), *x["idx"]))

print("wrote", BIN, "parts", len(out), "size_kb", round(os.path.getsize(BIN) / 1024, 1))
print(Counter(x["role"] for x in out))
