"""研究 213：市場廣度（breadth_daily.csv，上市個股收盤價自算，2010～）
欄位：AD10＝近 10 日上漲家數占比、M50／M200＝站上 50／200 日均線的家數占比、NHNL＝（60 日新高−新低）家數占比
訊號（每天，用當天收盤算出 → 報酬從當天收盤起算）：
  M50 ≤5%／≤10%（洗盤到底）、M50 ≥85%／≥95%（過熱）、M200 ≤15%／≤25%、M200 ≥80%／≥90%
  NHNL ≤ 自身 250 日 5 分位（恐慌）、NHNL ≥ 95 分位（強勢）、AD10 ≤ 20%／≥ 80%
結果：之後 5／20／60 日加權報酬 − 全部日平均；家族 12 訊號 × 3 天期＝36，環狀平移 1,000 次、最大 |z|（雙尾）
兩段（對半分）；現況
用法：python -X utf8 backtest/research_213_市場廣度.py
"""
import csv
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402

px = dict(zip(bt.DAYS, bt.PX))
rows = [r for r in csv.DictReader(open(os.path.join(HERE, "breadth_daily.csv"))) if r["M50"] and r["date"] in px]
D = [r["date"] for r in rows]
N = len(D)
TW = np.array([px[d] for d in D])
col = {c: np.array([float(r[c]) if r[c] else np.nan for r in rows]) for c in ("AD10", "M50", "M200", "NHNL")}
F = {h: np.array([TW[k + h] / TW[k] - 1 if k + h < N else np.nan for k in range(N)]) for h in (5, 20, 60)}


def pct(x, w=250):
    out = np.full(N, np.nan)
    for k in range(w, N):
        out[k] = np.mean(x[k - w:k] < x[k])
    return out


pn = pct(col["NHNL"])
SIG = {
    "M50≤5%": col["M50"] <= 0.05, "M50≤10%": col["M50"] <= 0.10,
    "M50≥85%": col["M50"] >= 0.85, "M50≥95%": col["M50"] >= 0.95,
    "M200≤15%": col["M200"] <= 0.15, "M200≤25%": col["M200"] <= 0.25,
    "M200≥80%": col["M200"] >= 0.80, "M200≥90%": col["M200"] >= 0.90,
    "NHNL≤5分位": pn <= 0.05, "NHNL≥95分位": pn >= 0.95,
    "AD10≤20%": col["AD10"] <= 0.20, "AD10≥80%": col["AD10"] >= 0.80,
}
SIG = {k: np.nan_to_num(v, nan=0).astype(bool) for k, v in SIG.items()}
start = 250
valid = np.arange(start, N)
mid = (start + N) // 2


def z(x, fl):
    m = fl & ~np.isnan(x)
    if m.sum() < 10:
        return np.nan
    a = x[~np.isnan(x)]
    return (x[m].mean() - a.mean()) / (a.std() / np.sqrt(m.sum()))


pre = [(name, h, F[h][valid], SIG[name][valid]) for name in SIG for h in (5, 20, 60)]
real = [z(x, fl) for *_, x, fl in pre]
rng = np.random.default_rng(213)
null = np.array([np.nanmax([abs(z(x, np.roll(fl, s))) for *_, x, fl in pre]) for s in rng.integers(250, len(valid) - 250, 1000)])
L = [f"研究 213：市場廣度（{D[start]}～{D[-1]}；超額＝訊號日之後報酬 − 全部日平均；雙尾家族 {len(pre)} 檢定）",
     f"現況 {D[-1]}：M50 {col['M50'][-1]:.1%}、M200 {col['M200'][-1]:.1%}、NHNL {col['NHNL'][-1]:+.1%}（250 日第 {pn[-1] * 100:.0f} 分位）、AD10 {col['AD10'][-1]:.1%}", ""]
Dv = np.array(D)
for (name, h, x, fl), zz in zip(pre, real):
    m = fl & ~np.isnan(x)
    a = x[~np.isnan(x)]
    ex = x[m].mean() - a.mean() if m.sum() else np.nan
    first = m & (np.arange(len(x)) + start < mid)
    second = m & (np.arange(len(x)) + start >= mid)
    f1 = x[first].mean() - a.mean() if first.sum() else np.nan
    f2 = x[second].mean() - a.mean() if second.sum() else np.nan
    p = np.mean(null >= abs(zz)) if not np.isnan(zz) else np.nan
    L.append(f"{name:<12} {h:>2}日 n={m.sum():>4} 超額 {ex:+.2%} z={zz:+.2f} 家族p={p:.3f} | 前半 {f1:+.2%}（{first.sum()}）後半 {f2:+.2%}（{second.sum()}）")
out = os.path.join(HERE, "結果_研究213_市場廣度.txt")
open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
print("\n".join(L))
