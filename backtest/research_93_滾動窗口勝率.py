"""研究 93：滾動窗口勝率——從任一天開始持有 1／3／5／10 年，v3 勝過 0050 長抱、00631L 長抱的機率與最差情況
2002～2026；2015-09 起真實價格（同研究 87 的串接方式）
用法：python -X utf8 backtest/research_93_滾動窗口勝率.py
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("v3", os.path.join(HERE, "strategy_v3.py"))
V = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V)
bt, DAYS, N = V.bt, V.DAYS, V.N


def spliced(kind):
    i0 = next(i for i, d in enumerate(DAYS) if d >= "2002-01-01")
    j0 = next(i for i, d in enumerate(DAYS) if d >= "2015-09-01")
    if kind == "v3":
        _, _, a = V.run("2002-01-01", "2026-12-31", curve=True)
        _, _, b = V.run("2015-09-01", "2026-12-31", real=True, curve=True)
    else:
        r_sim = bt.R1 if kind == "0050" else bt.R2
        r_real = V.R1R if kind == "0050" else V.R2R
        a, eq = [1.0], 1.0
        for i in range(i0 + 1, N):
            eq *= 1 + r_sim[i]
            a.append(eq)
        b, eq = [1.0], 1.0
        for i in range(j0 + 1, N):
            eq *= 1 + r_real[i]
            b.append(eq)
    cut = j0 - i0
    return a[:cut] + [a[cut - 1] * x for x in b[1:]]


def main():
    s = {k: spliced(k) for k in ("v3", "0050", "00631L")}
    n = min(len(v) for v in s.values())
    L = ["研究 93：滾動窗口（每天起算；年化報酬）"]
    for yrs in (1, 3, 5, 10):
        h = int(yrs * 245)
        rows = []
        for k in range(0, n - h):
            r = {nm: (c[k + h] / c[k]) ** (1 / yrs) - 1 for nm, c in s.items()}
            rows.append(r)
        m = len(rows)
        win50 = sum(r["v3"] > r["0050"] for r in rows) / m
        win2 = sum(r["v3"] > r["00631L"] for r in rows) / m
        neg = sum(r["v3"] < 0 for r in rows) / m
        worst = min(r["v3"] for r in rows)
        med = sorted(r["v3"] for r in rows)[m // 2]
        w50 = min(r["0050"] for r in rows)
        w2 = min(r["00631L"] for r in rows)
        L.append(f"{yrs:2d} 年：v3 勝 0050 {win50:.0%}、勝 00631L 長抱 {win2:.0%}｜v3 年化中位 {med:+.1%}、最差 {worst:+.1%}、虧損機率 {neg:.0%}｜"
                 f"最差：0050 {w50:+.1%}、00631L {w2:+.1%}（{m} 個窗口）")
        print(L[-1], flush=True)
    out = "\n".join(L) + "\n"
    open(os.path.join(HERE, "結果_研究93_滾動窗口勝率.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
