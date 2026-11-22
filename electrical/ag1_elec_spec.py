# -*- coding: utf-8 -*-
"""
AG-1 反重力飞行器 —— 电气系统规格（唯一事实源）
=====================================================
本文件是整个电气交付物的单一事实源：
  1. 板卡定义（尺寸 / 层叠 / 安装孔）
  2. 器件库（真实封装外形尺寸，mm）
  3. 每板器件清单与布局坐标
  4. 电气网络表
  5. 线束拓扑
  6. 电路仿真参数

下游消费者：
  - gen_pcb.py      -> .kicad_pcb 工程文件
  - gen_elec3d.py   -> Blender 3D 几何
  - gen_sim.py      -> MNA 仿真波形
  - build_ag1_*.py  -> 机体装配

所有尺寸单位 mm（1:1 真实工程尺寸）。
导出: python ag1_elec_spec.py  ->  ag1_elec_spec.json
"""

import json, os, math

# ============================================================
# 0. 系统级电气参数（真实工程取值）
# ============================================================
SYS = {
    "name": "AG-1 Electrical Power & Control System",
    "rev": "C",
    "date": "2026-11-22",
    # 功率链
    "v_bus_nom": 800.0,          # 高压直流母线 V
    "v_bus_max": 900.0,
    "v_bus_min": 640.0,
    "i_bus_max": 320.0,          # A
    "p_system_kw": 240.0,        # 全机总电功率
    "p_out_kw": 60.0,            # 谐振高压子系统额定功率（4×450A 模块）
    # 谐振逆变
    "f_sw": 85e3,                # 开关频率 Hz
    "f_res": 83.9e3,             # 谐振频率（Lr=18uH, Cr=200nF）
    "lr_uh": 17.5,
    "cr_nf": 200.0,
    "dead_time_ns": 350,
    "n_xfmr": 25.0,              # 升压变压器变比
    # 高压输出
    "v_hv_stage": 20e3,          # 变压器副边 kV
    "cw_stages": 6,              # Cockcroft-Walton 倍压级数
    "v_coil_max": 240e3,         # 线圈峰值电压（2×6×20kV）
    "c_coil_uh": 1200.0,         # 场发射线圈电感 uH
    "q_coil": 80.0,
    # 辅助电源
    "v_aux": 28.0,
    "v_logic": 12.0,
    "v_mcu": 3.3,
    # 冷却
    "coolant": "PAO-4 介电冷却液",
    "flow_lpm": 22.0,
    "t_in_max": 45.0,
    "cool_p_kw": 18.0,
    # 质量预算
    "mass_elec_kg": 168.0,
}

# ============================================================
# 1. 板卡定义
#    layers: 层数; cu_mm: 铜厚; mat: 板材; keepout: 安装孔半径
# ============================================================
BOARDS = [
    {
        "id": "PWR", "name": "高压配电板 HV Power Distribution",
        "w": 420.0, "h": 300.0, "t": 2.0, "layers": 4, "cu_mm": 0.105,
        "mat": "FR-4 Tg180", "color": "深绿阻焊 + 沉金",
        "mounts": [(10, 10), (410, 10), (10, 290), (410, 290),
                   (210, 10), (210, 290)],
        "mount_r": 3.2, "layer_use": "HV 母线层（内层 2oz 加厚）",
        "rack": "PWR_BAY",
    },
    {
        "id": "INV", "name": "谐振逆变桥 Resonant Inverter Bridge",
        "w": 380.0, "h": 280.0, "t": 2.0, "layers": 4, "cu_mm": 0.105,
        "mat": "FR-4 Tg180 + 陶瓷基板", "color": "黑色阻焊 + 沉金",
        "mounts": [(10, 10), (370, 10), (10, 270), (370, 270)],
        "mount_r": 3.2, "layer_use": "功率层（内层 3oz）",
        "rack": "INV_BAY",
    },
    {
        "id": "DRV", "name": "栅极驱动板 Gate Driver",
        "w": 180.0, "h": 120.0, "t": 1.6, "layers": 4, "cu_mm": 0.035,
        "mat": "FR-4 Tg170", "color": "蓝色阻焊",
        "mounts": [(5, 5), (175, 5), (5, 115), (175, 115)],
        "mount_r": 2.5, "layer_use": "隔离层（6kV 爬电距离）",
        "rack": "DRV_BAY",
    },
    {
        "id": "CTL", "name": "主控板 Flight Control Computer",
        "w": 240.0, "h": 160.0, "t": 1.6, "layers": 6, "cu_mm": 0.035,
        "mat": "FR-4 Tg170", "color": "哑光黑阻焊",
        "mounts": [(6, 6), (234, 6), (6, 154), (234, 154)],
        "mount_r": 2.5, "layer_use": "6 层（GND/SIG/PWR 分开）",
        "rack": "CTL_BAY",
    },
    {
        "id": "SNS", "name": "传感接口板 Sensor Interface",
        "w": 200.0, "h": 140.0, "t": 1.6, "layers": 4, "cu_mm": 0.035,
        "mat": "FR-4 Tg170", "color": "绿色阻焊",
        "mounts": [(5, 5), (195, 5), (5, 135), (195, 135)],
        "mount_r": 2.5, "layer_use": "模拟地独立层",
        "rack": "SNS_BAY",
    },
    {
        "id": "AUX", "name": "辅助电源板 Auxiliary Power Supply",
        "w": 160.0, "h": 110.0, "t": 1.6, "layers": 4, "cu_mm": 0.07,
        "mat": "FR-4 Tg170", "color": "绿色阻焊",
        "mounts": [(5, 5), (155, 5), (5, 105), (155, 105)],
        "mount_r": 2.5, "layer_use": "爬电距离 8mm",
        "rack": "AUX_BAY",
    },
    {
        "id": "COM", "name": "通信背板 Backplane",
        "w": 300.0, "h": 120.0, "t": 2.0, "layers": 6, "cu_mm": 0.07,
        "mat": "FR-4 Tg180", "color": "黑色阻焊 + ENIG",
        "mounts": [(6, 6), (294, 6), (6, 114), (294, 114)],
        "mount_r": 3.2, "layer_use": "差分对阻抗控制 100Ω",
        "rack": "COM_BAY",
    },
]

# ============================================================
# 2. 封装库 —— 真实器件外形尺寸（mm）
#    kind: 3D 几何生成用（box/cyl/cyl_h/rib/axial/bga/sot/ee/dsub/rj45/mlcc/...）
# ============================================================
PACKAGES = {
    # ---- 无源贴片 ----
    "0402":     {"kind": "mlcc", "w": 1.0,  "d": 0.5,  "h": 0.35},
    "0603":     {"kind": "mlcc", "w": 1.6,  "d": 0.8,  "h": 0.45},
    "0805":     {"kind": "mlcc", "w": 2.0,  "d": 1.25, "h": 0.7},
    "1206":     {"kind": "mlcc", "w": 3.2,  "d": 1.6,  "h": 0.8},
    "1210":     {"kind": "mlcc", "w": 3.2,  "d": 2.5,  "h": 1.1},
    "1812":     {"kind": "mlcc", "w": 4.6,  "d": 3.2,  "h": 1.6},
    "2512":     {"kind": "mlcc", "w": 6.3,  "d": 3.2,  "h": 1.8},
    # ---- 圆柱电解 ----
    "rad_d8x12":  {"kind": "cyl", "dia": 8.0,  "h": 12.0},
    "rad_d10x20": {"kind": "cyl", "dia": 10.0, "h": 20.0},
    "rad_d18x40": {"kind": "cyl", "dia": 18.0, "h": 40.0},
    "rad_d35x50": {"kind": "cyl", "dia": 35.0, "h": 50.0},   # 470uF/900V
    "snap_d30x45": {"kind": "cyl", "dia": 30.0, "h": 45.0},
    # ---- 薄膜电容 ----
    "film_42x30x22": {"kind": "box", "w": 42.0, "d": 30.0, "h": 22.0},
    "film_34x24x15": {"kind": "box", "w": 34.0, "d": 24.0, "h": 15.0},
    "film_28x20x13": {"kind": "box", "w": 28.0, "d": 20.0, "h": 13.0},
    # ---- 功率半导体模块 ----
    "econodual_62x48": {"kind": "module", "w": 62.0, "d": 48.0, "h": 30.0},
    "sot227":          {"kind": "module", "w": 40.0, "d": 25.0, "h": 12.0},
    "to247":           {"kind": "sot", "w": 16.0, "d": 5.0, "h": 20.0},
    "d2pak":           {"kind": "sot", "w": 10.2, "d": 4.4, "h": 4.5},
    "to220":           {"kind": "sot", "w": 10.1, "d": 4.6, "h": 15.5},
    # ---- 电感 / 变压器 ----
    "ee85":       {"kind": "ee", "w": 85.0, "d": 60.0, "h": 45.0, "core": 2},
    "ee55":       {"kind": "ee", "w": 55.0, "d": 40.0, "h": 30.0, "core": 2},
    "ee33":       {"kind": "ee", "w": 33.0, "d": 24.0, "h": 18.0, "core": 2},
    "toroid_60":  {"kind": "toroid", "od": 60.0, "id": 32.0, "h": 25.0},
    "toroid_40":  {"kind": "toroid", "od": 40.0, "id": 22.0, "h": 16.0},
    "smd_ind_12": {"kind": "box", "w": 12.0, "d": 12.0, "h": 8.0},
    # ---- 继电器 / 接触器 / 熔断器 ----
    "contactor_68": {"kind": "box", "w": 68.0, "d": 55.0, "h": 52.0},
    "contactor_50": {"kind": "box", "w": 50.0, "d": 45.0, "h": 40.0},
    "relay_28":     {"kind": "box", "w": 28.0, "d": 15.0, "h": 20.0},
    "fuse_32x90":   {"kind": "cyl_h", "dia": 32.0, "len": 90.0},
    "fuse_22x58":   {"kind": "cyl_h", "dia": 22.0, "len": 58.0},
    "precharge_res": {"kind": "box", "w": 60.0, "d": 30.0, "h": 25.0},
    # ---- IC ----
    "lqfp144":  {"kind": "qfp", "w": 20.0, "d": 20.0, "h": 1.4, "pin": 144},
    "lqfp64":   {"kind": "qfp", "w": 10.0, "d": 10.0, "h": 1.2, "pin": 64},
    "bga256":   {"kind": "bga", "w": 17.0, "d": 17.0, "h": 1.6},
    "bga96":    {"kind": "bga", "w": 13.5, "d": 8.0,  "h": 1.1},
    "bga153":   {"kind": "bga", "w": 11.5, "d": 13.0, "h": 1.0},
    "soic16w":  {"kind": "sot", "w": 10.3, "d": 7.5,  "h": 2.4},
    "soic8":    {"kind": "sot", "w": 4.9,  "d": 3.9,  "h": 1.6},
    "sot23":    {"kind": "sot", "w": 2.9,  "d": 1.3,  "h": 1.1},
    "qfn32":    {"kind": "qfp", "w": 5.0,  "d": 5.0,  "h": 0.9, "pin": 32},
    # ---- 连接器 ----
    "xt90":     {"kind": "box", "w": 30.0, "d": 16.0, "h": 14.0},
    "mc4":      {"kind": "cyl_h", "dia": 18.0, "len": 62.0},
    "rj45":     {"kind": "rj45", "w": 16.0, "d": 21.0, "h": 13.5},
    "usbc":     {"kind": "box", "w": 9.0, "d": 7.5, "h": 3.3},
    "db9":      {"kind": "dsub", "w": 31.0, "d": 12.5, "h": 12.0},
    "m12_4p":   {"kind": "cyl_h", "dia": 14.0, "len": 22.0},
    "gx16":     {"kind": "cyl_h", "dia": 16.0, "len": 26.0},
    "header_2x32": {"kind": "box", "w": 81.3, "d": 5.1, "h": 8.5},
    "terminal_m8": {"kind": "box", "w": 30.0, "d": 40.0, "h": 18.0},
    "molex_minifit": {"kind": "box", "w": 14.0, "d": 9.5, "h": 12.5},
    # ---- 散热 / 机械 ----
    "heatsink_400": {"kind": "heatsink", "w": 400.0, "d": 300.0, "h": 60.0, "fins": 26},
    "heatsink_200": {"kind": "heatsink", "w": 200.0, "d": 120.0, "h": 40.0, "fins": 18},
    "coldplate_380": {"kind": "coldplate", "w": 380.0, "d": 280.0, "h": 14.0},
    # ---- 铜排 ----
    "busbar_3x30": {"kind": "busbar", "thk": 3.0, "wid": 30.0},
    # ---- 传感器 ----
    "rogowski_50": {"kind": "toroid", "od": 50.0, "id": 34.0, "h": 12.0},
    "pt100_probe": {"kind": "cyl_h", "dia": 5.0, "len": 40.0},
}

# ============================================================
# 3. 器件清单（每板）
#    字段: ref, pkg, val, x, y, rot, h_extra, cls(HV/LV/IC/PASS/ELEC/COOL)
#    坐标原点 = 板左下角，x 向右，y 向上
# ============================================================
def _grid(x0, y0, cols, rows, dx, dy):
    out = []
    for r in range(rows):
        for c in range(cols):
            out.append((x0 + c * dx, y0 + r * dy))
    return out

PARTS = {}

# ---------- PWR 高压配电板 420x300 ----------
_pwr = []
_pwr.append(("F1", "fuse_32x90", "400A/1000VDC", 55, 240, 90, 0, "HV"))
_pwr.append(("K1", "contactor_68", "KILOVAC EV200 主接触器", 130, 235, 0, 0, "HV"))
_pwr.append(("K2", "contactor_68", "预充接触器", 215, 235, 0, 0, "HV"))
_pwr.append(("R1", "precharge_res", "50Ω/100W 铝壳", 300, 240, 0, 0, "HV"))
# 母线电容组 4 只
for i, (cx, cy) in enumerate(_grid(55, 150, 4, 1, 45, 0)):
    _pwr.append(("C%d" % (i + 1), "rad_d35x50", "470uF/900V", cx, cy, 0, 0, "HV"))
# 均压电阻
for i, (cx, cy) in enumerate(_grid(55, 115, 4, 1, 45, 0)):
    _pwr.append(("R%d" % (i + 10), "2512", "100k 2W", cx, cy, 0, 0, "HV"))
# 泄放
_pwr.append(("R20", "2512", "2k2 5W 泄放", 245, 115, 0, 0, "HV"))
# 共模电感
_pwr.append(("L1", "toroid_60", "共模 2x1.2mH", 320, 150, 0, 0, "HV"))
# 防反二极管
_pwr.append(("D1", "econodual_62x48", "1200V/200A 防反", 320, 70, 0, 0, "HV"))
# 母线端子
_pwr.append(("TB1", "terminal_m8", "BAT+ 输入", 390, 250, 90, 0, "HV"))
_pwr.append(("TB2", "terminal_m8", "BUS+ 输出", 390, 150, 90, 0, "HV"))
_pwr.append(("TB3", "terminal_m8", "BAT- / BUS-", 390, 50, 90, 0, "HV"))
# 电压检测
_pwr.append(("U1", "soic8", "ISO224 隔离放大", 245, 40, 0, 0, "IC"))
_pwr.append(("U2", "qfn32", "ADS8688 8ch ADC", 200, 40, 0, 0, "IC"))
# 温度
_pwr.append(("T1", "pt100_probe", "母线测温 PT100", 150, 40, 0, 0, "ELEC"))
# MLCC 阵列
for i, (cx, cy) in enumerate(_grid(60, 25, 8, 1, 9, 0)):
    _pwr.append(("C%d" % (i + 20), "1812", "10nF/1000V", cx, cy, 0, 0, "HV"))
# 铜排
_pwr.append(("BB1", "busbar_3x30", "BUS+ 铜排", 210, 195, 0, 0, "BUS"))
_pwr.append(("BB2", "busbar_3x30", "BUS- 铜排", 210, 175, 0, 0, "BUS"))
# 高压预警指示
_pwr.append(("LED1", "1206", "800V 带电指示", 20, 285, 0, 0, "ELEC"))
PARTS["PWR"] = _pwr

# ---------- INV 谐振逆变桥 380x280 ----------
_inv = []
# 全桥 4 个半桥模块（U 型布置）
_inv.append(("Q1", "econodual_62x48", "SiC 1200V/450A 高边A", 90, 200, 0, 0, "HV"))
_inv.append(("Q2", "econodual_62x48", "SiC 1200V/450A 低边A", 90, 130, 0, 0, "HV"))
_inv.append(("Q3", "econodual_62x48", "SiC 1200V/450A 高边B", 185, 200, 0, 0, "HV"))
_inv.append(("Q4", "econodual_62x48", "SiC 1200V/450A 低边B", 185, 130, 0, 0, "HV"))
# 谐振电感
_inv.append(("Lr", "ee85", "18uH 铁氧体", 295, 190, 0, 0, "HV"))
# 谐振电容 4 并联
for i, (cx, cy) in enumerate(_grid(60, 45, 4, 1, 40, 0)):
    _inv.append(("Cr%d" % (i + 1), "film_42x30x22", "50nF/3000V", cx, cy, 0, 0, "HV"))
# 隔直电容
_inv.append(("Cdc", "film_34x24x15", "2uF/1200V", 230, 45, 0, 0, "HV"))
# 电流传感器
_inv.append(("CT1", "rogowski_50", "Rogowski 500A", 320, 110, 0, 0, "ELEC"))
# 母线铜排
_inv.append(("BB1", "busbar_3x30", "BUS+ 输入", 20, 165, 90, 0, "BUS"))
_inv.append(("BB2", "busbar_3x30", "BUS- 输入", 20, 110, 90, 0, "BUS"))
_inv.append(("BB3", "busbar_3x30", "PHASE-A 输出", 140, 90, 0, 0, "BUS"))
_inv.append(("BB4", "busbar_3x30", "PHASE-B 输出", 235, 90, 0, 0, "BUS"))
# 水冷板
_inv.append(("CP1", "coldplate_380", "水冷板", 190, 92, 0, 0, "COOL"))
# 温度阵列
for i in range(4):
    _inv.append(("T%d" % (i + 1), "pt100_probe", "模块测温", 100 + i * 55, 25, 90, 0, "ELEC"))
# 缓冲吸收
for i in range(4):
    _inv.append(("Rsn%d" % (i + 1), "2512", "22Ω 缓冲", 100 + i * 55, 15, 0, 0, "HV"))
# 散热器
_inv.append(("HS1", "heatsink_400", "铝挤压散热器", 190, 140, 0, 0, "COOL"))
PARTS["INV"] = _inv

# ---------- DRV 栅极驱动板 180x120（每块驱动 1 个半桥）----------
_drv = []
_drv.append(("U1", "soic16w", "Si8271 隔离驱动 高边", 40, 85, 0, 0, "IC"))
_drv.append(("U2", "soic16w", "Si8271 隔离驱动 低边", 40, 35, 0, 0, "IC"))
_drv.append(("U3", "soic8", "退饱和检测", 90, 60, 0, 0, "IC"))
# 隔离电源
_drv.append(("TR1", "ee33", "隔离辅助电源 5W", 140, 85, 0, 0, "IC"))
# 有源钳位
for i in range(4):
    _drv.append(("D%d" % (i + 1), "sot23", "TVS 有源钳位", 25 + i * 18, 60, 0, 0, "IC"))
# 栅极电阻
for i in range(4):
    _drv.append(("Rg%d" % (i + 1), "1206", "2.2Ω 栅极电阻", 25 + i * 18, 45, 0, 0, "PASS"))
# 隔离电容
for i in range(6):
    _drv.append(("C%d" % (i + 1), "1812", "1nF/6kV 隔离", 20 + i * 14, 20, 0, 0, "HV"))
# 光纤输入
_drv.append(("J1", "molex_minifit", "PWM 光纤输入", 165, 90, 90, 0, "ELEC"))
# 栅极输出
_drv.append(("J2", "molex_minifit", "栅极输出 G/E", 165, 30, 90, 0, "ELEC"))
PARTS["DRV"] = _drv

# ---------- CTL 主控板 240x160 ----------
_ctl = []
_ctl.append(("U1", "lqfp144", "STM32H743 主控", 70, 100, 0, 0, "IC"))
_ctl.append(("U2", "bga256", "FPGA 协处理", 150, 100, 0, 0, "IC"))
_ctl.append(("U3", "bga96", "DDR3 x16", 195, 130, 0, 0, "IC"))
_ctl.append(("U4", "bga96", "DDR3 x16", 195, 70, 0, 0, "IC"))
_ctl.append(("U5", "bga153", "eMMC 8GB", 150, 45, 0, 0, "IC"))
_ctl.append(("U6", "qfn32", "电源管理 PMIC", 40, 40, 0, 0, "IC"))
# 晶振
_ctl.append(("Y1", "sot23", "25MHz", 100, 130, 0, 0, "PASS"))
_ctl.append(("Y2", "sot23", "50MHz", 120, 130, 0, 0, "PASS"))
_ctl.append(("Y3", "sot23", "32.768kHz", 45, 65, 0, 0, "PASS"))
# 连接器
_ctl.append(("J1", "rj45", "千兆以太网", 230, 145, 0, 0, "ELEC"))
_ctl.append(("J2", "db9", "CAN-A", 15, 145, 0, 0, "ELEC"))
_ctl.append(("J3", "db9", "CAN-B", 15, 125, 0, 0, "ELEC"))
_ctl.append(("J4", "usbc", "USB-C 调试", 230, 25, 0, 0, "ELEC"))
_ctl.append(("J5", "header_2x32", "背板接口 A", 120, 15, 0, 0, "ELEC"))
_ctl.append(("J6", "header_2x32", "背板接口 B", 60, 15, 0, 0, "ELEC"))
# 去耦阵列
for i, (cx, cy) in enumerate(_grid(58, 78, 6, 1, 5, 0)):
    _ctl.append(("C%d" % (i + 1), "0402", "100nF 去耦", cx, cy, 0, 0, "PASS"))
for i, (cx, cy) in enumerate(_grid(140, 78, 6, 1, 5, 0)):
    _ctl.append(("C%d" % (i + 20), "0402", "100nF 去耦", cx, cy, 0, 0, "PASS"))
# 调试排针
_ctl.append(("J7", "header_2x32", "SWD/JTAG", 200, 45, 0, 0, "ELEC"))
PARTS["CTL"] = _ctl

# ---------- SNS 传感接口板 200x140 ----------
_sns = []
# 高压分压电阻串 20 x 1M
for i, (cx, cy) in enumerate(_grid(30, 110, 10, 2, 9, 12)):
    _sns.append(("R%d" % (i + 1), "2512", "1MΩ 2kV", cx, cy, 0, 0, "HV"))
# 隔离放大
_sns.append(("U1", "soic8", "AMC1311 隔离放大", 135, 118, 0, 0, "IC"))
_sns.append(("U2", "soic8", "ISO7741 数字隔离", 160, 118, 0, 0, "IC"))
# ADC
_sns.append(("U3", "qfn32", "ADS131M08 8ch 24bit", 150, 85, 0, 0, "IC"))
# PT100 接口
for i in range(4):
    _sns.append(("J%d" % (i + 1), "m12_4p", "PT100-%d" % (i + 1), 30 + i * 30, 55, 90, 0, "ELEC"))
# Rogowski
_sns.append(("J5", "gx16", "Rogowski 输入", 165, 55, 0, 0, "ELEC"))
# 真空计
_sns.append(("J6", "gx16", "真空计 RS485", 165, 30, 0, 0, "ELEC"))
# IMU
_sns.append(("U4", "qfn32", "IMU 9 轴", 90, 30, 0, 0, "IC"))
# 基准
_sns.append(("U5", "soic8", "4.096V 基准", 45, 30, 0, 0, "IC"))
# 滤波
for i, (cx, cy) in enumerate(_grid(30, 85, 8, 1, 8, 0)):
    _sns.append(("C%d" % (i + 1), "0805", "100nF 滤波", cx, cy, 0, 0, "PASS"))
PARTS["SNS"] = _sns

# ---------- AUX 辅助电源板 160x110 ----------
_aux = []
_aux.append(("U1", "soic16w", "UCC28780 反激控制", 40, 80, 0, 0, "IC"))
_aux.append(("T1", "ee33", "800V→28V 反激变压器", 85, 70, 0, 0, "HV"))
_aux.append(("D1", "d2pak", "SiC 肖特基 1200V", 40, 50, 0, 0, "HV"))
for i, (cx, cy) in enumerate(_grid(120, 80, 2, 2, 18, 20)):
    _aux.append(("C%d" % (i + 1), "rad_d18x40", "470uF/50V", cx, cy, 0, 0, "PASS"))
_aux.append(("L1", "toroid_40", "输出滤波 22uH", 130, 45, 0, 0, "PASS"))
_aux.append(("U2", "to220", "LM2596 12V 降压", 60, 25, 0, 0, "IC"))
_aux.append(("U3", "sot23", "AMS1117 3.3V", 90, 25, 0, 0, "IC"))
_aux.append(("F1", "fuse_22x58", "输入熔断 2A", 18, 95, 90, 0, "HV"))
_aux.append(("J1", "terminal_m8", "800V 输入", 145, 95, 90, 0, "HV"))
for i, (cx, cy) in enumerate(_grid(30, 12, 8, 1, 8, 0)):
    _aux.append(("C%d" % (i + 10), "0805", "10uF", cx, cy, 0, 0, "PASS"))
PARTS["AUX"] = _aux

# ---------- COM 通信背板 300x120 ----------
_com = []
for i in range(7):
    _com.append(("J%d" % (i + 1), "header_2x32", "槽位 %d" % (i + 1),
                 35 + i * 38, 95, 0, 0, "ELEC"))
_com.append(("U1", "qfn32", "背板管理 MCU", 270, 35, 0, 0, "IC"))
_com.append(("J8", "m12_4p", "外部 CAN", 30, 30, 90, 0, "ELEC"))
_com.append(("J9", "rj45", "外部以太网", 270, 100, 0, 0, "ELEC"))
for i, (cx, cy) in enumerate(_grid(50, 45, 10, 1, 10, 0)):
    _com.append(("C%d" % (i + 1), "0603", "100nF 端接", cx, cy, 0, 0, "PASS"))
_com.append(("TB1", "terminal_m8", "28V 供电", 240, 30, 90, 0, "ELEC"))
PARTS["COM"] = _com

# ============================================================
# 4. 电气网络表（关键连接，用于线束与 PCB 网络）
# ============================================================
NETS = [
    # 高压母线
    {"net": "HV_BAT_P", "v": 800, "cls": "HV", "nodes": ["PWR/TB1", "PWR/F1.1", "PWR/K1.1"]},
    {"net": "HV_BUS_P", "v": 800, "cls": "HV", "nodes": ["PWR/K1.2", "PWR/K2.2", "PWR/BB1",
                                                            "INV/BB1", "AUX/J1"]},
    {"net": "HV_BAT_N", "v": 0, "cls": "HV", "nodes": ["PWR/TB3", "PWR/BB2", "INV/BB2"]},
    {"net": "HV_PRECHARGE", "cls": "HV", "nodes": ["PWR/K2.1", "PWR/R1.1", "PWR/F1.2"]},
    # 相线
    {"net": "PHASE_A", "cls": "HV", "nodes": ["INV/BB3", "INV/Lr.1"]},
    {"net": "PHASE_B", "cls": "HV", "nodes": ["INV/BB4"]},
    # 控制
    {"net": "PWM_A_H", "cls": "SIG", "nodes": ["CTL/U2", "DRV/J1"]},
    {"net": "GATE_A_H", "cls": "SIG", "nodes": ["DRV/J2", "INV/Q1"]},
    {"net": "DESAT_A_H", "cls": "SIG", "nodes": ["DRV/U3", "INV/Q1"]},
    # 辅助
    {"net": "AUX_28V", "cls": "PWR", "nodes": ["AUX/C1", "COM/TB1"]},
    {"net": "V12", "cls": "PWR", "nodes": ["AUX/U2", "CTL/U6"]},
    {"net": "V3V3", "cls": "PWR", "nodes": ["AUX/U3", "CTL/U1"]},
    # 传感
    {"net": "HV_SENSE", "cls": "SIG", "nodes": ["SNS/R1", "SNS/U1"]},
    {"net": "I_COIL", "cls": "SIG", "nodes": ["INV/CT1", "SNS/J5"]},
    # 通信
    {"net": "CANH", "cls": "SIG", "nodes": ["CTL/J2", "COM/J8"]},
    {"net": "CANL", "cls": "SIG", "nodes": ["CTL/J2", "COM/J8"]},
    {"net": "ETH_TX", "cls": "SIG", "nodes": ["CTL/J1", "COM/J9"]},
    # 冷却
    {"net": "COOL_IN", "cls": "COOL", "nodes": ["INV/CP1", "COOL/P1"]},
    {"net": "COOL_OUT", "cls": "COOL", "nodes": ["INV/CP1", "COOL/T1"]},
]

# ============================================================
# 5. 线束拓扑（机体内布线用，坐标为机体坐标 m）
#    kind: hv_coax / hv_single / lv_twist / shield / fiber / coolant / ground
# ============================================================
HARNESS_KINDS = {
    "hv_coax":   {"dia": 14.0, "color": "#c0392b", "name": "高压同轴（母线）"},
    "hv_single": {"dia": 12.0, "color": "#e67e22", "name": "高压单芯（相线）"},
    "lv_twist":  {"dia": 7.0,  "color": "#2c3e50", "name": "低压双绞"},
    "shield":    {"dia": 9.0,  "color": "#7f8c8d", "name": "屏蔽控制"},
    "fiber":     {"dia": 3.0,  "color": "#8e44ad", "name": "光纤"},
    "coolant_in":  {"dia": 16.0, "color": "#2980b9", "name": "冷却进液"},
    "coolant_out": {"dia": 16.0, "color": "#c0392b", "name": "冷却回液"},
    "ground":    {"dia": 6.0,  "color": "#b7950b", "name": "接地编织带"},
}

# 线束段：从 -> 到（机体局部坐标，单位 m，由装配脚本换算）
HARNESS = [
    {"id": "W1", "kind": "hv_coax", "from": "PWR/TB2", "to": "INV/BB1", "len_m": 1.35},
    {"id": "W2", "kind": "hv_single", "from": "INV/BB3", "to": "COILRING/FEED_A", "len_m": 2.10},
    {"id": "W3", "kind": "hv_single", "from": "INV/BB4", "to": "COILRING/FEED_B", "len_m": 2.10},
    {"id": "W4", "kind": "lv_twist", "from": "CTL/J5", "to": "COM/J1", "len_m": 0.42},
    {"id": "W5", "kind": "fiber", "from": "CTL/U2", "to": "DRV/J1", "len_m": 1.85},
    {"id": "W6", "kind": "shield", "from": "SNS/J5", "to": "INV/CT1", "len_m": 0.95},
    {"id": "W7", "kind": "coolant_in", "from": "COOL/P1", "to": "INV/CP1", "len_m": 2.40},
    {"id": "W8", "kind": "coolant_out", "from": "INV/CP1", "to": "COOL/T1", "len_m": 2.40},
    {"id": "W9", "kind": "ground", "from": "PWR/TB3", "to": "FRAME/GND", "len_m": 1.20},
    {"id": "W10", "kind": "hv_coax", "from": "AUX/J1", "to": "PWR/BB1", "len_m": 0.85},
]

# ============================================================
# 6. 机架（板卡安装机架，机体坐标 m）
# ============================================================
RACKS = {
    "PWR_BAY": {"pos": [-0.62, 0.52, -0.05], "rot_deg": 0,   "board": "PWR"},
    "INV_BAY": {"pos": [0.58, 0.50, -0.05],  "rot_deg": 0,   "board": "INV"},
    "DRV_BAY": {"pos": [0.58, 0.12, -0.05],  "rot_deg": 0,   "board": "DRV"},
    "CTL_BAY": {"pos": [-0.60, -0.10, 0.02], "rot_deg": 180, "board": "CTL"},
    "SNS_BAY": {"pos": [-0.60, -0.46, -0.05],"rot_deg": 180, "board": "SNS"},
    "AUX_BAY": {"pos": [0.60, -0.20, -0.05], "rot_deg": 0,   "board": "AUX"},
    "COM_BAY": {"pos": [0.0, -0.62, -0.02],  "rot_deg": 90,  "board": "COM"},
}

# ============================================================
# 7. 导出
# ============================================================
def summary():
    total_parts = sum(len(v) for v in PARTS.values())
    rows = []
    for b in BOARDS:
        n = len(PARTS.get(b["id"], []))
        rows.append((b["id"], b["name"], b["w"], b["h"], b["layers"], n))
    return total_parts, rows


if __name__ == "__main__":
    n, rows = summary()
    print("AG-1 电气系统 rev %s (%s)" % (SYS["rev"], SYS["date"]))
    print("-" * 78)
    print("%-6s %-40s %6s %6s %4s %5s" % ("ID", "名称", "W", "H", "层", "器件"))
    for r in rows:
        print("%-6s %-40s %6.0f %6.0f %4d %5d" % r)
    print("-" * 78)
    print("板卡 %d 块，器件 %d 个，网络 %d 条，线束 %d 段" %
          (len(BOARDS), n, len(NETS), len(HARNESS)))

    out = {
        "sys": SYS, "boards": BOARDS, "packages": PACKAGES,
        "parts": PARTS, "nets": NETS, "harness_kinds": HARNESS_KINDS,
        "harness": HARNESS, "racks": RACKS,
    }
    here = os.path.dirname(os.path.abspath(__file__))
    p = os.path.join(here, "ag1_elec_spec.json")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("-> %s" % p)
