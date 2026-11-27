"""研究 454：P 依前一天清洗 VIX 分組，抱到 D+1／D+2／D+3／D+5 開盤（D 開進）的平均與勝率；對照研究 201（依跌深）
用法：python -X utf8 backtest/research_454_高VIX抱久.py
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
med = np.array([np.median(M.V[max(0, k - 2):k + 1]) for k in range(len(M.V))])
vix = {d: med[k] for k, d in enumerate(M.R.D) if not np.isnan(med[k])}
dates, day, night, near = R.R144.R139.load_tx()
pos = {d: k for k, d in enumerate(dates)}
H = (1, 2, 3, 5)
G = {"<25": [], "25～35": [], "≥35": []}
for x in R.build():
    if not x["sig"]:
        continue
    k = pos[x["d"]]
    v = vix.get(dates[k - 1])
    if v is None or k + 5 >= len(dates):
        continue
    m = near[dates[k - 1]]
    b0 = day[x["d"]][m][0]
    row = []
    for h in H:
        bb = day[dates[k + h]].get(m)
        row.append((bb[0] - b0 - R.COST) / b0 if bb else np.nan)
    G["<25" if v < 25 else ("≥35" if v >= 35 else "25～35")].append(row)
L = ["研究 454：P 抱久一點 × 前一天 VIX（D 開進 → D+h 開出）", ""]
for g, v in G.items():
    a = np.array(v)
    L.append(f"VIX {g:6s} {len(a):3d} 筆｜" + "｜".join(f"D+{h} {np.nanmean(a[:, i]):+.2%}（勝 {np.nanmean(a[:, i] > 0):.0%}，每日 {np.nanmean(a[:, i]) / h:+.2%}）" for i, h in enumerate(H)))
o = "\n".join(L)
print(o)
open(os.path.join(HERE, "結果_研究454_高VIX抱久.txt"), "w", encoding="utf-8").write(o + "\n")
# 對照：非 P 訊號日、前一天 VIX 同組，D+1 開 → D+5 開（抱久那 4 天的額外部分）
sigd = {x["d"] for x in R.build() if x["sig"]}
C = {"<25": [], "25～35": [], "≥35": []}
for k in range(1, len(dates) - 6):
    d = dates[k]
    v = vix.get(dates[k - 1])
    if d in sigd or v is None:
        continue
    m = near[dates[k - 1]]
    a, b = day[dates[k + 1]].get(m), day[dates[k + 5]].get(m)
    if a and b:
        C["<25" if v < 25 else ("≥35" if v >= 35 else "25～35")].append(b[0] / a[0] - 1)
L2 = ["", "對照（非訊號日、同 VIX 組；D+1 開→D+5 開 4 天）vs P 的同一段："]
for g in G:
    a = np.array(G[g])
    L2.append(f"VIX {g:6s} 非訊號 {np.mean(C[g]):+.2%}（{len(C[g])} 天）｜P 的 D+1→D+5 {np.nanmean(a[:, 3] - a[:, 0]):+.2%}")
o2 = "\n".join(L2)
print(o2)
open(os.path.join(HERE, "結果_研究454_高VIX抱久.txt"), "a", encoding="utf-8").write(o2 + "\n")
