"""研究 54：P/C 提早進場在新版基準（出場 2.5%＋融資過熱 250／17.5%）上的安慰劑檢定（200 次平移），1x 與 2x
用法：python -X utf8 backtest/research_54_PC新版安慰劑.py
"""
import importlib.util
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r40", os.path.join(HERE, "research_40_候選組合.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
N = R.N


def main():
    rng = random.Random(54)
    L = ["研究 54：P/C 提早進場 × 新版基準 安慰劑檢定（全期 2002- | 前段 | 後段 | 真實）"]
    heat = (250, 0.175)
    base = [R.run(a, b, heat=heat) for a, b in R.R32.PER]
    L.append("新版基準 " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in base) + f" | 真實 {R.run(*R.R32.REAL, heat=heat, real=True)[0]:.1%}")
    pr = R.R32.PR
    i0 = next(i for i in range(N) if pr[i] is not None)
    seg = pr[i0:]
    for lev in (1.0, 2.0):
        real = [R.run(a, b, heat=heat, pc=True, lev_early=lev) for a, b in R.R32.PER]
        rr = R.run(*R.R32.REAL, heat=heat, pc=True, lev_early=lev, real=True)
        sims = []
        for _ in range(200):
            k = rng.randrange(250, len(seg) - 250)
            R.PR = [None] * i0 + seg[k:] + seg[:k]
            sims.append(R.run(*R.R32.PER[0], heat=heat, pc=True, lev_early=lev)[0])
        R.PR = pr
        sims.sort()
        p = (sum(x >= real[0][0] for x in sims) + 1) / 201
        L.append(f"＋P/C 提早 {lev:.0f}x " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in real) + f" | 真實 {rr[0]:.1%}/{rr[1]:.1%} | 平移中位 {sims[100]:.1%}、90 分位 {sims[180]:.1%} | p {p:.3f}")
        print(L[-1], flush=True)
    open(os.path.join(HERE, "結果_研究54_PC新版安慰劑.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
