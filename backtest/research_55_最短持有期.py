"""研究 55：最短持有期——進場後 K 週內不因 MA80×0.975 出場，只有跌破更深的停損（進場價 ×(1−s)）才出
目的：減少盤整年（2010～2013）反覆進出。新版基準（含融資濾網）＋拔靴（不含融資濾網）
用法：python -X utf8 backtest/research_55_最短持有期.py
"""
import importlib.util
import itertools
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r41", os.path.join(HERE, "research_41_總經濾網.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
spec = importlib.util.spec_from_file_location("r24", os.path.join(HERE, "research_24_候選參數拔靴檢驗.py"))
R24 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R24)
bt, DAYS, PX, N, WE, HOT = R.bt, R.DAYS, R.PX, R.N, R.WE, R.HOT
RR = R.R40.R32.R


def core(px, we, m60, m80, hot, K, s, i_start, i_end, r2fn):
    eq = peak = 1.0
    mdd, on, pos, pend, wk, ent = 0.0, False, False, None, 0, 0.0
    for i in range(i_start, i_end + 1):
        if i > i_start:
            eq *= 1 + (r2fn(i) if pos else bt.RC)
        if pend is not None:
            eq *= 1 - bt.COST * 2
            pos, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if we[i] and i >= 261:
            h = hot[i] if hot else False
            if on:
                wk += 1
                if wk <= K:
                    out = px[i] < ent * (1 - s) or h
                else:
                    out = px[i] < m80[i] * 0.975 or h
                on = not out
            elif px[i] > m60[i] * 1.01 and not h:
                on, wk, ent = True, 0, px[i]
            if on != pos:
                pend = on
    return eq, mdd


def hist(K, s, start, end, real=False):
    r2 = RR.R2R if real else bt.R2
    i0 = next(i for i, x in enumerate(DAYS) if x >= start)
    i1 = max(i for i, x in enumerate(DAYS) if x <= end)
    eq, mdd = core(PX, WE, R.M60, R.M80, HOT, K, s, i0, i1, lambda i: r2[i])
    return eq ** (bt.TD / (i1 - i0)) - 1, mdd


def boot(K, s, paths):
    out = []
    for rets in paths:
        px = [100.0]
        for r in rets:
            px.append(px[-1] * (1 + r))
        r2 = [0.0] + [2 * (px[i] / px[i - 1] - 1 + bt.DIV / bt.TD) - bt.DRAG / bt.TD for i in range(1, len(px))]
        we = [i % 5 == 0 for i in range(len(px))]
        eq, mdd = core(px, we, R24.sma(px, 60), R24.sma(px, 80), None, K, s, 261, len(px) - 1, lambda i: r2[i])
        out.append((eq ** (1 / R24.YEARS) - 1, mdd))
    return out


def main():
    rng = random.Random(7)
    paths = [R24.R.path(rng, 250) for _ in range(300)]
    b0 = boot(0, 0.0, paths)
    L = ["研究 55：最短持有期（歷史 全期 2002- | 前段 | 後段 | 真實；拔靴 300 條：年化中位、P(<-50%)、勝現行）"]
    for K, s in [(0, 0.0)] + list(itertools.product((4, 8, 13), (0.08, 0.12, 0.16))):
        rs = [hist(K, s, a, b) for a, b in R.PER]
        rr = hist(K, s, *R.REAL, real=True)
        b = b0 if K == 0 else boot(K, s, paths)
        cs = sorted(x[0] for x in b)
        win = sum(1 for x, y in zip(b, b0) if x[0] > y[0] + 1e-12) / len(b)
        nm = "新版（無最短持有）" if K == 0 else f"至少 {K} 週、停損 -{s:.0%}"
        L.append(f"{nm:20s} " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in rs) + f" | 真實 {rr[0]:.1%}/{rr[1]:.1%} || 拔靴 {cs[150]:.1%}、P {sum(x[1] < -0.5 for x in b) / len(b):.0%}、勝 {win:.0%}")
        print(L[-1], flush=True)
    open(os.path.join(HERE, "結果_研究55_最短持有期.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
