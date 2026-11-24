"""研究 38b：融資過熱濾網鄰近參數（均值天數 n × 門檻 y），每組 100 次平移安慰劑
用法：python -X utf8 backtest/research_38b_融資過熱鄰近參數.py
"""
import importlib.util
import itertools
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r38", os.path.join(HERE, "research_38_融資過熱安慰劑.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
R3, N = R.R, R.N


def main():
    rng = random.Random(13)
    L = ["研究 38b：融資過熱濾網鄰近參數（全期 2002- | 前段 -2012 | 後段 2013- | 真實；p＝100 次平移）",
         "現行：20.2%／-43.6% | 13.3% | 25.9% | 真實 33.0%／-37.2%"]
    for n, y in itertools.product((120, 250, 500), (0.10, 0.125, 0.15, 0.175, 0.20, 0.25)):
        dev = [R3.ratio_dev(i, n) if i >= n else None for i in range(N)]
        kw = R.kw_for(dev, y)
        a = R3.run("2002-01-01", "2026-12-31", **kw)
        b = R3.run("2002-01-01", "2012-12-31", **kw)
        c = R3.run("2013-01-01", "2026-12-31", **kw)
        rr = R3.run("2015-09-01", "2026-12-31", r2=R.R2R, **kw)
        i0 = next(i for i in range(N) if dev[i] is not None)
        seg = dev[i0:]
        sims = []
        for _ in range(100):
            k = rng.randrange(250, len(seg) - 250)
            sims.append(R3.run("2002-01-01", "2026-12-31", **R.kw_for([None] * i0 + seg[k:] + seg[:k], y))["cagr"])
        p = (sum(x >= a["cagr"] for x in sims) + 1) / 101
        L.append(f"n={n:3d} y={y:5.1%}  {a['cagr']:5.1%}/{a['mdd']:6.1%} | {b['cagr']:5.1%} | {c['cagr']:5.1%} | 真實 {rr['cagr']:5.1%}/{rr['mdd']:6.1%} | p {p:.2f}")
        print(L[-1], flush=True)
    open(os.path.join(HERE, "結果_研究38b_融資過熱鄰近參數.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
