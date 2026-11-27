"""研究 421：主策略核心規則套台積電（2330.TW Yahoo 還原價，2000～）vs 加權；以及週報酬 VR(26)
用研究 217 的 sim／bh 與研究 217 trend_stats 的做法
用法：python -X utf8 backtest/research_421_台積電趨勢.py
"""
import io
import contextlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
with contextlib.redirect_stdout(io.StringIO()):
    import research_217_主策略套亞洲市場 as R  # noqa: E402

g = json.load(open(os.path.join(HERE, "2330.TW.json")))
adj = g["indicators"].get("adjclose", [{}])[0].get("adjclose") or g["indicators"]["quote"][0]["close"]
rows = {}
for t, p in zip(g["timestamp"], adj):
    if p:
        rows[datetime.fromtimestamp(t, timezone(timedelta(hours=8))).strftime("%Y-%m-%d")] = p
TD = sorted(rows)
TP = np.array([rows[d] for d in TD])
MK = {"加權": R.MK["加權"], "台積電": (TD, TP)}
L = ["研究 421：主策略核心規則套台積電 vs 加權（年化／最大回檔；2001～）", ""]
SEG = (("2001～2026", "2001-01-01", "2026-12-31"), ("2001～2012", "2001-01-01", "2012-12-31"), ("2013～2026", "2013-01-01", "2026-12-31"))
for name, (D, P) in MK.items():
    L.append(f"【{name}】")
    for lab, a, b in SEG:
        s = R.sim(D, P, start=a, end=b)
        b1 = R.bh(D, P, 1, a, b)
        L.append(f"  {lab}：規則 2x {s[0]:6.1%}／{s[1]:6.1%}｜買進持有 1x {b1[0]:6.1%}／{b1[1]:6.1%}")
    wk = [datetime.fromisoformat(x).isocalendar()[:2] for x in D]
    idx = [k for k in range(len(D) - 1) if wk[k + 1] != wk[k] and D[k] >= "2001"]
    w = np.array([P[k] for k in idx])
    r = np.diff(np.log(w))
    vr = {}
    for q in (12, 26):
        rq = np.array([r[i:i + q].sum() for i in range(len(r) - q + 1)])
        vr[q] = rq.var() / (q * r.var())
    L.append(f"  VR(12) {vr[12]:.2f}、VR(26) {vr[26]:.2f}")
out = "\n".join(L)
print(out)
open(os.path.join(HERE, "結果_研究421_台積電趨勢.txt"), "w", encoding="utf-8").write(out + "\n")
