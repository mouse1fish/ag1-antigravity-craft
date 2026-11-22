# -*- coding: utf-8 -*-
"""
STEP 零件探测 / 转换工具
用 OCP (OpenCASCADE) 读取 STEP，输出:
  - 包围盒尺寸 (mm)
  - 面数 / 三角数
  - 可选导出 OBJ
用法:
  python step_probe.py                 # 探测当前目录所有 .step/.stp
  python step_probe.py <file.step> ... # 探测指定文件
  加 --obj 参数则同时导出同名 .obj
"""
import sys, os, glob, json

from OCP.STEPControl import STEPControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE
from OCP.TopoDS import TopoDS
from OCP.BRep import BRep_Tool
from OCP.TopLoc import TopLoc_Location
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.gp import gp_Pnt


def read_step(path):
    reader = STEPControl_Reader()
    status = reader.ReadFile(path)
    if status != IFSelect_RetDone:
        raise RuntimeError("ReadFile failed: %s (status=%s)" % (path, status))
    reader.TransferRoots()
    shape = reader.OneShape()
    return shape


def bbox_of(shape):
    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    lo = box.CornerMin()
    hi = box.CornerMax()
    xmin, ymin, zmin = lo.X(), lo.Y(), lo.Z()
    xmax, ymax, zmax = hi.X(), hi.Y(), hi.Z()
    return (xmax - xmin, ymax - ymin, zmax - zmin), (xmin, ymin, zmin), (xmax, ymax, zmax)


def _call(obj, names, *args):
    """兼容不同 OCP 版本的 _s 后缀命名"""
    for n in names:
        if hasattr(obj, n):
            return getattr(obj, n)(*args)
    raise AttributeError("none of %s on %r" % (names, obj))


def tessellate(shape, lin_defl=0.15, ang_defl=0.35):
    """返回 [(verts[(x,y,z)...], tris[(a,b,c)...]), ...] 按面拆分"""
    BRepMesh_IncrementalMesh(shape, lin_defl, False, ang_defl, True)
    faces = []
    ntri = 0
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        face = _call(TopoDS, ("Face", "Face_s"), exp.Current())
        loc = TopLoc_Location()
        tri = _call(BRep_Tool, ("Triangulation", "Triangulation_s"), face, loc)
        if tri is not None:
            trsf = loc.Transformation()
            verts = []
            nb = tri.NbNodes()
            for i in range(1, nb + 1):
                p = tri.Node(i).Transformed(trsf)
                verts.append((p.X(), p.Y(), p.Z()))
            tris = []
            nt = tri.NbTriangles()
            reversed_ = (face.Orientation() == 1)  # TopAbs_REVERSED == 1
            for i in range(1, nt + 1):
                a, b, c = tri.Triangle(i).Get()
                if reversed_:
                    tris.append((a - 1, c - 1, b - 1))
                else:
                    tris.append((a - 1, b - 1, c - 1))
            if verts and tris:
                faces.append((verts, tris))
                ntri += len(tris)
        exp.Next()
    return faces, ntri


def export_obj(path, faces, name):
    lines = ["# %s" % name]
    base = 1
    for verts, tris in faces:
        for v in verts:
            lines.append("v %.6f %.6f %.6f" % v)
        for a, b, c in tris:
            lines.append("f %d %d %d" % (a + base, b + base, c + base))
        base += len(verts)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    do_obj = "--obj" in sys.argv
    if not args:
        args = glob.glob("*.step") + glob.glob("*.stp") + glob.glob("*.STEP")
    out = []
    for path in args:
        if not os.path.exists(path):
            print("MISSING %s" % path)
            continue
        try:
            shape = read_step(path)
            dims, mn, mx = bbox_of(shape)
            faces, ntri = tessellate(shape)
            fcount = len(faces)
            vcount = sum(len(v) for v, _ in faces)
            rec = {
                "file": os.path.basename(path),
                "size_mm": [round(d, 2) for d in dims],
                "min": [round(v, 2) for v in mn],
                "max": [round(v, 2) for v in mx],
                "faces": fcount,
                "verts": vcount,
                "tris": ntri,
            }
            out.append(rec)
            print(json.dumps(rec, ensure_ascii=False))
            if do_obj:
                objp = os.path.splitext(path)[0] + ".obj"
                export_obj(objp, faces, os.path.basename(path))
                print("  -> wrote %s (%.1f KB)" % (objp, os.path.getsize(objp) / 1024.0))
        except Exception as e:
            print("FAIL %s : %s" % (os.path.basename(path), e))
    if len(out) > 1:
        with open("_step_probe_result.json", "w", encoding="utf-8", newline="\n") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
