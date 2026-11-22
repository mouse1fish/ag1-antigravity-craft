# -*- coding: utf-8 -*-
"""
massmesh.py —— 在 Blender 里把百万零件族构建成网格
==================================================
每个族合并成一个 mesh（用 numpy 批量算顶点，foreach_set 灌进 Blender），
避免创建上百万个 object 把 Blender 撑死。

密度由 MASS_DENSITY 控制：屏幕上铆钉只有 1~2 像素，没必要全画。
"""
import os
import sys
import math
import numpy as np
import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import massparts as MP


def _skew(a):
    N = a.shape[0]
    K = np.zeros((N, 3, 3), dtype=np.float32)
    K[:, 0, 1] = -a[:, 2]
    K[:, 0, 2] = a[:, 1]
    K[:, 1, 0] = a[:, 2]
    K[:, 1, 2] = -a[:, 0]
    K[:, 2, 0] = -a[:, 1]
    K[:, 2, 1] = a[:, 0]
    return K


def _mat(name, color, metal, rough, emit, es):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*[min(1, max(0, c)) for c in color], 1)
    b.inputs["Metallic"].default_value = min(1, max(0, metal))
    b.inputs["Roughness"].default_value = min(1, max(0, rough))
    try:
        em = emit or [0, 0, 0]
        b.inputs["Emission"].default_value = (*[min(1, max(0, c)) for c in em], 1)
        b.inputs["Emission Strength"].default_value = max(0, es)
    except Exception:
        pass
    return m


def build_family(fam, geo, density=1.0, coll=None):
    """把一个族的所有实例合并成一个 mesh 对象"""
    inst = MP.gen_instances(fam)
    n_all = len(inst)
    if n_all == 0:
        return None, 0
    if density < 0.999:
        take = max(1, int(n_all * density))
        idx = np.linspace(0, n_all - 1, take).astype(np.int64)
        inst = inst[idx]

    P = inst[:, 0:3].astype(np.float32)
    Nv = inst[:, 3:6].astype(np.float32)
    ln = np.linalg.norm(Nv, axis=1)
    ln[ln < 1e-6] = 1.0
    Nv = Nv / ln[:, None]

    V = np.array(geo["v"], dtype=np.float32).reshape(-1, 3) * 0.001   # mm → m
    I = np.array(geo["i"], dtype=np.int32).reshape(-1, 3)
    nv, nt = V.shape[0], I.shape[0]
    ninst = P.shape[0]

    # 把几何的 +Z 对齐到实例法线
    z = np.zeros_like(Nv)
    z[:, 2] = 1.0
    cosd = np.clip(np.sum(Nv * z, axis=1), -1.0, 1.0)
    ax = np.cross(z, Nv)
    s = np.linalg.norm(ax, axis=1)
    small = s < 1e-6
    neg = small & (cosd < 0)
    ax[neg] = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    s[small] = 1.0
    axu = ax / s[:, None]
    theta = np.arccos(cosd)
    K = _skew(axu)
    I3 = np.eye(3, dtype=np.float32)[None, :, :]
    R = I3 + np.sin(theta)[:, None, None] * K + (1 - np.cos(theta))[:, None, None] * (K @ K)

    verts = (np.einsum("nij,vj->nvi", R, V) + P[:, None, :]).reshape(-1, 3)
    off = (np.arange(ninst, dtype=np.int32) * nv)[:, None, None]
    tris = (I[None, :, :] + off).reshape(-1, 3)

    me = bpy.data.meshes.new("mass_" + fam["id"])
    me.vertices.add(len(verts))
    me.vertices.foreach_set("co", verts.ravel())
    me.loops.add(len(tris) * 3)
    me.loops.foreach_set("vertex_index", tris.ravel())
    me.polygons.add(len(tris))
    me.polygons.foreach_set("loop_start", np.arange(0, len(tris) * 3, 3, dtype=np.int32))
    me.polygons.foreach_set("loop_total", np.full(len(tris), 3, dtype=np.int32))
    me.update()
    me.validate()

    ob = bpy.data.objects.new("MASS_" + fam["id"], me)
    (coll or bpy.context.scene.collection).objects.link(ob)
    ob.data.materials.append(_mat("massm_" + fam["id"], fam["color"], fam["metal"],
                                  fam["rough"], fam.get("emit"), fam.get("es", 0.0)))
    ob["grp"] = "mass"
    ob["fam"] = fam["id"]

    del verts, tris, R, K
    return ob, n_all


def build_all(density=1.0, coll=None):
    fams, geoms = MP.build_families()
    objs = []
    total = 0
    tri = 0
    for f in fams:
        ob, n_all = build_family(f, geoms[f["geo"]], density, coll)
        total += n_all
        if ob is not None:
            objs.append(ob)
            tri += len(ob.data.polygons)
    print("MASS built: families=%d objects=%d parts=%d tris=%d density=%.2f"
          % (len(fams), len(objs), total, tri, density))
    return objs, total, tri


if __name__ == "__main__":
    d = float(os.environ.get("MASS_DENSITY", "0.3"))
    build_all(d)
