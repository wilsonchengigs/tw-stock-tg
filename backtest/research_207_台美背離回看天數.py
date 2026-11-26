"""研究 207：台美背離的回看天數穩健性（研究 204～205 用 20 日是事先挑的）
回看 W＝10／20／40／60 日；門檻用各自背離分布的下 1／2／3／5 百分位（不同窗長的背離大小不同，用分位才公平）
結果：之後 5 日加權報酬相對「同 W 日跌幅（±2%）且 |背離| < 該窗 30 百分位絕對值」對照的超額；去叢集 W 天
家族：4 窗 × 4 分位＝16，環狀平移 1,000 次；另列兩段（1998–2012／2013–2026）
用法：python -X utf8 backtest/research_207_台美背離回看天數.py
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_206_台美背離延伸 as R  # noqa: E402

TW, DAYS, N = R.TW, R.DAYS, R.N
US = R.BENCH["GSPC"]
f5 = R.F[5]


def build(W):
    twW = np.array([TW[k] / TW[k - W] - 1 if k >= W else np.nan for k in range(N)])
    usW = np.array([US[k] / US[k - W] - 1 if k >= W else np.nan for k in range(N)])
    gap = twW - usW
    calm = np.nanpercentile(np.abs(gap), 30)
    okc = ~np.isnan(twW) & ~np.isnan(gap) & (np.abs(gap) < calm) & ~np.isnan(f5)
    order = np.argsort(twW[okc])
    xs, ys = twW[okc][order], f5[okc][order]
    cs = np.r_[0, np.cumsum(ys)]
    ex = np.full(N, np.nan)
    for k in range(N):
        if np.isnan(twW[k]) or np.isnan(f5[k]):
            continue
        lo, hi = np.searchsorted(xs, twW[k] - 0.02), np.searchsorted(xs, twW[k] + 0.02, "right")
        if hi - lo >= 20:
            ex[k] = f5[k] - (cs[hi] - cs[lo]) / (hi - lo)
    return gap, ex


def events(cond, W):
    out, last = [], -99
    for k in range(W, N):
        if cond[k] and k - last > W:
            out.append(k)
            last = k
    return out


L = ["研究 207：台美背離回看天數（S&P；門檻＝各窗背離分布下 x 百分位；5 日同跌幅超額）"]
tests = []
for W in (10, 20, 40, 60):
    gap, ex = build(W)
    for q in (1, 2, 3, 5):
        th = np.nanpercentile(gap, q)
        ev = events(gap <= th, W)
        tests.append((W, q, th, ex, ev))
valid = np.arange(60, N - 5)


def z(x, fl):
    m = fl & ~np.isnan(x)
    if m.sum() < 3:
        return np.nan
    a = x[~np.isnan(x)]
    return (x[m].mean() - a.mean()) / (a.std() / np.sqrt(m.sum()))


pre = []
for W, q, th, ex, ev in tests:
    fl = np.zeros(N, bool)
    fl[ev] = True
    pre.append((ex[valid], fl[valid]))
real = [z(x, fl) for x, fl in pre]
rng = np.random.default_rng(207)
null = np.array([np.nanmax([z(x, np.roll(fl, s)) for x, fl in pre]) for s in rng.integers(100, len(valid) - 100, 1000)])
for (W, q, th, ex, ev), zz in zip(tests, real):
    fp = np.mean(null >= zz) if not np.isnan(zz) else np.nan
    v = ex[ev]
    ok = ~np.isnan(v)
    seg = []
    for lo, hi in (("1998", "2013"), ("2013", "2099")):
        s = [ex[k] for k in ev if lo <= DAYS[k] < hi and not np.isnan(ex[k])]
        seg.append(f"{np.mean(s):+.2%}（{len(s)}）" if s else "—")
    L.append(f"  W {W:2d} 下 {q:>3}%（門檻 {th:+.1%}）：{ok.sum():2d} 次 超額 {np.nanmean(v):+.2%} 正的比例 {np.mean(v[ok] > 0):.0%}  z {zz:+.2f} 家族 p {fp:.3f}  兩段 {seg[0]}／{seg[1]}")
gap20, _ = build(20)
L.append(f"\n參考：W 20 的 -10% 約等於第 {np.mean(gap20[~np.isnan(gap20)] <= -0.10) * 100:.1f} 百分位")
out = "\n".join(L) + "\n"
print(out)
open(os.path.join(HERE, "結果_研究207_台美背離回看天數.txt"), "w", encoding="utf-8").write(out)
