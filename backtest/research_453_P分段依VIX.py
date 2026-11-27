"""研究 453：P 的日盤段（D開→D收）與隔夜段（D收→D+1開）依前一天清洗 VIX 分組（<25／25～35／≥35）
用法：python -X utf8 backtest/research_453_P分段依VIX.py
"""
import io
import contextlib
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
with contextlib.redirect_stdout(io.StringIO()):
    import research_148_恐慌連續觸發 as R
    import research_444_P依VIX倍數 as M
VD = M.R.D
med = np.array([np.median(M.V[max(0, k - 2):k + 1]) for k in range(len(M.V))])
vix = {d: med[k] for k, d in enumerate(VD) if not np.isnan(med[k])}
dates, day, night, near = R.R144.R139.load_tx()
pos = {d: k for k, d in enumerate(dates)}
G = {"<25": [], "25～35": [], "≥35": []}
for x in R.build():
    if not x["sig"]:
        continue
    k = pos[x["d"]]
    v = vix.get(dates[k - 1])
    if v is None:
        continue
    m = near[dates[k - 1]]
    b, b1 = day[x["d"]][m], day[dates[k + 1]][m]
    g = "<25" if v < 25 else ("≥35" if v >= 35 else "25～35")
    G[g].append(((b[3] - b[0] - R.COST) / b[0], (b1[0] - b[3]) / b[0], x["r"]))
L = ["研究 453：P 日盤段／隔夜段 × 前一天台指 VIX（近 3 日中位）", ""]
for g, v in G.items():
    a = np.array(v)
    L.append(f"VIX {g:6s} {len(a):3d} 筆｜日盤 {a[:,0].mean():+.2%}（勝 {np.mean(a[:,0]>0):.0%}）｜隔夜 {a[:,1].mean():+.2%}（勝 {np.mean(a[:,1]>0):.0%}）｜合計 {a[:,2].mean():+.2%}")
o = "\n".join(L)
print(o)
open(os.path.join(HERE, "結果_研究453_P分段依VIX.txt"), "w", encoding="utf-8").write(o + "\n")
