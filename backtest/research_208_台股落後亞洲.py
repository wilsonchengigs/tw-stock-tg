"""研究 208：台股落後亞洲市場（KOSPI ^KS11、日經 ^N225、恆生 ^HSI；Yahoo 2026-11-26 抓）20 日 ≥x 後會不會補漲
亞洲收盤時間與台股相近（同一天，晚 0.5～2.5 小時），用同一天收盤；實際操作 D+1 開盤進，這裡 5 日報酬從 D 收盤算（與 204 一致）
對照同 204b：tw20 ±2% 且 |背離| < 5%；去叢集 20 天；門檻 6／8／10／12%；家族 3 指數 × 4 門檻＝12，平移 1,000 次
另：與 S&P 版（≤-10%）±5 天不重疊的事件；以及「同時落後 S&P 與亞洲」
用法：python -X utf8 backtest/research_208_台股落後亞洲.py
"""
import bisect
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_206_台美背離延伸 as R  # noqa: E402

TW, DAYS, N, f5, tw20 = R.TW, R.DAYS, R.N, R.F[5], R.tw20


def asia(name, tz):
    g = json.load(open(os.path.join(HERE, f"{name}.json")))
    rows = [(datetime.fromtimestamp(t, timezone(timedelta(hours=tz))).strftime("%Y-%m-%d"), p)
            for t, p in zip(g["timestamp"], g["indicators"]["quote"][0]["close"]) if p]
    d, p = [x for x, _ in rows], [x for _, x in rows]
    return np.array([p[bisect.bisect_right(d, x) - 1] if bisect.bisect_right(d, x) > 0 else np.nan for x in DAYS])


A = {"KOSPI": asia("KS11", 9), "日經": asia("N225", 9), "恆生": asia("HSI", 8)}
GAP = {}
for k, u in A.items():
    u20 = np.array([u[i] / u[i - 20] - 1 if i >= 20 and u[i - 20] > 0 else np.nan for i in range(N)])
    GAP[k] = tw20 - u20
GAP["S&P"] = R.GAP["GSPC"]


def excess(gap):
    okc = ~np.isnan(gap) & (np.abs(gap) < 0.05) & ~np.isnan(f5) & ~np.isnan(tw20)
    order = np.argsort(tw20[okc])
    xs, cs = tw20[okc][order], np.r_[0, np.cumsum(f5[okc][order])]
    out = np.full(N, np.nan)
    for k in range(N):
        if np.isnan(tw20[k]) or np.isnan(f5[k]):
            continue
        lo, hi = np.searchsorted(xs, tw20[k] - 0.02), np.searchsorted(xs, tw20[k] + 0.02, "right")
        if hi - lo >= 20:
            out[k] = f5[k] - (cs[hi] - cs[lo]) / (hi - lo)
    return out


EXS = {k: excess(g) for k, g in GAP.items()}
L = ["研究 208：台股落後亞洲 20 日 ≥x 之後 5 日（同跌幅超額）",
     "現況 " + DAYS[-1] + "：" + "、".join(f"{k} 背離 {g[-1]:+.1%}" for k, g in GAP.items())]
tests = []
for k in ("KOSPI", "日經", "恆生"):
    for th in (0.06, 0.08, 0.10, 0.12):
        tests.append((f"{k} 落後 ≤-{th:.0%}", EXS[k], R.events(GAP[k] <= -th)))
for name, n, m, zz, p in R.family(tests, +1, 208):
    L.append(f"  {name}：{n:2d} 次 超額 {m:+.2%}  z {zz:+.2f}  家族 p {p:.3f}")
e_sp = R.events(GAP["S&P"] <= -0.10)
L.append("\n【與 S&P ≤-10% 不重疊（±5 天）的事件】")
for k in ("KOSPI", "日經", "恆生"):
    for th in (0.08, 0.10):
        ev = R.events(GAP[k] <= -th)
        only = [i for i in ev if not any(abs(i - j) <= 5 for j in e_sp)]
        v = EXS[k][only]
        v = v[~np.isnan(v)]
        raw = f5[only]
        raw = raw[~np.isnan(raw)]
        L.append(f"  {k} ≤-{th:.0%}：{len(ev)} 次中不重疊 {len(v)} 次 超額 {v.mean():+.2%}、原始 {raw.mean():+.2%}、正的比例 {np.mean(raw > 0):.0%}" if len(v) else f"  {k} ≤-{th:.0%}：無")
L.append("\n【同時落後 S&P ≤-x 且 亞洲平均 ≤-x】")
asia_avg = np.nanmean(np.vstack([GAP[k] for k in ("KOSPI", "日經", "恆生")]), axis=0)
for th in (0.06, 0.08, 0.10):
    ev = R.events((GAP["S&P"] <= -th) & (asia_avg <= -th))
    v = EXS["S&P"][ev]
    v = v[~np.isnan(v)]
    seg = [np.nanmean([EXS["S&P"][i] for i in ev if lo <= DAYS[i] < hi]) for lo, hi in (("1998", "2013"), ("2013", "2099"))]
    L.append(f"  ≤-{th:.0%}：{len(ev)} 次 超額 {v.mean():+.2%}、原始 {np.nanmean(f5[ev]):+.2%}、正的比例 {np.nanmean(f5[ev] > 0):.0%}  兩段 {seg[0]:+.2%}／{seg[1]:+.2%}")
    ev2 = R.events((GAP["S&P"] <= -th) & (asia_avg > -th / 2))
    v2 = EXS["S&P"][ev2]
    v2 = v2[~np.isnan(v2)]
    L.append(f"     對比 落後 S&P 但亞洲沒落後（> -{th / 2:.0%}）：{len(ev2)} 次 超額 {v2.mean() if len(v2) else np.nan:+.2%}")
out = "\n".join(L) + "\n"
print(out)
open(os.path.join(HERE, "結果_研究208_台股落後亞洲.txt"), "w", encoding="utf-8").write(out)
