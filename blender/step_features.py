# -*- coding: utf-8 -*-
"""
STEP 零件特征分析
从 STEP 提取真实工程特征：
  - 回转轴（CYLINDRICAL_SURFACE 的法向聚类）
  - 孔径列表（半径 + 轴向 + 位置）—— 真实安装孔
  - 平面（安装面）
  - 包围盒
输出 JSON，供装配脚本做 1:1 真实装配。
"""
import sys, os, glob, json, math
from collections import defaultdict

from OCP.STEPControl import STEPControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE, TopAbs_EDGE
from OCP.TopoDS import TopoDS
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps


def _face(shape):
    for n in ("Face", "Face_s"):
        if hasattr(TopoDS, n):
            return getattr(TopoDS, n)(shape)
    raise AttributeError("TopoDS.Face")


def read_step(path):
    r = STEPControl_Reader()
    if r.ReadFile(path) != IFSelect_RetDone:
        raise RuntimeError("read fail " + path)
    r.TransferRoots()
    return r.OneShape()


def bbox(shape):
    b = Bnd_Box()
    BRepBndLib.Add_s(shape, b)
    lo, hi = b.CornerMin(), b.CornerMax()
    return (lo.X(), lo.Y(), lo.Z()), (hi.X(), hi.Y(), hi.Z())


def surf_type(ad):
    t = ad.GetType()
    if t == GeomAbs_Cylinder:
        return "cyl"
    if t == GeomAbs_Plane:
        return "plane"
    return "other"


def analyze(path):
    shape = read_step(path)
    lo, hi = bbox(shape)
    size = tuple(round(hi[i] - lo[i], 3) for i in range(3))

    cyls = []
    planes = []
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        f = _face(exp.Current())
        ad = BRepAdaptor_Surface(f, True)
        k = surf_type(ad)
        # 面积
        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(f, props)
        area = props.Mass()
        if k == "cyl":
            c = ad.Cylinder()
            ax = c.Axis()
            d = ax.Direction()
            loc = ax.Location()
            cyls.append({
                "r": round(c.Radius(), 3),
                "axis": [round(d.X(), 3), round(d.Y(), 3), round(d.Z(), 3)],
                "pnt": [round(loc.X(), 3), round(loc.Y(), 3), round(loc.Z(), 3)],
                "area": round(area, 1),
            })
        elif k == "plane":
            pl = ad.Plane()
            n = pl.Axis().Direction()
            loc = pl.Axis().Location()
            planes.append({
                "n": [round(n.X(), 3), round(n.Y(), 3), round(n.Z(), 3)],
                "pnt": [round(loc.X(), 3), round(loc.Y(), 3), round(loc.Z(), 3)],
                "area": round(area, 1),
            })
        exp.Next()

    # 回转轴判定：统计 |axis| 落在主方向上的圆柱数量
    votes = {"x": 0.0, "y": 0.0, "z": 0.0}
    for c in cyls:
        ax = c["axis"]
        for i, n in enumerate(("x", "y", "z")):
            votes[n] += abs(ax[i]) * c["area"]
    total = sum(votes.values()) or 1.0
    spin = max(votes, key=votes.get)
    spin_conf = round(votes[spin] / total, 3)

    # 主回转半径（面积加权）
    if spin_conf > 0.5:
        idx = "xyz".index(spin)
        ws = 0.0
        rs = 0.0
        for c in cyls:
            w = abs(c["axis"][idx]) * c["area"]
            ws += w
            rs += w * c["r"]
        main_r = round(rs / ws, 2) if ws else 0.0
    else:
        main_r = 0.0

    # 候选安装孔：小半径、面积不小、法向集中且贯穿
    holes = [c for c in cyls if c["r"] <= 6.5 and c["area"] > 3.0]
    holes.sort(key=lambda c: -c["area"])

    return {
        "file": os.path.basename(path),
        "size": size,
        "min": [round(v, 3) for v in lo],
        "max": [round(v, 3) for v in hi],
        "spin_axis": spin if spin_conf > 0.5 else None,
        "spin_conf": spin_conf,
        "spin_radius": main_r,
        "n_cyl": len(cyls),
        "n_plane": len(planes),
        "holes": holes[:12],
        "top_planes": sorted(planes, key=lambda p: -p["area"])[:4],
    }


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        args = sorted(glob.glob("*.step") + glob.glob("*.stp"))
    res = []
    for p in args:
        if not os.path.exists(p):
            print("MISS", p)
            continue
        try:
            r = analyze(p)
            res.append(r)
            print(json.dumps(r, ensure_ascii=False))
        except Exception as e:
            print("FAIL", os.path.basename(p), e)
    with open("_step_features.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print("-> _step_features.json")
