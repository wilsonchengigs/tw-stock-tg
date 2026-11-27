"""研究 452：P 出場時間——D 開→D 收（日盤內）vs 現行 D 開→D+1 開；另看 D 收→D+1 開（隔夜段）
台指期真實價（研究 148 build 同資料），成本每筆同 COST；兩段
用法：python -X utf8 backtest/research_452_P當天收盤出.py
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
dates, day, night, near = R.R144.R139.load_tx()
pos = {d: k for k, d in enumerate(dates)}
rows = [x for x in R.build() if x["sig"]]
out = {"現行 D開→D+1開": [], "D開→D收": [], "隔夜 D收→D+1開": []}
yrs = []
for x in rows:
    k = pos[x["d"]]
    m = near[dates[k - 1]]
    b, b1 = day[x["d"]][m], day[dates[k + 1]][m]
    out["現行 D開→D+1開"].append(x["r"])
    out["D開→D收"].append((b[3] - b[0] - R.COST) / b[0])
    out["隔夜 D收→D+1開"].append((b1[0] - b[3]) / b[0])
    yrs.append(x["d"][:4])
yrs = np.array(yrs)
L = [f"研究 452：P 出場時間（{len(rows)} 筆，台指期真實價）", ""]
for lab, v in out.items():
    v = np.array(v)
    seg = [v[(yrs >= lo) & (yrs < hi)].mean() for lo, hi in (("1998", "2013"), ("2013", "2099"))]
    L.append(f"{lab:14s} 平均 {v.mean():+.2%} 勝率 {np.mean(v > 0):.0%} 最差 {v.min():+.1%} 標準差 {v.std():.2%}｜兩段 {seg[0]:+.2%}／{seg[1]:+.2%}")
o = "\n".join(L)
print(o)
open(os.path.join(HERE, "結果_研究452_P當天收盤出.txt"), "w", encoding="utf-8").write(o + "\n")
