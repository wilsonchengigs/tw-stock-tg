"""研究 98（待研究 26）：極端高波動時降槓桿——要同時改善 1990 年代、又不傷 1998～2026
資料：1990-01～1997-12 證交所（taiex_1990_1997.csv）＋ 1998～ bt 的加權指數（Yahoo）
規則：核心均線（MA60×1.01 進、MA80×0.975 出，無融資濾網；兩段都一樣才公平），在場時若近 n 日年化波動 > v → 只押 1x（或 1.5x）
用法：python -X utf8 backtest/research_98_極端波動降槓桿.py
"""
import csv
import importlib.util
import itertools
import math
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402

old = [(r["date"], float(r["close"])) for r in csv.DictReader(open(os.path.join(HERE, "taiex_1990_1997.csv"), encoding="utf-8"))]
new = [(d, p) for d, p in zip(bt.DAYS, bt.PX) if d >= "1998-01-01"]
SER = old + new
D = [d for d, _ in SER]
P = [p for _, p in SER]
N = len(P)
TD = 250
R1 = [0.0] + [P[i] / P[i - 1] - 1 + 0.03 / TD for i in range(1, N)]
RC = 0.01 / TD
WE = [i == N - 1 or date.fromisoformat(D[i]).isocalendar()[:2] != date.fromisoformat(D[i + 1]).isocalendar()[:2] for i in range(N)]


def sma(n):
    out, s = [None] * N, 0.0
    for i, v in enumerate(P):
        s += v
        if i >= n:
            s -= P[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def vol(n):
    lr = [0.0] + [math.log(P[i] / P[i - 1]) for i in range(1, N)]
    out, s, s2 = [None] * N, 0.0, 0.0
    for i in range(N):
        s += lr[i]
        s2 += lr[i] ** 2
        if i >= n:
            s -= lr[i - n]
            s2 -= lr[i - n] ** 2
            out[i] = math.sqrt(max(s2 / n - (s / n) ** 2, 0) * TD)
    return out


M60, M80 = sma(60), sma(80)
VOL = {n: vol(n) for n in (20, 60, 120)}


def run(start, end, n=None, v=None, low=1.0):
    i0 = next(i for i, d in enumerate(D) if d >= start and M80[i] is not None and i >= 130)
    i1 = max(i for i, d in enumerate(D) if d <= end)
    eq = peak = 1.0
    mdd, on, lev, pend = 0.0, False, 0.0, None
    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + ((lev * R1[i] - max(lev - 1, 0) * 0.01 / TD) if lev > 0 else RC)
        if pend is not None:
            eq *= 1 - 0.0025 * abs(pend - lev)
            lev, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if WE[i]:
            on = (not P[i] < M80[i] * 0.975) if on else (P[i] > M60[i] * 1.01)
            t = 0.0
            if on:
                t = low if (n and VOL[n][i] is not None and VOL[n][i] > v) else 2.0
            if t != lev:
                pend = t
    yrs = (i1 - i0) / TD
    return eq ** (1 / yrs) - 1, mdd


def main():
    v60 = sorted(x for x, d in zip(VOL[60], D) if x and d >= "1998")
    v60o = sorted(x for x, d in zip(VOL[60], D) if x and d < "1998")
    L = ["研究 98：極端高波動降槓桿（1990-1997 | 1998-2012 | 2013-2026 | 1990-2026 全期；年化/最大回檔）",
         f"60 日年化波動中位：1990 年代 {v60o[len(v60o) // 2]:.0%}、1998 後 {v60[len(v60) // 2]:.0%}；1998 後 90／95 分位 {v60[int(.9 * len(v60))]:.0%}／{v60[int(.95 * len(v60))]:.0%}"]
    pers = (("1990-01-01", "1997-12-31"), ("1998-01-01", "2012-12-31"), ("2013-01-01", "2026-12-31"), ("1990-01-01", "2026-12-31"))
    L.append("核心 2x（不降）  " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in (run(a, b) for a, b in pers)))
    for n, v, low in itertools.product((20, 60, 120), (0.30, 0.35, 0.40, 0.50), (1.0, 1.5)):
        rs = [run(a, b, n, v, low) for a, b in pers]
        L.append(f"波動{n}日 > {v:.0%} → {low}x  " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in rs))
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究98_極端波動降槓桿.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
