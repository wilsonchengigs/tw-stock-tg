"""研究 217：主策略核心規則（不含融資過熱，各市場都沒有同口徑融資資料）套到其他市場，檢查是否只在台股有效
規則：週最後一個交易日收盤 > MA60×1.01 → 下一交易日收盤進；< MA80×0.975 → 下一交易日收盤出；在場 2x（每日重設、年借貸成本 2%），空手 0；每次進出成本 0.25%（同 bt）
市場：加權（bt.PX 1998～）、日經 ^N225、KOSPI ^KS11、恆生 ^HSI、S&P ^GSPC（價格指數，不含息，各市場一樣）；1998～2026 與兩段
對照：買進持有 1x、2x（每日重設）；鄰近參數：進場 MA40～80 × 出場 MA60～120（21 組）勝過 1x 買進持有的比例
用法：python -X utf8 backtest/research_217_主策略套亞洲市場.py
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402

TD = 252
BORROW = 0.02 / TD
COST = 0.0025


def load(name, tz):
    g = json.load(open(os.path.join(HERE, f"{name}.json")))
    rows = {}
    for t, p in zip(g["timestamp"], g["indicators"]["quote"][0]["close"]):
        if p:
            rows[datetime.fromtimestamp(t, timezone(timedelta(hours=tz))).strftime("%Y-%m-%d")] = p
    d = sorted(rows)
    return d, np.array([rows[x] for x in d])


MK = {"加權": ([d for d in bt.DAYS], np.array(bt.PX)), "日經": load("N225", 9), "KOSPI": load("KS11", 9),
      "恆生": load("HSI", 8), "S&P": load("GSPC", -5)}


def sim(D, P, ne=60, nx=80, be=0.01, bx=0.025, lev=2.0, start="1998-01-01", end="2026-12-31"):
    n = len(P)
    r = np.r_[0.0, P[1:] / P[:-1] - 1]
    cs = np.r_[0, np.cumsum(P)]
    ma = lambda k, w: (cs[k + 1] - cs[k + 1 - w]) / w if k + 1 >= w else np.nan  # noqa: E731
    wk = [datetime.fromisoformat(x).isocalendar()[:2] for x in D]
    we = [k == n - 1 or wk[k + 1] != wk[k] for k in range(n)]
    i0 = next(k for k, x in enumerate(D) if x >= start)
    i1 = max(k for k, x in enumerate(D) if x <= end)
    state, pend, eq, peak, mdd, eqs = 0, None, 1.0, 1.0, 0.0, []
    for k in range(max(i0, 130), i1 + 1):
        if k > max(i0, 130):
            if state:
                eq *= 1 + lev * r[k] - (lev - 1) * BORROW
        if pend is not None:
            eq *= 1 - COST * lev
            state, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        eqs.append(eq)
        if we[k]:
            if state == 0 and P[k] > ma(k, ne) * (1 + be):
                pend = 1
            elif state == 1 and P[k] < ma(k, nx) * (1 - bx):
                pend = 0
    yrs = len(eqs) / TD
    return eq ** (1 / yrs) - 1, mdd


def bh(D, P, lev, start="1998-01-01", end="2026-12-31"):
    i0 = max(next(k for k, x in enumerate(D) if x >= start), 130)
    i1 = max(k for k, x in enumerate(D) if x <= end)
    r = P[i0 + 1:i1 + 1] / P[i0:i1] - 1
    e = np.cumprod(1 + lev * r - (lev - 1) * BORROW)
    return e[-1] ** (TD / len(r)) - 1, (e / np.maximum.accumulate(e) - 1).min()


L = ["研究 217：主策略核心規則套到其他市場（價格指數、不含息、不含融資過熱；年化／最大回檔）", ""]
SEG = (("1998～2026", "1998-01-01", "2026-12-31"), ("1998～2012", "1998-01-01", "2012-12-31"), ("2013～2026", "2013-01-01", "2026-12-31"))
for name, (D, P) in MK.items():
    L.append(f"【{name}】（{D[0]}～）")
    for lab, a, b in SEG:
        s = sim(D, P, start=a, end=b)
        b1, b2 = bh(D, P, 1, a, b), bh(D, P, 2, a, b)
        L.append(f"  {lab}：規則 2x {s[0]:6.1%}／{s[1]:6.1%}｜買進持有 1x {b1[0]:6.1%}／{b1[1]:6.1%}｜2x {b2[0]:6.1%}／{b2[1]:6.1%}")
    grid = [(ne, nx) for ne in (40, 50, 60, 70, 80) for nx in (60, 80, 100, 120) if nx >= ne] + [(60, 80)]
    wins = 0
    b1 = bh(D, P, 1)
    res = []
    for ne, nx in grid[:-1]:
        s = sim(D, P, ne, nx)
        res.append(s[0])
        wins += s[0] > b1[0] and s[1] > -0.6
    L.append(f"  鄰近 {len(res)} 組（進 MA40～80 × 出 MA60～120）：年化中位 {np.median(res):.1%}（範圍 {min(res):.1%}～{max(res):.1%}），勝過 1x 買進持有且回檔 > -60% 的 {wins} 組")
out = "\n".join(L) + "\n"
print(out)
open(os.path.join(HERE, "結果_研究217_主策略套亞洲市場.txt"), "w", encoding="utf-8").write(out)


def trend_stats():
    """各市場週報酬的趨勢性：變異數比 VR(q)＝Var(q 週報酬)／(q×Var(1 週))，>1＝有趨勢（動能），<1＝均值回歸；
    以及 12 週動能符號的命中率（過去 12 週漲 → 下 4 週漲的比例 − 無條件上漲比例）；1998～2026"""
    L2 = ["\n【趨勢性（週報酬，1998～2026）】VR>1 代表趨勢延續"]
    for name, (D, P) in MK.items():
        wk = [datetime.fromisoformat(x).isocalendar()[:2] for x in D]
        idx = [k for k in range(len(D) - 1) if wk[k + 1] != wk[k] and D[k] >= "1998-01-01"]
        w = np.array([P[k] for k in idx])
        r = np.diff(np.log(w))
        vr = {}
        for q in (4, 12, 26):
            rq = np.array([r[i:i + q].sum() for i in range(0, len(r) - q + 1)])
            vr[q] = rq.var() / (q * r.var())
        m12 = np.array([w[i] / w[i - 12] - 1 for i in range(12, len(w) - 4)])
        f4 = np.array([w[i + 4] / w[i] - 1 for i in range(12, len(w) - 4)])
        hit = np.mean(f4[m12 > 0] > 0) - np.mean(f4 > 0)
        spread = f4[m12 > 0].mean() - f4[m12 <= 0].mean()
        L2.append(f"  {name:5s}：VR(4) {vr[4]:.2f}、VR(12) {vr[12]:.2f}、VR(26) {vr[26]:.2f}｜12 週漲之後 4 週：上漲比例 +{hit * 100:.1f} 個百分點、平均報酬差 {spread:+.2%}")
    return L2


if __name__ == "__main__":
    add = trend_stats()
    print("\n".join(add))
    open(os.path.join(HERE, "結果_研究217_主策略套亞洲市場.txt"), "a", encoding="utf-8").write("\n".join(add) + "\n")
