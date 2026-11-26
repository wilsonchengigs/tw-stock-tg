"""研究 185：櫃買指數相對加權指數的強弱（中小型股風險偏好）→ v3 濾網與台指期前瞻報酬

資料：backtest/otc_index.csv（build_otc_index.py，櫃買中心，1999-09～）；加權＝bt.PX
相對強弱 RS＝櫃買 ÷ 加權
(A) v3 濾網（研究 138 引擎，1999-09～）：RS < MA60／MA120 時 A 不進場、B 也出場；RS 序列環狀平移 300 次；4 組家族
(B) 事件：RS 20 日變化 ≥90／≤10 分位（250 日）→ 台指期隔天開盤買抱 10 天（去叢集 sign-flip，對照同波動度非訊號日）
用法：python -X utf8 backtest/research_185_櫃買相對強弱.py
"""
import csv
import importlib.util
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r138", os.path.join(HERE, "research_138_金字塔加碼與分段停損.py"))
R138 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R138)
DAYS, PX = R138.DAYS, np.array(R138.PX)
START = "2000-06-01"


def rs_series():
    otc = {r["date"]: float(r["close"]) for r in csv.DictReader(open(os.path.join(HERE, "otc_index.csv"), encoding="utf-8"))}
    v = np.array([otc.get(d, np.nan) / PX[i] for i, d in enumerate(DAYS)])
    for i in range(1, len(v)):
        if np.isnan(v[i]):
            v[i] = v[i - 1]
    return v


def ma(x, L):
    out = np.full(len(x), np.nan)
    c = np.nancumsum(x)
    for i in range(L - 1, len(x)):
        w = x[i - L + 1:i + 1]
        if not np.isnan(w).any():
            out[i] = w.mean()
    return out


def make_sizer(weak, also_exit):
    def f(i, on, px2, ctx):
        if not on:
            ctx["in"] = False
            return 0.0
        if ctx.get("in"):
            if also_exit and weak[i]:
                ctx["in"] = False
                return 0.0
            return 1.0
        if weak[i]:
            return 0.0
        ctx["in"] = True
        return 1.0
    return f


def main():
    rs = rs_series()
    end = DAYS[-1]
    base = R138.run(R138.FULL, START, end)
    out = [f"研究 185：櫃買÷加權 相對強弱（{START}～{end}）", f"v3 現行：{base[0]:.1%}／{base[1]:.1%}", "", "== (A) v3 濾網 =="]
    rng = np.random.default_rng(185)
    shifts = rng.integers(250, len(DAYS) - 250, 300)
    real, nulls = [], []
    for L in (60, 120):
        weak = rs < ma(rs, L)
        weak = np.where(np.isnan(ma(rs, L)), False, weak)
        for ex in (False, True):
            res = R138.run(make_sizer(weak, ex), START, end)
            d = res[0] - base[0]
            nd = np.array([R138.run(make_sizer(np.roll(weak, s), ex), START, end)[0] - base[0] for s in shifts])
            p = (1 + np.sum(nd >= d)) / (len(nd) + 1)
            segs = "  ".join(f"{a[:4]}–{z[:4]} {R138.run(make_sizer(weak, ex), a, z)[0] - R138.run(R138.FULL, a, z)[0]:+.1%}"
                             for a, z in (("2000-06-01", "2008-12-31"), ("2009-01-01", "2017-12-31"), ("2018-01-01", end)))
            real.append(p)
            nulls.append(nd)
            out.append(f"RS<MA{L} {'B 也出場' if ex else 'A 只擋進'}：{res[0]:.1%}／{res[1]:.1%}（差 {d:+.2%}，p {p:.3f}）｜{segs}")
    N = np.array(nulls).T
    ranks = np.array([[(1 + np.sum(N[:, j] >= N[s, j])) / (len(N) + 1) for j in range(N.shape[1])] for s in range(len(N))])
    minp = ranks.min(axis=1)
    out.append(f"家族（4 組）：最佳 p {min(real):.3f} → 家族 p {(1 + np.sum(minp <= min(real))) / (len(minp) + 1):.3f}")
    out.append("")
    # (B) 事件
    ch = np.r_[np.full(20, np.nan), rs[20:] / rs[:-20] - 1]
    pct = np.full(len(rs), np.nan)
    for i in range(270, len(rs)):
        w = ch[i - 250:i]
        if not np.isnan(w).any():
            pct[i] = np.mean(w < ch[i])
    fwd = np.full(len(PX), np.nan)
    fwd[:-11] = PX[11:] / PX[1:-10] - 1     # 隔天收盤近似進場 → 第 11 天收盤（加權指數近似台指期）
    r1 = np.r_[0.0, PX[1:] / PX[:-1] - 1]
    vol = np.array([np.std(r1[max(1, i - 20):i]) if i > 5 else np.nan for i in range(len(PX))])
    dec = np.digitize(np.nan_to_num(vol), np.nanpercentile(vol, np.arange(10, 100, 10)))
    out.append("== (B) RS 20 日變化極端 → 之後 10 天（加權指數近似，去叢集）==")
    for lab, sig in (("中小型股相對強 ≥90 分位", pct >= 0.9), ("中小型股相對弱 ≤10 分位", pct <= 0.1)):
        g = ~np.isnan(fwd) & ~np.isnan(pct)
        idx, last = [], -99
        for i in np.where(sig & g)[0]:
            if i - last >= 10:
                idx.append(i)
            last = i
        idx = np.array(idx)
        ctrl = g & ~sig
        d_ = np.array([fwd[i] - fwd[np.where(ctrl & (dec == dec[i]))[0]].mean() for i in idx])
        sims = np.array([(d_ * rng.choice((-1, 1), len(d_))).mean() for _ in range(2000)])
        p = (1 + np.sum(np.abs(sims) >= abs(d_.mean()))) / 2001
        out.append(f"{lab}：{len(idx)} 個事件 10 天 {fwd[idx].mean():+.2%} 勝率 {np.mean(fwd[idx] > 0):.0%} 比同波動 {d_.mean():+.2%}（p {p:.3f}）")
    out.append(f"目前 RS 20 日變化第 {pct[-1]:.0%} 分位；RS 在 MA60 {'之下' if rs[-1] < ma(rs, 60)[-1] else '之上'}")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究185_櫃買相對強弱.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
