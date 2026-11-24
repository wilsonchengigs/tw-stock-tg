"""研究 35：台指選 P/C 提早進場的穩健性（研究 32 延伸）
變形：百分位回看 120／250／500 日；改用 P/C 成交量比；固定門檻（未平倉比 ≥ 110／120／130／140%）；
每個變形都跑 100 次循環平移安慰劑，報告 p 值。規則其餘同研究 32（10 日、反彈 3%、最多 13 週、早進 1x 與 2x）
用法：python -X utf8 backtest/research_35_PC穩健性.py
"""
import csv
import importlib.util
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r32", os.path.join(HERE, "research_32_PC比提早進場.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
N = R.N
rows = list(csv.DictReader(open(os.path.join(HERE, "pcratio_daily.csv"), encoding="utf-8")))
OI = R.R31.align_tw({r["date"]: float(r["oi_ratio"]) for r in rows if r["oi_ratio"]})
VOL = R.R31.align_tw({r["date"]: float(r["vol_ratio"]) for r in rows if r["vol_ratio"]})


def pct_series(arr, n):
    return [R.R31.pct_rank(arr, i, n) if i >= 150 else None for i in range(N)]


def abs_series(arr, th):
    # 轉成「是否 ≥ 門檻」的 0/1，搭配 q=0.5 使用
    return [None if arr[i] is None else (1.0 if arr[i] >= th else 0.0) for i in range(N)]


def test(pr, q, lev, rng, n_sh=100):
    R.PR = pr
    real = R.ev(q=q, L=10, c=0.03, T=13, lev_early=lev)
    valid = [i for i in range(N) if pr[i] is not None]
    i0 = valid[0]
    seg = pr[i0:]
    M = len(seg)
    sims = []
    for _ in range(n_sh):
        k = rng.randrange(250, M - 250)
        R.PR = [None] * i0 + seg[k:] + seg[:k]
        sims.append(R.run("2002-01-01", "2026-12-31", q=q, L=10, c=0.03, T=13, lev_early=lev)[0])
    R.PR = pr
    p = (sum(1 for x in sims if x >= real[0][0][0]) + 1) / (n_sh + 1)
    return real, p, sorted(sims)[n_sh // 2]


def main():
    rng = random.Random(11)
    base = R.ev()
    L = ["研究 35：P/C 提早進場穩健性（全期 2002- | 前段 | 後段 | 真實；p＝100 次平移安慰劑）", f"現行 {R.fmt(*base)}"]
    variants = [("未平倉 百分位 120 日 ≥95%", pct_series(OI, 120), 0.95),
                ("未平倉 百分位 250 日 ≥95%（研究 32）", pct_series(OI, 250), 0.95),
                ("未平倉 百分位 500 日 ≥95%", pct_series(OI, 500), 0.95),
                ("成交量比 百分位 250 日 ≥95%", pct_series(VOL, 250), 0.95),
                ("成交量比 百分位 250 日 ≥99%", pct_series(VOL, 250), 0.99)]
    for th in (110, 120, 130, 140):
        variants.append((f"未平倉 固定門檻 ≥{th}%", abs_series(OI, th), 0.5))
    for nm, pr, q in variants:
        for lev in (1.0, 2.0):
            (rs, rr), p, med = test(pr, q, lev, rng)
            L.append(f"{nm:28s} 早進{lev:.0f}x {R.fmt(rs, rr)} | 平移中位 {med:.1%} | p {p:.2f}")
            print(L[-1], flush=True)
    open(os.path.join(HERE, "結果_研究35_PC穩健性.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
