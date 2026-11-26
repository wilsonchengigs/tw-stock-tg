"""研究 210：券資比（融券張數 ÷ 融資張數，上市，FinMind TaiwanStockTotalMarginPurchaseShortSale 2001～）
訊號（每天，用當天收盤後公布的數字 → D 收盤後才知道，報酬從 D 收盤起算，實際 D+1 才能動作）：
  R 原始券資比的 250 日分位 ≥90／≥95／≤10／≤5
  S 季節調整：券資比 ÷ 前 3 年同月份平均（停券期 4～8 月券資比會機械性下降），再取 250 日分位 ≥90／≤10
  C 融券張數 20 日變化 ≥+50%／≤-30%
結果：之後 5／20／60 日加權報酬 − 全部日平均；家族：10 訊號 × 3 天期＝30，環狀平移 1,000 次、最大 |z|（雙尾）
兩段 2001–2013／2014–2026；現況
用法：python -X utf8 backtest/research_210_券資比.py
"""
import csv
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402

rows = list(csv.DictReader(open(os.path.join(HERE, "short_margin_daily.csv"))))
px = dict(zip(bt.DAYS, bt.PX))
rows = [r for r in rows if r["date"] in px]
D = [r["date"] for r in rows]
N = len(D)
TW = np.array([px[d] for d in D])
ms = np.array([float(r["margin_shares"]) for r in rows])
ss = np.array([float(r["short_shares"]) for r in rows])
ratio = ss / ms
F = {h: np.array([TW[k + h] / TW[k] - 1 if k + h < N else np.nan for k in range(N)]) for h in (5, 20, 60)}


def pct(x, w=250):
    out = np.full(N, np.nan)
    for k in range(w, N):
        out[k] = np.mean(x[k - w:k] < x[k])
    return out


ym = np.array([d[:7] for d in D])
mon = np.array([int(d[5:7]) for d in D])
yr = np.array([int(d[:4]) for d in D])
mavg = {}
for y in set(yr):
    for m in range(1, 13):
        sel = (yr == y) & (mon == m)
        if sel.any():
            mavg[(y, m)] = ratio[sel].mean()
adj = np.full(N, np.nan)
for k in range(N):
    prev = [mavg.get((yr[k] - i, mon[k])) for i in (1, 2, 3)]
    prev = [p for p in prev if p]
    if len(prev) == 3:
        adj[k] = ratio[k] / np.mean(prev)
pr, pa = pct(ratio), pct(adj)
ch20 = np.r_[np.full(20, np.nan), ss[20:] / ss[:-20] - 1]
SIG = {
    "券資比分位≥90": pr >= 0.90, "券資比分位≥95": pr >= 0.95, "券資比分位≤10": pr <= 0.10, "券資比分位≤5": pr <= 0.05,
    "季調券資比≥90": pa >= 0.90, "季調券資比≥95": pa >= 0.95, "季調券資比≤10": pa <= 0.10, "季調券資比≤5": pa <= 0.05,
    "融券20日≥+50%": ch20 >= 0.5, "融券20日≤-30%": ch20 <= -0.3,
}
SIG = {k: np.nan_to_num(v, nan=0).astype(bool) for k, v in SIG.items()}
start = 250 + 800  # 季調需要 3 年
valid = np.arange(start, N)


def z(x, fl):
    m = fl & ~np.isnan(x)
    if m.sum() < 10:
        return np.nan
    a = x[~np.isnan(x)]
    return (x[m].mean() - a.mean()) / (a.std() / np.sqrt(m.sum()))


pre = [(name, h, F[h][valid], SIG[name][valid]) for name in SIG for h in (5, 20, 60)]
real = [z(x, fl) for *_, x, fl in pre]
rng = np.random.default_rng(210)
null = np.array([np.nanmax([abs(z(x, np.roll(fl, s))) for *_, x, fl in pre]) for s in rng.integers(250, len(valid) - 250, 1000)])
L = [f"研究 210：券資比（{D[start]}～{D[-1]}；超額＝訊號日之後報酬 − 全部日平均；雙尾家族 30 檢定）",
     f"現況 {D[-1]}：券資比 {ratio[-1]:.2%}（250 日第 {pr[-1] * 100:.0f} 分位）、季調 {adj[-1]:.2f}（第 {pa[-1] * 100:.0f} 分位）、融券 20 日 {ch20[-1]:+.0%}", ""]
Dv = np.array(D)
for (name, h, x, fl), zz in zip(pre, real):
    m = SIG[name] & (np.arange(N) >= start) & ~np.isnan(F[h])
    base = np.nanmean(F[h][start:])
    s1 = np.nanmean(F[h][m & (Dv < "2014")]) - base
    s2 = np.nanmean(F[h][m & (Dv >= "2014")]) - base
    p = np.mean(null >= abs(zz)) if not np.isnan(zz) else np.nan
    L.append(f"  {name:12s} {h:2d} 日：{m.sum():4d} 天 超額 {np.nanmean(F[h][m]) - base:+.2%}  z {zz:+.2f} 家族 p {p:.3f}  兩段 {s1:+.2%}／{s2:+.2%}")
out = "\n".join(L) + "\n"
print(out)
open(os.path.join(HERE, "結果_研究210_券資比.txt"), "w", encoding="utf-8").write(out)
