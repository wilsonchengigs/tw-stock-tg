"""研究 401：美債殖利率曲線（10 年 ^TNX − 3 個月 ^IRX，Yahoo，單位 %）對台股
狀態（用台股該日之前最後一個美國收盤）：倒掛＝利差 < 0；轉正＝過去 250 日內曾倒掛、現在利差 > 0（歷史上衰退常在轉正後）
(A) 各狀態之後 60／120／250 日加權報酬 vs 全部日（重疊樣本，平移安慰劑）
(B) v3 濾網：狀態成立時在場改 1x（或不進），全期／兩段／真實價；利差序列平移 200 次、家族最小 p
用法：python -X utf8 backtest/research_401_殖利率曲線.py
"""
import bisect
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_138_金字塔加碼與分段停損 as R138  # noqa: E402

V, bt, DAYS, N = R138.V, R138.bt, R138.DAYS, R138.N
NY = timezone(timedelta(hours=-5))


def load(f):
    g = json.load(open(os.path.join(HERE, f + ".json")))
    rows = [(datetime.fromtimestamp(t, NY).strftime("%Y-%m-%d"), p) for t, p in zip(g["timestamp"], g["indicators"]["quote"][0]["close"]) if p]
    d, p = [x for x, _ in rows], [x for _, x in rows]
    return np.array([p[bisect.bisect_left(d, x) - 1] if bisect.bisect_left(d, x) > 0 else np.nan for x in DAYS])


spread = load("TNX") - load("IRX")
inv = spread < 0
inv_recent = np.array([np.nanmin(spread[max(0, i - 250):i + 1]) < 0 if i > 0 else False for i in range(N)])
steep = inv_recent & (spread > 0)
PX = np.array(bt.PX)
F = {h: np.array([PX[i + h] / PX[i] - 1 if i + h < N else np.nan for i in range(N)]) for h in (60, 120, 250)}
start = next(i for i, d in enumerate(DAYS) if d >= "1998-01-01")
L = ["研究 401：美債殖利率曲線（10y − 3m）對台股", f"現況 {DAYS[-1]}：利差 {spread[-1]:+.2f}%（{'倒掛' if inv[-1] else '轉正期' if steep[-1] else '正常'}）", ""]
L.append("各狀態天數：倒掛 " + f"{int(inv[start:].sum())}、轉正期 {int(steep[start:].sum())}、全部 {N - start}")
rng = np.random.default_rng(401)
for name, flag in (("倒掛", inv), ("倒掛後轉正", steep)):
    for h in (60, 120, 250):
        f = F[h][start:]
        fl = flag[start:] & ~np.isnan(f)
        real = np.nanmean(f[fl]) - np.nanmean(f)
        null = [np.nanmean(f[np.roll(fl, int(s)) & ~np.isnan(f)]) - np.nanmean(f) for s in rng.integers(500, len(f) - 500, 300)]
        p = np.mean(np.array(null) <= real)
        L.append(f"  {name} {h:3d} 日：超額 {real:+.1%}（全部日 {np.nanmean(f):+.1%}）  平移 p（偏弱） {p:.2f}")


def perf(st):
    R138.ST = st
    out = []
    for a, b in V.PER:
        out.append(R138.run(R138.FULL, a, b)[:2])
    out.append(R138.run(R138.FULL, *V.REAL, real=True)[:2])
    return out


base_st = list(R138.ST)
fmt = lambda p: "  ".join(f"{c:5.1%}／{m:6.1%}" for c, m in p)  # noqa: E731
L.append("\n【v3 濾網】（全期 2002～｜2002–2012｜2013～｜真實價）")
L.append(f"現行：{fmt(perf(base_st))}")


def sizer_of(flag, low):
    def f(i, on, px2, ctx):
        return (low / 2 if flag[i] else 1.0) if on else 0.0
    return f


for name, flag in (("倒掛", inv), ("轉正期", steep)):
    for low in (1.0, 0.0):
        R138.ST = base_st
        res = []
        for a, b in V.PER:
            res.append(R138.run(sizer_of(flag, low), a, b)[:2])
        res.append(R138.run(sizer_of(flag, low), *V.REAL, real=True)[:2])
        null = [R138.run(sizer_of(np.roll(flag, int(s)), low), *V.PER[0])[0] for s in rng.integers(500, N - 500, 200)]
        p = np.mean(np.array(null) >= res[0][0])
        L.append(f"{name} → {'1x' if low else '空手'}：{fmt(res)}  平移 p {p:.2f}")
R138.ST = base_st
out = "\n".join(L)
print(out)
open(os.path.join(HERE, "結果_研究401_殖利率曲線.txt"), "w", encoding="utf-8").write(out + "\n")
