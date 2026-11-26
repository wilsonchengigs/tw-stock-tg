"""研究 187：大盤估值（上市股票本益比／殖利率中位數，每週）當 v3 濾網與長期報酬預測（研究紀錄列過兩次「估值濾網」新題目）

資料：backtest/valuation_weekly.csv（build_valuation_weekly.py，證交所 BWIBBU_d，2005-09～）
估值分位：過去 5 年（260 週，至少 104 週）滾動百分位；當週收盤後可知，往後補到每日
(1) 預測力：估值分位五等分 → 之後 1 年（250 日）加權指數報酬（重疊樣本，只看單調性）；與 1 年報酬的相關
(2) v3 濾網（研究 138 引擎，2007-09～）：
    A 貴（PE 分位 ≥90 或殖利率分位 ≤10）時不進場；B 貴時也出場；C 便宜（PE 分位 ≤10）時空手提早進 1 倍（停損 −8%）
    估值序列環狀平移 300 次；家族最小 p；三段 2007–2013／2014–2019／2020–2026
用法：python -X utf8 backtest/research_187_估值濾網.py
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
START = "2007-09-01"


def daily_pct():
    rows = list(csv.DictReader(open(os.path.join(HERE, "valuation_weekly.csv"), encoding="utf-8")))
    wd = [r["date"] for r in rows]
    pe = np.array([float(r["pe_median"]) for r in rows])
    yl = np.array([float(r["yield_median"]) for r in rows])

    def roll_pct(x):
        p = np.full(len(x), np.nan)
        for i in range(104, len(x)):
            w = x[max(0, i - 260):i]
            p[i] = np.mean(w < x[i])
        return p
    ppe, pyl = roll_pct(pe), roll_pct(yl)
    idx = np.searchsorted(wd, DAYS, side="right") - 1
    ok = idx >= 0
    out = {}
    for nm, arr in (("pe", ppe), ("yl", pyl), ("pe_raw", pe), ("yl_raw", yl)):
        s = np.full(len(DAYS), np.nan)
        s[ok] = arr[idx[ok]]
        out[nm] = s
    return out


def make_sizer(expensive, cheap, mode):
    def f(i, on, px2, ctx):
        if mode == "C":
            if on:
                ctx.pop("early", None)
                return 1.0
            e = ctx.get("early")
            if e is not None:
                if PX[i] < e * 0.92:
                    ctx.pop("early")
                    ctx["cool"] = i
                    return 0.0
                return 0.5
            if cheap[i] and i - ctx.get("cool", -99) > 20:
                ctx["early"] = PX[i]
                return 0.5
            return 0.0
        if not on:
            ctx["in"] = False
            return 0.0
        if ctx.get("in"):
            if mode == "B" and expensive[i]:
                ctx["in"] = False
                return 0.0
            return 1.0
        if expensive[i]:
            return 0.0
        ctx["in"] = True
        return 1.0
    return f


def main():
    V = daily_pct()
    out = [f"研究 187：大盤估值濾網（上市本益比／殖利率中位數，{START}～{DAYS[-1]}）",
           f"目前：本益比中位數 {V['pe_raw'][-1]:.1f}（5 年第 {V['pe'][-1]:.0%} 分位）、殖利率中位數 {V['yl_raw'][-1]:.2f}%（第 {V['yl'][-1]:.0%} 分位）", ""]
    # (1) 預測力
    f250 = np.full(len(PX), np.nan)
    f250[:-250] = PX[250:] / PX[:-250] - 1
    out.append("== (1) 估值分位五等分 → 之後一年加權指數（價格）報酬（重疊樣本）==")
    for nm, lab in (("pe", "本益比分位"), ("yl", "殖利率分位")):
        g = ~np.isnan(V[nm]) & ~np.isnan(f250)
        q = V[nm][g]
        r = f250[g]
        cells = []
        for a, b in ((0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01)):
            m = (q >= a) & (q < b)
            cells.append(f"{a:.0%}–{min(b, 1):.0%} {r[m].mean():+.1%}（{m.sum()} 天）")
        out.append(f"{lab}：" + "｜".join(cells) + f"｜相關 {np.corrcoef(q, r)[0, 1]:+.2f}")
    out.append("")
    # (2) 濾網
    base = R138.run(R138.FULL, START, DAYS[-1])
    out.append(f"== (2) v3 濾網（現行 {base[0]:.1%}／{base[1]:.1%}）==")
    rng = np.random.default_rng(187)
    shifts = rng.integers(260, len(DAYS) - 260, 300)
    real, nulls = [], []

    def masks(pe, yl):
        exp_ = np.nan_to_num(pe, nan=0.5) >= 0.9
        exp2 = np.nan_to_num(yl, nan=0.5) <= 0.1
        cheap = np.nan_to_num(pe, nan=0.5) <= 0.1
        return exp_, exp2, cheap
    for nm, (ei, mode) in {"A PE≥90 不進": (0, "A"), "B PE≥90 也出": (0, "B"), "A 殖利率≤10 不進": (1, "A"), "B 殖利率≤10 也出": (1, "B"),
                           "C PE≤10 提早進 1x": (2, "C")}.items():
        m = masks(V["pe"], V["yl"])
        exp_ = m[ei] if ei < 2 else m[0]
        res = R138.run(make_sizer(exp_, m[2], mode), START, DAYS[-1])
        d = res[0] - base[0]
        nd = []
        for s in shifts:
            ms = masks(np.roll(V["pe"], s), np.roll(V["yl"], s))
            nd.append(R138.run(make_sizer(ms[ei] if ei < 2 else ms[0], ms[2], mode), START, DAYS[-1])[0] - base[0])
        nd = np.array(nd)
        p = (1 + np.sum(nd >= d)) / (len(nd) + 1)
        segs = "  ".join(f"{a[:4]}–{z[:4]} {R138.run(make_sizer(exp_, m[2], mode), a, z)[0] - R138.run(R138.FULL, a, z)[0]:+.1%}"
                         for a, z in (("2007-09-01", "2013-12-31"), ("2014-01-01", "2019-12-31"), ("2020-01-01", DAYS[-1])))
        real.append(p)
        nulls.append(nd)
        out.append(f"{nm:16s}：{res[0]:.1%}／{res[1]:.1%}（差 {d:+.2%}，p {p:.3f}）｜{segs}")
    N = np.array(nulls).T
    ranks = np.array([[(1 + np.sum(N[:, j] >= N[s, j])) / (len(N) + 1) for j in range(N.shape[1])] for s in range(len(N))])
    minp = ranks.min(axis=1)
    out.append(f"家族（{len(real)} 組）：最佳 p {min(real):.3f} → 家族 p {(1 + np.sum(minp <= min(real))) / (len(minp) + 1):.3f}")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究187_估值濾網.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
