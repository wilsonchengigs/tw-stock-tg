"""研究 218：依台股滾動趨勢性（研究 217）調主策略槓桿
VR_t＝截至 t 前 W 年的加權週報酬 VR(26)（每週五更新，只用過去資料）；v3 在場時：VR ≥ 門檻 → 2x，否則 lowlev（1x／1.5x）
W＝3／5／8 年 × 門檻 0.9／1.0 × lowlev 1／1.5 ＝ 12 組；v3 進出不變（研究 138 run 引擎）
比較：全期 2002～、兩段、真實價；與「同平均曝險的固定槓桿」比；VR 序列環狀平移 300 次、家族最小 p 值
用法：python -X utf8 backtest/research_218_趨勢性調槓桿.py
"""
import os
import sys
from datetime import date

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_138_金字塔加碼與分段停損 as R138  # noqa: E402

V, bt, DAYS, PX, N = R138.V, R138.bt, R138.DAYS, R138.PX, R138.N
wk = [date.fromisoformat(d).isocalendar()[:2] for d in DAYS]
WEK = [k for k in range(N - 1) if wk[k + 1] != wk[k]]
logw = np.log(np.array([PX[k] for k in WEK]))
rw = np.diff(logw)


def vr_series(years, q=26):
    nw = int(years * 52)
    out = np.full(N, np.nan)
    cur = np.nan
    j = 0
    for wi in range(len(WEK)):
        if wi >= nw:
            r = rw[wi - nw:wi]
            rq = np.convolve(r, np.ones(q), "valid")
            cur = rq.var() / (q * r.var())
        k0 = WEK[wi]
        k1 = WEK[wi + 1] if wi + 1 < len(WEK) else N
        out[k0:k1] = cur  # 週五收盤算出，當天收盤起適用（下一天收盤成交由引擎處理）
    return out


def sizer_of(vr, th, low):
    def f(i, on, px2, ctx):
        if not on:
            return 0.0
        return 1.0 if (np.isnan(vr[i]) or vr[i] >= th) else low / 2
    return f


def perf(sz, lev=2.0):
    out = []
    for a, b in V.PER:
        cg, mdd, _, ex = R138.run(sz, a, b, lev=lev)
        out.append((cg, mdd, ex))
    cg, mdd, _, ex = R138.run(sz, *V.REAL, real=True, lev=lev)
    out.append((cg, mdd, ex))
    return out


def fmt(p):
    return "  ".join(f"{c:5.1%}／{m:6.1%}" for c, m, _ in p)


base = perf(R138.FULL)
L = ["研究 218：依滾動趨勢性 VR(26) 調主策略槓桿（全期 2002～｜2002–2012｜2013～｜真實價 2015-09～）", f"現行 v3 2x：{fmt(base)}", ""]
GRID = [(W, th, low) for W in (3, 5, 8) for th in (0.9, 1.0) for low in (1.0, 1.5)]
VRS = {W: vr_series(W) for W in (3, 5, 8)}
real = []
for W, th, low in GRID:
    p = perf(sizer_of(VRS[W], th, low))
    real.append(p[0][0])
    avg = p[0][2] / 1.0
    fixed = perf(R138.FULL, lev=2.0 * avg / base[0][2])
    low_frac = np.mean([VRS[W][i] < th for i in range(N) if DAYS[i] >= "2002" and not np.isnan(VRS[W][i])])
    L.append(f"W {W} 年 VR<{th} → {low}x：{fmt(p)}｜同曝險固定 {fixed[0][0]:5.1%}／{fixed[0][1]:6.1%}｜低槓桿時間 {low_frac:.0%}")
rng = np.random.default_rng(218)
S = 300
shifts = rng.integers(52 * 5, N - 52 * 5, S)
null = np.zeros((S, len(GRID)))
for si, s in enumerate(shifts):
    for j, (W, th, low) in enumerate(GRID):
        null[si, j] = R138.run(sizer_of(np.roll(VRS[W], s), th, low), *V.PER[0])[0]
realv = np.array(real)
single = (1 + (null >= realv).sum(axis=0)) / (S + 1)
ranks = np.array([[(1 + np.sum(null[:, j] >= null[s, j])) / (S + 1) for j in range(len(GRID))] for s in range(S)])
minp = ranks.min(axis=1)
L.append("\n【平移安慰劑（全期年化）】")
for j, g in enumerate(GRID):
    L.append(f"  W {g[0]} VR<{g[1]} → {g[2]}x：單組 p {single[j]:.3f}、家族 p {(1 + np.sum(minp <= single[j])) / (S + 1):.3f}")
L.append(f"\n現況：VR(26) 3 年 {VRS[3][-1]:.2f}、5 年 {VRS[5][-1]:.2f}、8 年 {VRS[8][-1]:.2f}")
out = "\n".join(L) + "\n"
print(out)
open(os.path.join(HERE, "結果_研究218_趨勢性調槓桿.txt"), "w", encoding="utf-8").write(out)
