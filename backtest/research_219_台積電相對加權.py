"""研究 219：台積電（2330，Yahoo adjclose，2000～）20 日報酬 − 加權 20 日報酬（gap）之後 5 日加權報酬
台積電約占加權 3～4 成：台積電落後加權 ≤-x（權值股沒跟上）→ 補漲？台積電領先加權 ≥+x（權值股獨強、其他股沒跟）→ 回落？
用同一天收盤；5 日報酬從 D 收盤算（與 204 一致）；對照同 208：tw20 ±2% 且 |gap| < 5% 的同跌幅對照，去叢集 20 天
家族：落後 4 門檻（4／6／8／10%）、領先 4 門檻，各自 1,000 次平移；兩段（1998–2013／2013–）；現況
用法：python -X utf8 backtest/research_219_台積電相對加權.py
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

DAYS, N, f5, tw20 = R.DAYS, R.N, R.F[5], R.tw20

g = json.load(open(os.path.join(HERE, "2330.TW.json")))
ac = g["indicators"]["adjclose"][0]["adjclose"]
rows = [(datetime.fromtimestamp(t, timezone(timedelta(hours=8))).strftime("%Y-%m-%d"), p) for t, p in zip(g["timestamp"], ac) if p]
d, p = [x for x, _ in rows], [x for _, x in rows]
S = np.array([p[bisect.bisect_right(d, x) - 1] if bisect.bisect_right(d, x) > 0 and x >= d[0] else np.nan for x in DAYS])
s20 = np.array([S[i] / S[i - 20] - 1 if i >= 20 and S[i - 20] > 0 else np.nan for i in range(N)])
GAP = s20 - tw20

okc = ~np.isnan(GAP) & (np.abs(GAP) < 0.05) & ~np.isnan(f5) & ~np.isnan(tw20)
order = np.argsort(tw20[okc])
xs, cs = tw20[okc][order], np.r_[0, np.cumsum(f5[okc][order])]
EX = np.full(N, np.nan)
for k in range(N):
    if np.isnan(tw20[k]) or np.isnan(f5[k]):
        continue
    lo, hi = np.searchsorted(xs, tw20[k] - 0.02), np.searchsorted(xs, tw20[k] + 0.02, "right")
    if hi - lo >= 20:
        EX[k] = f5[k] - (cs[hi] - cs[lo]) / (hi - lo)

first = next(i for i in range(N) if not np.isnan(GAP[i]))
L = [f"研究 219：台積電相對加權（{DAYS[first]}～{DAYS[-1]}；超額＝5 日加權報酬 − 同跌幅對照）",
     f"現況 {DAYS[-1]}：台積電 20 日 {s20[-1]:+.1%}、加權 20 日 {tw20[-1]:+.1%}、gap {GAP[-1]:+.1%}"]
for label, sign, cond in (("台積電落後 ≤-", +1, lambda th: GAP <= -th), ("台積電領先 ≥+", -1, lambda th: GAP >= th)):
    tests = [(f"{label}{th:.0%}", EX, R.events(cond(th))) for th in (0.04, 0.06, 0.08, 0.10)]
    L.append("")
    for name, n, m, zz, pv in R.family(tests, sign, 219 + sign):
        th = float(name.split("%")[0][-2:].strip("-+≥≤ ")) / 100
        ev = R.events(cond(th))
        seg = []
        for lo, hi in (("1998", "2013"), ("2013", "2099")):
            v = [EX[i] for i in ev if lo <= DAYS[i] < hi and not np.isnan(EX[i])]
            seg.append(f"{np.mean(v):+.2%}（{len(v)}）" if v else "無")
        L.append(f"  {name}：{n:2d} 次 超額 {m:+.2%}  z {zz:+.2f}  家族 p {pv:.3f} | 兩段 {seg[0]}／{seg[1]}（正向＝{'補漲' if sign > 0 else '回落'}預期為 {'+' if sign > 0 else '-'}）")
out = "\n".join(L) + "\n"
print(out)
open(os.path.join(HERE, "結果_研究219_台積電相對加權.txt"), "w", encoding="utf-8").write(out)
