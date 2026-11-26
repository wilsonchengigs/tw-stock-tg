"""研究 206：台美背離延伸（接研究 204／204b）
(a) 反向：加權 20 日 − 基準 20 日 ≥ +x（台股領先太多）→ 之後 5／20 日加權報酬，相對「同跌幅（同 tw20）但沒領先」對照，看會不會補跌
(b) 基準換 S&P／NDX／費半 SOX／台積電 ADR TSM：負向背離 ≤ −x 之後 5 日的同跌幅超額，哪個基準最有資訊
對照＝tw20 相差 ≤2% 且 |背離| < 5% 的日子；去叢集 20 天；
家族：(a) 4 基準 × 2 門檻(10/15%) × 2 天期(5/20)＝16（單尾＝補跌）；(b) 4 基準 × 3 門檻(10/15/20%) × 5 日＝12（單尾＝補漲）
環狀平移事件旗標 1,000 次、取最大 z
用法：python -X utf8 backtest/research_206_台美背離延伸.py
"""
import bisect
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402

NY = timezone(timedelta(hours=-5))
DAYS = [d for d in bt.DAYS if d >= "1998-01-01"]
i0 = bt.DAYS.index(DAYS[0])
TW = np.array(bt.PX[i0:])
N = len(DAYS)


def us_series(name):
    g = json.load(open(os.path.join(HERE, f"{name}.json")))
    rows = [(datetime.fromtimestamp(t, NY).strftime("%Y-%m-%d"), p) for t, p in zip(g["timestamp"], g["indicators"]["quote"][0]["close"]) if p]
    d, p = [x for x, _ in rows], [x for _, x in rows]
    return np.array([p[bisect.bisect_left(d, x) - 1] if bisect.bisect_left(d, x) > 0 else np.nan for x in DAYS])


def ret(a, k, h):
    return a[k + h] / a[k] - 1 if k + h < N else np.nan


tw20 = np.array([TW[k] / TW[k - 20] - 1 if k >= 20 else np.nan for k in range(N)])
F = {h: np.array([ret(TW, k, h) for k in range(N)]) for h in (5, 20)}
BENCH = {b: us_series(b) for b in ("GSPC", "NDX", "SOX", "TSM")}
GAP = {}
for b, u in BENCH.items():
    u20 = np.array([u[k] / u[k - 20] - 1 if k >= 20 else np.nan for k in range(N)])
    GAP[b] = tw20 - u20


def excess_series(b, h):
    """每天：fwd − 同 tw20（±2%）且 |背離|<5% 的對照平均"""
    g, f = GAP[b], F[h]
    okc = ~np.isnan(tw20) & ~np.isnan(g) & (np.abs(g) < 0.05) & ~np.isnan(f)
    order = np.argsort(tw20[okc])
    xs, ys = tw20[okc][order], f[okc][order]
    cs = np.r_[0, np.cumsum(ys)]
    out = np.full(N, np.nan)
    for k in range(N):
        if np.isnan(tw20[k]) or np.isnan(f[k]):
            continue
        lo, hi = np.searchsorted(xs, tw20[k] - 0.02), np.searchsorted(xs, tw20[k] + 0.02, "right")
        if hi - lo >= 20:
            out[k] = f[k] - (cs[hi] - cs[lo]) / (hi - lo)
    return out


EX = {(b, h): excess_series(b, h) for b in BENCH for h in (5, 20)}


def events(cond):
    out, last = [], -99
    for k in range(20, N):
        if cond[k] and k - last > 20:
            out.append(k)
            last = k
    return out


def family(tests, sign, seed):
    """tests：[(名稱, 超額序列, 事件索引)]；sign +1＝看補漲、−1＝看補跌；回傳 [(名稱, n, 平均, z, 家族 p)]"""
    valid = np.where(~np.isnan(EX[("GSPC", 20)]))[0]
    pre = []
    for name, x, ev in tests:
        fl = np.zeros(N, bool)
        fl[ev] = True
        pre.append((name, x[valid] * sign, fl[valid]))

    def z(x, fl):
        m = fl & ~np.isnan(x)
        if m.sum() < 3:
            return np.nan
        a = x[~np.isnan(x)]
        return (x[m].mean() - a.mean()) / (a.std() / np.sqrt(m.sum()))

    real = [z(x, fl) for _, x, fl in pre]
    rng = np.random.default_rng(seed)
    null = np.array([np.nanmax([z(x, np.roll(fl, s)) for _, x, fl in pre]) for s in rng.integers(100, len(valid) - 100, 1000)])
    res = []
    for (name, x, fl), zz in zip(pre, real):
        m = fl & ~np.isnan(x)
        res.append((name, int(m.sum()), np.nanmean(x[m]) * sign if m.sum() else np.nan, zz, np.mean(null >= zz) if not np.isnan(zz) else np.nan))
    return res


L = ["研究 206：台美背離延伸（同跌幅對照：tw20 ±2% 且 |背離|<5%）"]
L.append("現況 " + DAYS[-1] + "：加權 20 日 " + f"{tw20[-1]:+.1%}；" + "、".join(f"{b} 背離 {GAP[b][-1]:+.1%}" for b in BENCH))

# (a) 反向
tests = []
for b in BENCH:
    for th in (0.10, 0.15):
        ev = events(GAP[b] >= th)
        for h in (5, 20):
            tests.append((f"{b:4s} 領先 ≥{th:.0%} {h:2d} 日", EX[(b, h)], ev))
L.append("\n【(a) 台股領先 ≥x 之後：同跌幅超額（負＝補跌）】")
for name, n, m, zz, p in family(tests, -1, 2061):
    L.append(f"  {name}：{n:2d} 次 超額 {m:+.2%}  z(補跌) {zz:+.2f}  家族 p {p:.3f}")
# 原始報酬（GSPC）
for th in (0.10, 0.15):
    ev = events(GAP["GSPC"] >= th)
    for h in (5, 20):
        v = F[h][ev]
        v = v[~np.isnan(v)]
        L.append(f"  GSPC 領先 ≥{th:.0%} {h} 日原始：{len(v)} 次 平均 {v.mean():+.2%}（全部日 {np.nanmean(F[h]):+.2%}）正的比例 {np.mean(v > 0):.0%}；"
                 + "2013 後 " + (f"{np.mean([F[h][k] for k in ev if DAYS[k] >= '2013' and not np.isnan(F[h][k])]):+.2%}" if any(DAYS[k] >= '2013' for k in ev) else "無"))

# (b) 不同基準的負向背離
tests = []
for b in BENCH:
    for th in (0.10, 0.15, 0.20):
        tests.append((f"{b:4s} 落後 ≤-{th:.0%}  5 日", EX[(b, 5)], events(GAP[b] <= -th)))
L.append("\n【(b) 台股落後 ≤-x 之後 5 日：同跌幅超額（正＝補漲）】")
for name, n, m, zz, p in family(tests, +1, 2062):
    L.append(f"  {name}：{n:2d} 次 超額 {m:+.2%}  z {zz:+.2f}  家族 p {p:.3f}")
# 重疊：GSPC 10% 事件與其他基準 10% 事件
e_sp = set(events(GAP["GSPC"] <= -0.10))
for b in ("NDX", "SOX", "TSM"):
    eb = events(GAP[b] <= -0.10)
    near = sum(1 for k in eb if any(abs(k - j) <= 5 for j in e_sp))
    only = [k for k in eb if not any(abs(k - j) <= 5 for j in e_sp)]
    v = EX[(b, 5)][only]
    v = v[~np.isnan(v)]
    L.append(f"  {b} 落後 ≤-10% 共 {len(eb)} 次，其中 {near} 次與 S&P 版 ±5 天內重疊；不重疊 {len(v)} 次 5 日超額 "
             + (f"{v.mean():+.2%}、正的比例 {np.mean(v > 0):.0%}" if len(v) else "—"))
out = "\n".join(L) + "\n"
print(out)
open(os.path.join(HERE, "結果_研究206_台美背離延伸.txt"), "w", encoding="utf-8").write(out)
