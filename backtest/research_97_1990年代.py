"""研究 97：1990～1997 樣本外（核心均線規則沒看過這段）——含 1990 年崩盤（12,495 → 2,560）
資料：證交所 FMTQIK 1990-01-04～（backtest/taiex_1990_1997.csv；1990 年代有週六交易）
規則：進場 MA60×1.01、出場 MA80×0.975（無融資濾網，1990 年代沒有融資資料）；週末判斷、隔天收盤成交；2x＝2×(指數＋3% 配息)−1% 內扣；現金 1%
起點：均線可算的第一天（1990-05）；長抱也從同一天起算。另外假設「起點時已經在場」（最壞情況：崩盤前就持有）
用法：python -X utf8 backtest/research_97_1990年代.py
"""
import csv
import os
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
rows = [(r["date"], float(r["close"])) for r in csv.DictReader(open(os.path.join(HERE, "taiex_1990_1997.csv"), encoding="utf-8"))]
D = [d for d, _ in rows]
P = [p for _, p in rows]
N = len(P)
TD = 280  # 1990 年代含週六，一年約 280 個交易日
R1 = [0.0] + [P[i] / P[i - 1] - 1 + 0.03 / TD for i in range(1, N)]
R2 = [0.0] + [2 * R1[i] - 0.01 / TD for i in range(1, N)]
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


M60, M80 = sma(60), sma(80)


def run(start, end, kind="strat", start_on=False, bout=0.975):
    i0 = next(i for i, d in enumerate(D) if d >= start and M80[i] is not None)
    i1 = max(i for i, d in enumerate(D) if d <= end)
    eq = peak = 1.0
    mdd, on, pos, pend, trades = 0.0, start_on, start_on, None, 0
    for i in range(i0, i1 + 1):
        if i > i0:
            if kind == "1x":
                eq *= 1 + R1[i]
            elif kind == "2x":
                eq *= 1 + R2[i]
            else:
                eq *= 1 + (R2[i] if pos else RC)
        if pend is not None:
            eq *= 1 - 0.0025 * 2
            pos, pend = pend, None
            trades += 1
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if kind == "strat" and WE[i]:
            on = (not P[i] < M80[i] * bout) if on else (P[i] > M60[i] * 1.01)
            if on != pos:
                pend = on
    yrs = (i1 - i0) / TD
    return eq ** (1 / yrs) - 1, mdd, eq, trades, D[i0]


def main():
    L = ["研究 97：1990～1997 樣本外（核心均線規則；年化／最大回檔／期末倍數）"]
    for nm, s, e in (("1990-05～1997", "1990-01-01", "1997-12-31"), ("1990-05～1990-12（崩盤段）", "1990-01-01", "1990-12-31"),
                     ("1991～1997", "1991-01-01", "1997-12-31")):
        L.append(f"\n== {nm} ==")
        for lab, kw in (("策略（起點空手）", dict()), ("策略（起點已在場）", dict(start_on=True)), ("策略 舊出場 ×0.98", dict(bout=0.98)),
                        ("0050 型長抱 1x", dict(kind="1x")), ("正2 型長抱 2x", dict(kind="2x"))):
            c, m, eq, tr, d0 = run(s, e, **kw)
            L.append(f"  {lab:16s} 年化 {c:+6.1%}、最大回檔 {m:6.1%}、期末 {eq:.2f} 倍、交易 {tr} 次（起點 {d0}）")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究97_1990年代.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
