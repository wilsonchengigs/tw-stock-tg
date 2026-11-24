"""研究 40：兩個統計候選合併——融資過熱濾網（研究 38）＋ P/C 提早進場（研究 32），出場 MA80×0.975
規則：
- 空手：站上 MA60×1.01 且「融資不過熱」→ 正常持有；否則若 P/C 提早條件成立且融資不過熱 → 提早持有（lev_early），停損近 10 日低點
- 提早持有：站上 MA60×1.01 → 正常；跌破停損或 13 週 → 出場
- 正常持有：跌破 MA80×0.975 或「融資過熱」→ 出場
融資過熱＝融資金額／加權指數 高於 n 日均值 y 以上
用法：python -X utf8 backtest/research_40_候選組合.py
"""
import importlib.util
import itertools
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r38", os.path.join(HERE, "research_38_融資過熱安慰劑.py"))
R38 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R38)
spec = importlib.util.spec_from_file_location("r32", os.path.join(HERE, "research_32_PC比提早進場.py"))
R32 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R32)
bt = R32.bt
DAYS, PX, N, WE = R32.DAYS, R32.PX, R32.N, R32.WE
M60, M80 = R32.M60, R32.M80
PR = R32.PR


def run(start, end, heat=None, pc=False, lev_early=1.0, real=False):
    r1, r2 = (R32.R.R1R, R32.R.R2R) if real else (bt.R1, bt.R2)
    hot = [False] * N
    if heat:
        n, y = heat
        hot = [i >= n and (v := R38.R.ratio_dev(i, n)) is not None and v > y for i in range(N)]
    i0 = next(i for i, x in enumerate(DAYS) if x >= start)
    i1 = max(i for i, x in enumerate(DAYS) if x <= end)
    eq = peak = 1.0
    mdd, st, lev, pend, stop, wk = 0.0, 0, 0.0, None, 0.0, 0
    for i in range(i0, i1 + 1):
        if i > i0:
            w2, w1 = (lev - 1, 2 - lev) if lev > 1 else (0.0, lev)
            eq *= 1 + w2 * r2[i] + w1 * r1[i] + (1 - w2 - w1) * bt.RC
        if pend is not None:
            eq *= 1 - bt.COST * abs(pend - lev)
            lev, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if not WE[i] or i < 260:
            continue
        if st == 0:
            if PX[i] > M60[i] * 1.01 and not hot[i]:
                st = 2
            elif pc and not hot[i] and any(PR[j] is not None and PR[j] >= 0.95 for j in range(i - 10, i + 1)):
                lo = min(PX[i - 10:i + 1])
                if PX[i] > lo * 1.03:
                    st, stop, wk = 1, lo, 0
        elif st == 1:
            wk += 1
            if PX[i] > M60[i] * 1.01:
                st = 2
            elif PX[i] < stop or wk > 13 or hot[i]:
                st = 0
        elif PX[i] < M80[i] * 0.975 or hot[i]:
            st = 0
        t = {0: 0.0, 1: lev_early, 2: 2.0}[st]
        if t != lev:
            pend = t
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd


def main():
    L = ["研究 40：候選組合（全期 2002- | 前段 -2012 | 後段 2013- | 真實 2015-09～；年化/最大回檔）"]

    def add(nm, **kw):
        rs = [run(a, b, **kw) for a, b in R32.PER]
        rr = run(*R32.REAL, real=True, **kw)
        L.append(f"{nm:34s} " + " | ".join(f"{c * 100:5.1f}%/{m * 100:6.1f}%" for c, m in rs) + f" | 真實 {rr[0] * 100:5.1f}%/{rr[1] * 100:6.1f}%")
        print(L[-1], flush=True)

    add("現行")
    add("P/C 提早 1x", pc=True)
    add("P/C 提早 2x", pc=True, lev_early=2.0)
    for n, y in ((250, 0.15), (250, 0.175), (500, 0.175), (500, 0.20)):
        add(f"融資過熱 n={n} y={y:.1%}", heat=(n, y))
        add(f"融資過熱 n={n} y={y:.1%}＋P/C 1x", heat=(n, y), pc=True)
        add(f"融資過熱 n={n} y={y:.1%}＋P/C 2x", heat=(n, y), pc=True, lev_early=2.0)
    open(os.path.join(HERE, "結果_研究40_候選組合.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
