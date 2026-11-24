"""研究 85（待研究 12）：融資過熱的其他定義，與現行「融資÷指數 偏離 250 日均 > 17.5%」比較
A z 分數：(比值 − 250 日均) ÷ 250 日標準差 > z（z 1.5～3）
B 融資÷成交金額（20 日均）的 250 日偏離 > y（散戶槓桿相對市場熱度）
C 融資÷台指期全月份未平倉口數 的 250 日偏離 > y
D 現行定義＋A 或 B 任一（並用）
都是「出場且不進」；出場 2.5%；全期 2002- | 前段 | 後段 | 真實；序列平移 100 次安慰劑
用法：python -X utf8 backtest/research_85_融資過熱定義.py
"""
import csv
import importlib.util
import itertools
import math
import os
import random
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r38", os.path.join(HERE, "research_38_融資過熱安慰劑.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
R3, N = R.R, R.N
bt = R3.bt
DAYS = bt.DAYS
M = R3.M
RATIO = R3.RATIO

amt = {r["date"]: float(r["amount"]) for r in csv.DictReader(open(os.path.join(HERE, "turnover_daily.csv"), encoding="utf-8")) if r["amount"]}
oi = defaultdict(float)
for r in csv.DictReader(open(os.path.join(HERE, "tx_daily.csv"), encoding="utf-8")):
    try:
        oi[r["date"]] += float(r["oi"] or 0)
    except ValueError:
        pass
AMT = [amt.get(d) for d in DAYS]
OI = [oi.get(d) or None for d in DAYS]


def roll_mean(x, n):
    out, s, q = [None] * N, 0.0, []
    for i, v in enumerate(x):
        if v is None:
            out[i] = None
            continue
        q.append(v)
        s += v
        if len(q) > n:
            s -= q.pop(0)
        if len(q) == n:
            out[i] = s / n
    return out


def dev_series(x, n=250):
    m = roll_mean(x, n)
    return [None if (x[i] is None or m[i] is None) else x[i] / m[i] - 1 for i in range(N)]


def z_series(x, n=250):
    out = [None] * N
    for i in range(n, N):
        w = [v for v in x[i - n + 1:i + 1] if v is not None]
        if x[i] is None or len(w) < n * 0.8:
            continue
        mu = sum(w) / len(w)
        sd = math.sqrt(sum((v - mu) ** 2 for v in w) / len(w))
        out[i] = (x[i] - mu) / sd if sd else 0.0
    return out


AMT20 = roll_mean(AMT, 20)
M_AMT = [None if (M[i] is None or AMT20[i] is None) else M[i] / AMT20[i] for i in range(N)]
M_OI = [None if (M[i] is None or OI[i] is None) else M[i] / OI[i] for i in range(N)]
CUR = R.DEV
SER = {"z": z_series(RATIO), "amt": dev_series(M_AMT), "oi": dev_series(M_OI)}


def kw(flag):
    return dict(entry_ok=lambda i: not flag[i], force_exit=lambda i: flag[i], bout=0.025)


def ev(flag):
    rs = [R3.run(a, b, **kw(flag)) for a, b in (("2002-01-01", "2026-12-31"), ("2002-01-01", "2012-12-31"), ("2013-01-01", "2026-12-31"))]
    rr = R3.run("2015-09-01", "2026-12-31", r2=R.R2R, **kw(flag))
    return rs, rr


def shifted(x, rng):
    i0 = next(i for i in range(N) if x[i] is not None)
    seg = x[i0:]
    k = rng.randrange(250, len(seg) - 250)
    return [None] * i0 + seg[k:] + seg[:k]


def main():
    rng = random.Random(85)
    L = ["研究 85：融資過熱的其他定義（全期 2002- | 前段 | 後段 | 真實；p＝100 次平移）"]

    def line(nm, flag, raw=None, fn=None):
        rs, rr = ev(flag)
        p = ""
        if raw is not None:
            sims = [R3.run("2002-01-01", "2026-12-31", **kw([fn(v) for v in shifted(raw, rng)]))["cagr"] for _ in range(100)]
            p = f" | p {(sum(x >= rs[0]['cagr'] for x in sims) + 1) / 101:.2f}"
        L.append(f"{nm:30s} " + " | ".join(f"{r['cagr']:.1%}/{r['mdd']:.1%}" for r in rs) + f" | 真實 {rr['cagr']:.1%}/{rr['mdd']:.1%}{p}")
        print(L[-1], flush=True)

    line("無融資濾網", [False] * N)
    cur_fn = lambda v: v is not None and v > 0.175  # noqa: E731
    line("現行：融資÷指數 偏離 > 17.5%", [cur_fn(v) for v in CUR], CUR, cur_fn)
    for z in (1.5, 2.0, 2.5, 3.0):
        fn = (lambda z: lambda v: v is not None and v > z)(z)
        line(f"A z 分數 > {z}", [fn(v) for v in SER["z"]], SER["z"], fn)
    for key, nm in (("amt", "B 融資÷成交金額"), ("oi", "C 融資÷台指期未平倉")):
        for y in (0.2, 0.3, 0.5):
            fn = (lambda y: lambda v: v is not None and v > y)(y)
            line(f"{nm} 偏離 > {y:.0%}", [fn(v) for v in SER[key]], SER[key], fn)
    for z, y in itertools.product((2.0, 2.5), (0.3,)):
        flag = [cur_fn(CUR[i]) or (SER["z"][i] is not None and SER["z"][i] > z) for i in range(N)]
        line(f"D 現行 或 z > {z}", flag)
        flag = [cur_fn(CUR[i]) or (SER["amt"][i] is not None and SER["amt"][i] > y) for i in range(N)]
        line(f"D 現行 或 融資÷成交金額 > {y:.0%}", flag)
    open(os.path.join(HERE, "結果_研究85_融資過熱定義.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
