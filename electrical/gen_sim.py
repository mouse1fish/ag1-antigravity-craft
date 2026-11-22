# -*- coding: utf-8 -*-
"""
AG-1 电路数值仿真
==================
不是画图，是真算。用 RK4 积分求解以下真实电路：
  1) 全桥 LC 串联谐振逆变器（含死区、ESR、变压器励磁）
  2) Cockcroft-Walton 6 级倍压（电荷递推求解纹波与压降）
  3) 场发射线圈阶跃响应（Q / 建立时间 / 峰值电压）
  4) 损耗与热阻链核算

输出: sim/*.csv  +  images/ag1/elec_*.png
"""
import os, sys, math, json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ag1_elec_spec as S

SIM = os.path.join(HERE, "sim")
os.makedirs(SIM, exist_ok=True)
IMG = os.path.join(HERE, "..", "images", "ag1")
os.makedirs(IMG, exist_ok=True)

# ---- 中文字体 ----
for fp in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"):
    if os.path.exists(fp):
        font_manager.fontManager.addfont(fp)
        name = font_manager.FontProperties(fname=fp).get_name()
        plt.rcParams["font.family"] = name
        break
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 130
plt.rcParams["savefig.bbox"] = "tight"

# ============================================================
# 1. 全桥 LC 串联谐振逆变器
#    状态 x = [i_L, v_C]
#    L di/dt = v_ab(t) - v_C - i*R_tot
#    C dv/dt = i
# ============================================================
def sim_resonant():
    Vbus = S.SYS["v_bus_nom"]
    L = S.SYS["lr_uh"] * 1e-6
    C = S.SYS["cr_nf"] * 1e-9
    fsw = S.SYS["f_sw"]
    dead = S.SYS["dead_time_ns"] * 1e-9
    P = S.SYS["p_out_kw"] * 1e3
    # 串联谐振：方波基波有效值 V1 = 4V/(π√2)，按基波匹配取等效负载
    V1rms = 4 * Vbus / (math.pi * math.sqrt(2))
    R_eq = V1rms ** 2 / P
    R_esr = 0.035                   # 电感/电容/走线 ESR
    R_tot = R_eq + R_esr
    T = 1.0 / fsw
    Z0 = math.sqrt(L / C)
    Q = Z0 / R_eq
    fr = 1.0 / (2 * math.pi * math.sqrt(L * C))

    # v_ab 方波（含死区时的零电压段）
    def vab(t):
        ph = (t % T) / T
        # 0~0.5: +Vbus ; 0.5~1: -Vbus ; 两端各留 dead/T 的零区
        d = dead / T
        if ph < d:
            return 0.0
        if ph < 0.5 - d:
            return Vbus
        if ph < 0.5 + d:
            return 0.0
        return -Vbus

    def deriv(t, x):
        i, v = x
        return np.array([(vab(t) - v - i * R_tot) / L, i / C])

    # RK4，50 点/周期分辨死区
    nper = 400
    ncyc = 60
    dt = T / nper
    n = nper * ncyc
    x = np.array([0.0, 0.0])
    ts = np.zeros(n); xs = np.zeros((n, 2)); vabs = np.zeros(n)
    for k in range(n):
        t = k * dt
        ts[k] = t
        xs[k] = x
        vabs[k] = vab(t)
        k1 = deriv(t, x)
        k2 = deriv(t + dt / 2, x + dt / 2 * k1)
        k3 = deriv(t + dt / 2, x + dt / 2 * k2)
        k4 = deriv(t + dt, x + dt * k3)
        x = x + dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)

    # 稳态取最后 10 个周期
    m = slice(n - nper * 10, n)
    i_ss = xs[m, 0]
    v_ss = xs[m, 1]
    t_ss = ts[m]

    i_pk = float(np.max(np.abs(i_ss)))
    i_rms = float(np.sqrt(np.mean(i_ss ** 2)))
    v_pk = float(np.max(np.abs(v_ss)))
    p_calc = i_rms ** 2 * R_eq

    # 器件应力
    res = {
        "Vbus": Vbus, "Lr_uH": L * 1e6, "Cr_nF": C * 1e9, "R_eq": round(R_eq, 4),
        "Z0_ohm": round(Z0, 3), "Q": round(Q, 3), "f_res_kHz": round(fr / 1e3, 2),
        "f_sw_kHz": fsw / 1e3, "ratio_f": round(fsw / fr, 4),
        "I_pk_A": round(i_pk, 1), "I_rms_A": round(i_rms, 1),
        "Vc_pk_kV": round(v_pk / 1e3, 3),
        "P_calc_kW": round(p_calc / 1e3, 1),
        "P_set_kW": P / 1e3,
        "err_pct": round((p_calc - P) / P * 100, 2),
    }

    # CSV
    p = os.path.join(SIM, "llc_waveform.csv")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write("t_us,vab_V,i_L_A,v_C_V,p_kW\n")
        for k in range(len(t_ss)):
            f.write("%.4f,%.1f,%.3f,%.1f,%.3f\n" % (
                t_ss[k] * 1e6, vab(t_ss[k]), i_ss[k], v_ss[k],
                i_ss[k] * vab(t_ss[k]) / 1e3))

    # 绘图
    fig, ax = plt.subplots(3, 1, figsize=(9.5, 7.2), sharex=True)
    tt = (t_ss - t_ss[0]) * 1e6
    ax[0].plot(tt, [vab(t) for t in t_ss], color="#c0392b", lw=1.6)
    ax[0].set_ylabel("桥臂电压 $v_{ab}$ (V)")
    ax[0].set_title("AG-1 谐振逆变器稳态波形  fs=%.1f kHz  fr=%.2f kHz  Q=%.2f"
                    % (fsw / 1e3, fr / 1e3, Q))
    ax[0].grid(alpha=0.3)
    ax[1].plot(tt, i_ss, color="#2980b9", lw=1.5)
    ax[1].axhline(i_pk, ls=":", color="#7f8c8d")
    ax[1].text(tt[5], i_pk * 0.92, " 峰值 %.1f A" % i_pk, fontsize=9, color="#2c3e50")
    ax[1].set_ylabel("谐振电流 $i_L$ (A)")
    ax[1].grid(alpha=0.3)
    ax[2].plot(tt, v_ss, color="#16a085", lw=1.5)
    ax[2].set_ylabel("谐振电容电压 $v_C$ (V)")
    ax[2].set_xlabel("时间 (µs)  ·  10 个开关周期")
    ax[2].grid(alpha=0.3)
    fig.savefig(os.path.join(IMG, "elec_resonant.png"))
    plt.close(fig)
    return res, xs, ts


# ============================================================
# 2. Cockcroft-Walton 6 级倍压
#    电荷递推法求每级电容电压，迭代到稳态
# ============================================================
def sim_cw():
    n = S.SYS["cw_stages"]
    f = S.SYS["f_sw"]
    Vp = S.SYS["v_hv_stage"]           # 副边峰值 20 kV
    C = 1000e-12                        # 每级电容
    Vf = 2.0                            # 二极管正向压降
    P_out = 400.0                       # 高压偏置功率 W
    V_ideal = 2 * n * Vp
    # 迭代求实际输出（含压降与纹波）
    Vout = V_ideal - 2 * n * Vf
    for _ in range(200):
        I_load = P_out / max(Vout, 1.0)
        # 压降
        drop = I_load / (f * C) * (n ** 3 / 6.0 + n ** 2 / 4.0 + n / 3.0)
        ripple = I_load / (f * C) * (n * (n + 1) / 2.0)
        Vout_new = V_ideal - 2 * n * Vf - drop
        if abs(Vout_new - Vout) < 1e-3:
            Vout = Vout_new
            break
        Vout = Vout_new
        del _
    I_load = P_out / Vout
    drop = I_load / (f * C) * (n ** 3 / 6.0 + n ** 2 / 4.0 + n / 3.0)
    ripple = I_load / (f * C) * (n * (n + 1) / 2.0)
    eff = Vout / V_ideal

    res = {
        "stages": n, "Vp_kV": Vp / 1e3, "C_pF": C * 1e12, "f_kHz": f / 1e3,
        "V_ideal_kV": round(V_ideal / 1e3, 2),
        "Vout_kV": round(Vout / 1e3, 2),
        "drop_kV": round(drop / 1e3, 2),
        "ripple_V": round(ripple, 1),
        "ripple_pct": round(ripple / Vout * 100, 4),
        "I_load_mA": round(I_load * 1e3, 3),
        "P_out_W": P_out,
        "efficiency_pct": round(eff * 100, 2),
        "stored_J": round(0.5 * n * C * Vout ** 2 * 4, 2),
    }

    # 逐级电压分布（每级电容在稳态下的直流电压）
    stages_v = []
    for k in range(1, n + 1):
        vk = 2 * Vp * k - 2 * Vf * k - (drop * (k / n) ** 2)
        stages_v.append(max(vk, 0))

    p = os.path.join(SIM, "cw_analysis.csv")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write("stage,V_dc_kV,V_ratio\n")
        for k, v in enumerate(stages_v, 1):
            f.write("%d,%.3f,%.4f\n" % (k, v / 1e3, v / V_ideal))

    fig, ax = plt.subplots(1, 2, figsize=(10, 4.2))
    ax[0].bar(range(1, n + 1), [v / 1e3 for v in stages_v], color="#8e44ad", alpha=0.85)
    ax[0].plot(range(1, n + 1), [v / 1e3 for v in stages_v], "o-", color="#2c3e50", ms=4)
    ax[0].set_xlabel("倍压级数"); ax[0].set_ylabel("累计直流电压 (kV)")
    ax[0].set_title("Cockcroft-Walton 逐级电压")
    ax[0].grid(alpha=0.3, axis="y")

    # 纹波-负载曲线
    loads = np.linspace(0.1, 5.0, 80)
    rp = [l / (S.SYS["f_sw"] * C) * (n * (n + 1) / 2.0) for l in loads]
    ax[1].plot(loads * 1e3, np.array(rp) / 1e3, color="#c0392b", lw=2)
    ax[1].axvline(I_load * 1e3, ls="--", color="#2980b9")
    ax[1].text(I_load * 1e3 + 0.08, max(rp) / 1e3 * 0.75,
               "工作点 %.2f mA" % (I_load * 1e3), fontsize=9, color="#2980b9")
    ax[1].set_xlabel("负载电流 (mA)"); ax[1].set_ylabel("纹波 pk-pk (kV)")
    ax[1].set_title("纹波随负载变化  (C=%.0f pF)" % (C * 1e12))
    ax[1].grid(alpha=0.3)
    fig.savefig(os.path.join(IMG, "elec_cw.png"))
    plt.close(fig)
    return res


# ============================================================
# 3. 场发射线圈阶跃响应
# ============================================================
def sim_coil():
    L = S.SYS["c_coil_uh"] * 1e-6
    Q = S.SYS["q_coil"]
    f = S.SYS["f_sw"]
    w0 = 2 * math.pi * f
    R = w0 * L / Q
    tau = 2 * L / R
    # 阶跃 V (对应 20kV 侧)
    V = S.SYS["v_hv_stage"]
    t = np.linspace(0, 8 * tau, 4000)
    # 欠阻尼 RLC 串联阶跃响应
    zeta = 1 / (2 * Q) if Q > 0 else 1
    wd = w0 * math.sqrt(max(1e-6, 1 - zeta ** 2))
    i = np.zeros_like(t)
    if zeta < 1:
        i = (V / (L * wd)) * np.exp(-zeta * w0 * t) * np.sin(wd * t)
    else:
        i = (V / L) * t * np.exp(-w0 * t)
    i_pk = float(np.max(i))
    t_pk = float(t[np.argmax(i)])
    # 稳态工频电流
    i_ac_pk = V / (w0 * L / 1.0) if w0 else 0
    X_L = w0 * L

    res = {
        "L_mH": L * 1e3, "Q": Q, "R_ohm": round(R, 3),
        "X_L_ohm": round(X_L, 1), "tau_us": round(tau * 1e6, 2),
        "zeta": round(zeta, 4),
        "i_step_pk_A": round(i_pk, 3), "t_pk_us": round(t_pk * 1e6, 2),
        "V_step_kV": V / 1e3,
        "I_ac_pk_A": round(i_ac_pk, 3),
        "B_peak_mT": round(4e-7 * math.pi * 500 * i_ac_pk / 0.05 * 1e3, 2),
        "energy_J": round(0.5 * L * i_pk ** 2, 3),
    }
    p = os.path.join(SIM, "coil_response.csv")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write("t_us,i_A\n")
        for k in range(0, len(t), 4):
            f.write("%.3f,%.4f\n" % (t[k] * 1e6, i[k]))

    fig, ax = plt.subplots(figsize=(8, 3.8))
    ax.plot(t * 1e6, i, color="#d35400", lw=1.6)
    ax.axhline(i_pk, ls=":", color="#7f8c8d")
    ax.annotate("峰值 %.3f A @ %.1f µs" % (i_pk, t_pk * 1e6),
                xy=(t_pk * 1e6, i_pk), xytext=(t_pk * 1e6 + 40, i_pk * 0.8),
                arrowprops=dict(arrowstyle="->", color="#2c3e50"), fontsize=9)
    ax.set_xlabel("时间 (µs)"); ax.set_ylabel("线圈电流 (A)")
    ax.set_title("场发射线圈阶跃响应  L=%.1f mH  Q=%d  ζ=%.3f"
                 % (L * 1e3, Q, zeta))
    ax.grid(alpha=0.3)
    fig.savefig(os.path.join(IMG, "elec_coil.png"))
    plt.close(fig)
    return res, i, t


# ============================================================
# 4. 损耗与热阻链
# ============================================================
def sim_loss(i_rms=None):
    Vbus = S.SYS["v_bus_nom"]
    fsw = S.SYS["f_sw"]
    P = S.SYS["p_out_kw"] * 1e3
    if i_rms is None:
        i_rms = S.SYS["i_bus_max"] / math.sqrt(2)
    I_rms = float(i_rms)
    # SiC MOSFET 参数（CAB450M12XM3 量级：Eon≈9mJ@400A, Eoff≈5mJ@400A, 800V）
    Rds_on = 8.5e-3
    Eon_mJ_A = 9.0 / 400.0
    Eoff_mJ_A = 5.0 / 400.0
    n_sw = 4            # 全桥 4 管，每周期各开关 1 次

    P_cond = 2 * (I_rms ** 2) * Rds_on        # 每桥臂 2 管导通
    P_sw = n_sw * (Eon_mJ_A + Eoff_mJ_A) * 1e-3 * I_rms * fsw
    P_drv = 4 * 0.35                           # 驱动损耗
    P_mag = 0.012 * P                          # 磁性件
    P_bus = 0.004 * P
    P_total = P_cond + P_sw + P_drv + P_mag + P_bus
    eff = P / (P + P_total)

    # 热阻链：结 -> 壳 -> 散热器 -> 冷却液（每模块 2 管并联封装）
    R_jc = 0.06      # K/W 每模块
    R_ch = 0.04      # K/W 导热硅脂
    R_ha = 0.012     # K/W 水冷板
    R_total = R_jc + R_ch + R_ha
    P_per_dev = P_total / 4
    T_rise = P_per_dev * R_total
    T_amb = S.SYS["t_in_max"]
    T_j = T_amb + T_rise + 8    # 加冷却液温升

    res = {
        "P_out_kW": P / 1e3,
        "P_cond_W": round(P_cond, 1),
        "P_sw_W": round(P_sw, 1),
        "P_drv_W": round(P_drv, 1),
        "P_mag_W": round(P_mag, 1),
        "P_bus_W": round(P_bus, 1),
        "P_loss_total_W": round(P_total, 1),
        "efficiency_pct": round(eff * 100, 3),
        "R_jc_K_W": R_jc, "R_ch_K_W": R_ch, "R_ha_K_W": R_ha,
        "R_total_K_W": round(R_total, 3),
        "T_rise_K": round(T_rise, 1),
        "T_junction_C": round(T_j, 1),
        "T_junction_limit_C": 175,
        "margin_K": round(175 - T_j, 1),
        "cool_flow_lpm": S.SYS["flow_lpm"],
        "cool_p_kW": S.SYS["cool_p_kw"],
    }

    # 图：损耗饼图 + 效率-负载曲线
    fig, ax = plt.subplots(1, 2, figsize=(10, 4.2))
    labels = ["导通损耗", "开关损耗", "驱动", "磁性件", "母线"]
    vals = [P_cond, P_sw, P_drv, P_mag, P_bus]
    colors = ["#c0392b", "#e67e22", "#f1c40f", "#16a085", "#2980b9"]
    ax[0].pie(vals, labels=labels, colors=colors, autopct="%1.1f%%",
              textprops={"fontsize": 9}, startangle=90)
    ax[0].set_title("损耗分布  总损耗 %.1f kW  效率 %.2f%%"
                    % (P_total / 1e3, eff * 100))

    loads = np.linspace(0.1, 1.2, 60) * P
    V1rms = 4 * Vbus / (math.pi * math.sqrt(2))
    effs = []
    for pl in loads:
        irms = pl / V1rms
        pc = 2 * irms ** 2 * Rds_on
        ps = n_sw * (Eon_mJ_A + Eoff_mJ_A) * 1e-3 * irms * fsw
        pt = pc + ps + P_drv + 0.012 * pl + 0.004 * pl
        effs.append(pl / (pl + pt) * 100)
    ax[1].plot(loads / 1e3, effs, color="#2980b9", lw=2)
    ax[1].axvline(P / 1e3, ls="--", color="#c0392b")
    ax[1].set_xlabel("输出功率 (kW)"); ax[1].set_ylabel("效率 (%)")
    ax[1].set_title("效率-负载曲线")
    ax[1].grid(alpha=0.3)
    fig.savefig(os.path.join(IMG, "elec_loss.png"))
    plt.close(fig)
    return res


if __name__ == "__main__":
    print("=== AG-1 电路数值仿真 ===\n")
    r1, xs, ts = sim_resonant()
    print("[1] 谐振逆变器")
    for k, v in r1.items():
        print("    %-14s %s" % (k, v))
    print()
    r2 = sim_cw()
    print("[2] Cockcroft-Walton 倍压")
    for k, v in r2.items():
        print("    %-14s %s" % (k, v))
    print()
    r3, _, _ = sim_coil()
    print("[3] 场发射线圈")
    for k, v in r3.items():
        print("    %-14s %s" % (k, v))
    print()
    r4 = sim_loss(r1["I_rms_A"])
    print("[4] 损耗与热")
    for k, v in r4.items():
        print("    %-20s %s" % (k, v))

    allres = {"resonant": r1, "cw": r2, "coil": r3, "loss": r4}
    p = os.path.join(SIM, "sim_results.json")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(allres, f, ensure_ascii=False, indent=1)
    print("\n-> %s" % p)
    print("-> %s\\elec_*.png" % os.path.abspath(IMG))
