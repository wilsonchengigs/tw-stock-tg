"""研究 43：新版策略（出場 2.5%＋融資過熱濾網）的風險選單：槓桿 1.25～2x（00631L＋0050 混合）歷史表現
用法：python -X utf8 backtest/research_43_新版風險選單.py
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r41", os.path.join(HERE, "research_41_總經濾網.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
bt, DAYS, PX, N, WE = R.bt, R.DAYS, R.PX, R.N, R.WE
RR = R.R40.R32.R


def run(lev, start, end, heat=True, real=False):
    r1, r2 = (RR.R1R, RR.R2R) if real else (bt.R1, bt.R2)
    w2 = lev - 1
    i0 = next(i for i, x in enumerate(DAYS) if x >= start)
    i1 = max(i for i, x in enumerate(DAYS) if x <= end)
    eq = peak = 1.0
    mdd, on, pos, pend = 0.0, False, False, None
    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + ((w2 * r2[i] + (1 - w2) * r1[i]) if pos else bt.RC)
        if pend is not None:
            eq *= 1 - bt.COST * lev
            pos, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if WE[i] and i >= 260:
            hot = heat and R.HOT[i]
            on = (not (PX[i] < R.M80[i] * 0.975 or hot)) if on else (PX[i] > R.M60[i] * 1.01 and not hot)
            if on != pos:
                pend = on
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd


def main():
    L = ["研究 43：新版風險選單（2002-2026 全期 | 前段 | 後段 | 真實 2015-09～；年化/最大回檔）"]
    for lev, nm in ((1.0, "0050 100%（1x）"), (1.25, "00631L 25%＋0050 75%"), (1.5, "00631L 50%＋0050 50%"), (1.75, "00631L 75%＋0050 25%"), (2.0, "00631L 100%")):
        for heat in (False, True):
            rs = [run(lev, a, b, heat) for a, b in R.PER]
            rr = run(lev, *R.REAL, heat, real=True)
            L.append(f"{nm:22s} {'＋融資濾網' if heat else '          '} " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in rs) + f" | 真實 {rr[0]:.1%}/{rr[1]:.1%}")
            print(L[-1], flush=True)
    open(os.path.join(HERE, "結果_研究43_新版風險選單.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
