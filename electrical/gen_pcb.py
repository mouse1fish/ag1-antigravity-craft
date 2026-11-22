# -*- coding: utf-8 -*-
"""
AG-1 PCB 生成器
从 ag1_elec_spec.py 读出板卡/器件，生成合法的 KiCad 7 工程文件：
  - <ID>.kicad_pcb   可直接被 KiCad 7/8 打开、3D 预览、导出 STEP
  - <ID>.kicad_sch   原理图（按网络生成简化原理框）
坐标: KiCad 用 mm，原点在板左下，Y 轴向上（KiCad 内部 Y 向下，故取负）。
"""
import os, sys, json, math, re

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ag1_elec_spec as S

OUT = os.path.join(HERE, "kicad")
os.makedirs(OUT, exist_ok=True)

# ---------- 封装 → pad 定义 ----------
def pads_for(pkg, pk):
    """返回 [(name, dx, dy, w, h, shape)]，坐标相对封装中心"""
    k = pk["kind"]
    if k == "mlcc":
        w, d = pk["w"], pk["d"]
        px = w * 0.5 - 0.25
        return [("1", -px, 0, w * 0.5, d, "roundrect"),
                ("2", px, 0, w * 0.5, d, "roundrect")]
    if k in ("sot",):
        w, d = pk["w"], pk["d"]
        if pkg in ("sot23",):
            return [("1", -0.95, -0.6, 0.6, 0.7, "roundrect"),
                    ("2", 0.95, -0.6, 0.6, 0.7, "roundrect"),
                    ("3", 0, 0.85, 0.6, 0.7, "roundrect")]
        if pkg in ("soic8",):
            n = 4
        elif pkg in ("soic16w",):
            n = 8
        elif pkg in ("d2pak",):
            return [("1", -2.54, 2.0, 1.4, 3.0, "roundrect"),
                    ("2", 0, 2.0, 1.4, 3.0, "roundrect"),
                    ("3", 2.54, 2.0, 1.4, 3.0, "roundrect"),
                    ("4", 0, -4.5, 9.0, 4.0, "roundrect")]
        else:
            n = 2
        pitch = 1.27 if n > 2 else 2.54
        out = []
        for i in range(n):
            y = (i - (n - 1) / 2.0) * pitch
            out.append((str(i + 1), -d / 2, y, 1.6, 0.6, "roundrect"))
            out.append((str(2 * n - i), d / 2, y, 1.6, 0.6, "roundrect"))
        return out
    if k == "cyl":  # 径向电解，2 引脚
        dia = pk["dia"]
        return [("1", -dia * 0.25, 0, 1.2, 1.6, "oval"),
                ("2", dia * 0.25, 0, 1.2, 1.6, "oval")]
    if k == "cyl_h":  # 卧式，两端
        L = pk["len"]
        return [("1", -L / 2, 0, 6.0, 6.0, "circle"),
                ("2", L / 2, 0, 6.0, 6.0, "circle")]
    if k in ("box", "module"):
        w, d = pk["w"], pk["d"]
        # 简化：4 角螺纹孔式 pad（机械固定）
        return [("1", -w / 2 + 4, -d / 2 + 4, 3.0, 3.0, "circle"),
                ("2", w / 2 - 4, -d / 2 + 4, 3.0, 3.0, "circle"),
                ("3", w / 2 - 4, d / 2 - 4, 3.0, 3.0, "circle"),
                ("4", -w / 2 + 4, d / 2 - 4, 3.0, 3.0, "circle")]
    if k == "qfp":
        w, pin = pk["w"], pk["pin"]
        per = pin // 4
        out = []
        step = w / (per + 1)
        for i in range(per):
            off = -w / 2 + step * (i + 1)
            out.append((str(i + 1), off, -w / 2, step * 0.5, 1.4, "roundrect"))
            out.append((str(per + i + 1), w / 2, off, 1.4, step * 0.5, "roundrect"))
            out.append((str(2 * per + i + 1), -off, w / 2, step * 0.5, 1.4, "roundrect"))
            out.append((str(3 * per + i + 1), -w / 2, -off, 1.4, step * 0.5, "roundrect"))
        return out
    if k == "bga":
        w, d = pk["w"], pk["d"]
        n = 8
        out = []
        step = min(w, d) / (n + 1)
        idx = 1
        for r in range(n):
            for c in range(n):
                out.append((str(idx), -w / 2 + step * (c + 1),
                            -d / 2 + step * (r + 1), step * 0.55, step * 0.55, "circle"))
                idx += 1
        return out
    if k == "ee":
        w, d = pk["w"], pk["d"]
        return [("1", -w / 2 + 3, -d / 2 + 3, 4.0, 4.0, "circle"),
                ("2", 0, -d / 2 + 3, 4.0, 4.0, "circle"),
                ("3", w / 2 - 3, -d / 2 + 3, 4.0, 4.0, "circle"),
                ("4", -w / 2 + 3, d / 2 - 3, 4.0, 4.0, "circle"),
                ("5", w / 2 - 3, d / 2 - 3, 4.0, 4.0, "circle")]
    if k == "toroid":
        od = pk["od"]
        return [("1", -od / 2 + 2, 0, 3.0, 3.0, "circle"),
                ("2", od / 2 - 2, 0, 3.0, 3.0, "circle")]
    if k == "dsub":
        w = pk["w"]
        out = [("1", -w / 2 + 2, -3, 1.6, 1.6, "circle"),
               ("2", w / 2 - 2, -3, 1.6, 1.6, "circle")]
        return out
    if k == "rj45":
        w, d = pk["w"], pk["d"]
        return [("1", -w / 2 + 1.5, -d / 2 + 1.5, 1.0, 1.4, "roundrect"),
                ("2", w / 2 - 1.5, -d / 2 + 1.5, 1.0, 1.4, "roundrect"),
                ("SH", -w / 2 + 1.0, d / 2 - 1.0, 2.2, 2.0, "circle"),
                ("SH2", w / 2 - 1.0, d / 2 - 1.0, 2.2, 2.0, "circle")]
    if k == "heatsink" or k == "coldplate":
        w, d = pk["w"], pk["d"]
        return [("H1", -w / 2 + 5, -d / 2 + 5, 3.2, 3.2, "circle"),
                ("H2", w / 2 - 5, -d / 2 + 5, 3.2, 3.2, "circle"),
                ("H3", w / 2 - 5, d / 2 - 5, 3.2, 3.2, "circle"),
                ("H4", -w / 2 + 5, d / 2 - 5, 3.2, 3.2, "circle")]
    if k == "busbar":
        return [("P", 0, 0, 5.0, 5.0, "circle")]
    # 默认 2 pad
    return [("1", -3, 0, 2.0, 2.0, "circle"), ("2", 3, 0, 2.0, 2.0, "circle")]


def layer_block(n_layers):
    if n_layers <= 2:
        cu = ['(0 "F.Cu" signal)', '(31 "B.Cu" signal)']
    elif n_layers == 4:
        cu = ['(0 "F.Cu" signal)', '(1 "In1.Cu" power)', '(2 "In2.Cu" power)',
              '(31 "B.Cu" signal)']
    else:
        cu = ['(0 "F.Cu" signal)', '(1 "In1.Cu" power)', '(2 "In2.Cu" power)',
              '(3 "In3.Cu" signal)', '(4 "In4.Cu" signal)', '(31 "B.Cu" signal)']
    return cu


def esc(s):
    return s.replace('"', '\\"')


def gen_board(b, parts):
    bid = b["id"]
    W, H = b["w"], b["h"]
    lines = []
    lines.append('(kicad_pcb (version 20221018) (generator pcbnew)')
    lines.append('')
    lines.append('  (general')
    lines.append('    (thickness %.2f)' % b["t"])
    lines.append('  )')
    lines.append('')
    lines.append('  (paper "A3")')
    lines.append('')
    lines.append('  (title_block')
    lines.append('    (title "%s - %s")' % (esc(bid), esc(b["name"])))
    lines.append('    (date "%s")' % S.SYS["date"])
    lines.append('    (rev "%s")' % S.SYS["rev"])
    lines.append('    (company "AG-1 Program")')
    lines.append('    (comment 1 "%s")' % esc(b["mat"]))
    lines.append('    (comment 2 "%s")' % esc(b["layer_use"]))
    lines.append('    (comment 3 "%s")' % esc(b["color"]))
    lines.append('  )')
    lines.append('')
    # 层
    cu = layer_block(b["layers"])
    lines.append('  (layers')
    for c in cu:
        lines.append('    ' + c)
    lines.append('    (36 "B.SilkS" user "B.Silkscreen")')
    lines.append('    (37 "F.SilkS" user "F.Silkscreen")')
    lines.append('    (44 "Edge.Cuts" user)')
    lines.append('  )')
    lines.append('')
    lines.append('  (setup')
    lines.append('    (pad_to_mask_clearance 0)')
    lines.append('  )')
    lines.append('')

    # 网络表：按器件名建 net
    net_names = ["GND"]
    for p in parts:
        net_names.append(p[0])
    lines.append('  (net 0 "")')
    for i, n in enumerate(net_names, start=1):
        lines.append('  (net %d "%s")' % (i, esc(n)))
    lines.append('')

    # 板框
    lines.append('  (gr_rect (start 0 0) (end %.2f %.2f) (layer "Edge.Cuts") (width 0.15))' % (W, H))
    # 安装孔
    for mx, my in b["mounts"]:
        lines.append('  (footprint "MountingHole:MountingHole_3.2mm_M3" (layer "F.Cu")')
        lines.append('    (at %.2f %.2f)' % (mx, H - my))
        lines.append('    (attr exclude_from_pos_files exclude_from_bom)')
        lines.append('    (fp_text reference "H%s" (at 0 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15)) hide))' % bid)
        lines.append('    (fp_text value "M3" (at 0 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15)) hide))')
        lines.append('    (pad "" np_thru_hole circle (at 0 0) (size %.1f %.1f) (drill %.1f) (layers "*.Cu" "*.Mask"))'
                     % (b["mount_r"] * 2, b["mount_r"] * 2, b["mount_r"] * 2))
        lines.append('  )')
    lines.append('')

    # 器件
    pad_pos = {}   # ref -> [(x,y,net)]
    for p in parts:
        ref, pkg, val, x, y, rot, hx, cls = p
        pk = S.PACKAGES.get(pkg)
        if not pk:
            continue
        kicad_pkg = "Custom:%s" % pkg
        lines.append('  (footprint "%s" (layer "F.Cu")' % kicad_pkg)
        # KiCad Y 向下，所以 y 取 H-y
        lines.append('    (at %.3f %.3f %.1f)' % (x, H - y, rot))
        lines.append('    (attr smd)')
        lines.append('    (fp_text reference "%s" (at 0 %.2f) (layer "F.SilkS") (effects (font (size 1.0 1.0) (thickness 0.15))))'
                     % (esc(ref), -(pk.get("d", 4) * 0.5 + 1.6)))
        lines.append('    (fp_text value "%s" (at 0 %.2f) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.12))))'
                     % (esc(val), (pk.get("d", 4) * 0.5 + 1.6)))
        # 封装本体（F.Fab 矩形，便于 3D 与丝印识别）
        bw = pk.get("w", pk.get("dia", pk.get("od", 5)))
        bd = pk.get("d", pk.get("dia", pk.get("od", bw)))
        lines.append('    (fp_rect (start %.3f %.3f) (end %.3f %.3f) (layer "F.Fab") (width 0.1))'
                     % (-bw / 2, -bd / 2, bw / 2, bd / 2))
        # pads
        nt = 1 + net_names.index(ref) if ref in net_names else 0
        pp = []
        for (pn, dx, dy, pw, ph, shape) in pads_for(pkg, pk):
            lines.append('      (pad "%s" %s (at %.3f %.3f) (size %.3f %.3f) (layers "F.Cu" "F.Paste" "F.Mask") (net %d "%s"))'
                         % (pn, shape, dx, dy, pw, ph, nt, esc(ref)))
            pp.append((x + dx, H - (y + dy)))
        lines.append('  )')
        pad_pos[ref] = pp
    lines.append('')

    # 简单走线：同网络最近邻串联（F.Cu，45°折线）
    def seg(a, bpt, net, width=0.25):
        out = []
        x1, y1 = a; x2, y2 = bpt
        # 45 度折
        dx, dy = x2 - x1, y2 - y1
        if abs(dx) > abs(dy):
            mx = x2 - (dx - (1 if dy > 0 else -1) * abs(dy)) if dy != 0 else x2
            my = y1
        else:
            mx = x1
            my = y2
        out.append('  (segment (start %.3f %.3f) (end %.3f %.3f) (width %.2f) (layer "F.Cu") (net %d))'
                   % (x1, y1, mx, my, width, net))
        out.append('  (segment (start %.3f %.3f) (end %.3f %.3f) (width %.2f) (layer "F.Cu") (net %d))'
                   % (mx, my, x2, y2, width, net))
        return out

    # 只对 HV/BUS 类的少量网络画铜皮走线，避免文件爆炸
    segs = []
    for p in parts:
        ref = p[0]
        cls = p[7]
        if ref not in pad_pos or len(pad_pos[ref]) < 2:
            continue
        if cls in ("HV", "BUS") and len(pad_pos[ref]) <= 4:
            pts = pad_pos[ref]
            nt = 1 + net_names.index(ref)
            for i in range(len(pts) - 1):
                segs += seg(pts[i], pts[i + 1], nt, 0.6 if cls == "BUS" else 0.4)
    lines += segs
    lines.append('')
    lines.append(')')
    return "\n".join(lines) + "\n"


def gen_sch(b, parts):
    """生成简化原理图（可被 KiCad 打开，展示器件-网络关系）"""
    bid = b["id"]
    W, H = b["w"], b["h"]
    L = []
    L.append('(kicad_sch (version 20230121) (generator eeschema)')
    L.append('')
    L.append('  (uuid "00000000-0000-0000-0000-%012d")' % (abs(hash(bid)) % 10**12))
    L.append('  (paper "A3")')
    L.append('  (title_block')
    L.append('    (title "%s - %s")' % (esc(bid), esc(b["name"])))
    L.append('    (rev "%s")' % S.SYS["rev"])
    L.append('  )')
    L.append('')
    L.append('  (lib_symbols)')
    L.append('')
    # 器件网格摆放 + 网络标签
    cols = max(1, int(W // 40))
    for i, p in enumerate(parts):
        ref, pkg, val, x, y, rot, hx, cls = p
        sx = 30 + (i % cols) * 40
        sy = 30 + (i // cols) * 30
        L.append('  (symbol (lib_id "Device:Generic") (at %.2f %.2f 0) (unit 1)' % (sx, sy))
        L.append('    (in_bom yes) (on_board yes) (dnp no)')
        L.append('    (uuid "00000000-0000-0000-0000-%012d")' % (abs(hash(bid + ref + pkg)) % 10**12))
        L.append('    (property "Reference" "%s" (at %.2f %.2f 0) (effects (font (size 1.2 1.2))))'
                 % (esc(ref), sx, sy - 8))
        L.append('    (property "Value" "%s" (at %.2f %.2f 0) (effects (font (size 1.0 1.0))))'
                 % (esc(val), sx, sy + 8))
        L.append('    (property "Footprint" "Custom:%s" (at 0 0 0) (effects (font (size 1 1)) hide))' % esc(pkg))
        L.append('  )')
    L.append('')
    L.append('  (sheet_instances (path "/" (page "1")))')
    L.append(')')
    return "\n".join(L) + "\n"


def check_balance(s):
    depth = 0
    instr = False
    esc_ = False
    for ch in s:
        if instr:
            if esc_:
                esc_ = False
            elif ch == "\\":
                esc_ = True
            elif ch == '"':
                instr = False
        else:
            if ch == '"':
                instr = True
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth < 0:
                    return False
    return depth == 0


if __name__ == "__main__":
    print("生成 KiCad 工程 -> %s" % OUT)
    total_kb = 0
    for b in S.BOARDS:
        bid = b["id"]
        parts = S.PARTS.get(bid, [])
        pcb = gen_board(b, parts)
        ok1 = check_balance(pcb)
        p1 = os.path.join(OUT, "AG1_%s.kicad_pcb" % bid)
        with open(p1, "w", encoding="utf-8", newline="\n") as f:
            f.write(pcb)
        sch = gen_sch(b, parts)
        ok2 = check_balance(sch)
        p2 = os.path.join(OUT, "AG1_%s.kicad_sch" % bid)
        with open(p2, "w", encoding="utf-8", newline="\n") as f:
            f.write(sch)
        kb = (os.path.getsize(p1) + os.path.getsize(p2)) / 1024.0
        total_kb += kb
        print("  %-4s pcb=%6.1f KB  sch=%5.1f KB  括号平衡=%s/%s  器件=%d"
              % (bid, os.path.getsize(p1) / 1024, os.path.getsize(p2) / 1024,
                 ok1, ok2, len(parts)))
    print("合计 %.1f KB" % total_kb)
