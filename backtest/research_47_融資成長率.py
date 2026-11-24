"""研究 47：融資過熱的其他定義——融資金額 n 日成長率 > x（不除以指數），以及與現行「融資÷指數偏離」並用
基準：出場 2.5%（不含融資濾網）與新版（含 250／17.5%）；每組 100 次平移安慰劑
用法：python -X utf8 backtest/research_47_融資成長率.py
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
R3, N = R.R3 if hasattr(R, "R3") else R.R, R.N
M = R3.M
DEV = R.DEV


def run(flag, combine=False):
    if combine:
        f = [bool(a) or (d is not None and d > 0.175) for a, d in zip(flag, DEV)]
    else:
        f = [bool(a) for a in flag]
    kw = dict(entry_ok=lambda i: not f[i], force_exit=lambda i: f[i], bout=0.025)
    out = [R3.run(a, b, **kw)["cagr"] for a, b in (("2002-01-01", "2026-12-31"), ("2002-01-01", "2012-12-31"), ("2013-01-01", "2026-12-31"))]
    rr = R3.run("2015-09-01", "2026-12-31", r2=R.R2R, **kw)["cagr"]
    mdd = R3.run("2002-01-01", "2026-12-31", **kw)["mdd"]
    return out, rr, mdd


def main():
    rng = random.Random(47)
    L = ["研究 47：融資成長率濾網（全期 | 前段 | 後段 | 真實 | 全期回檔 | 平移 p）"]
    for nm, flag, comb in (("出場 2.5%（無融資濾網）", [False] * N, False), ("新版（融資÷指數 250/17.5%）", [False] * N, True)):
        o, rr, mdd = run(flag, comb)
        L.append(f"{nm:30s} " + " | ".join(f"{x:.1%}" for x in o) + f" | {rr:.1%} | {mdd:.1%}")
    for n, x in itertools.product((20, 60, 120), (0.10, 0.15, 0.20, 0.30)):
        g = [None if (i < n or M[i] is None or M[i - n] is None) else (M[i] / M[i - n] - 1 > x) for i in range(N)]
        for comb in (False, True):
            o, rr, mdd = run(g, comb)
            i0 = next(i for i in range(N) if g[i] is not None)
            seg = g[i0:]
            sims = []
            for _ in range(100):
                k = rng.randrange(250, len(seg) - 250)
                sims.append(run([None] * i0 + seg[k:] + seg[:k], comb)[0][0])
            p = (sum(s >= o[0] for s in sims) + 1) / 101
            L.append(f"融資 {n} 日增 > {x:.0%}{'＋新版' if comb else '      '}  " + " | ".join(f"{v:.1%}" for v in o) + f" | {rr:.1%} | {mdd:.1%} | p {p:.2f}")
            print(L[-1], flush=True)
    open(os.path.join(HERE, "結果_研究47_融資成長率.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
