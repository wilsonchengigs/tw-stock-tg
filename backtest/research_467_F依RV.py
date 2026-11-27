"""研究 467：F 外資雙指標（未平倉變化 z 與交易淨額 z 都 >1.5、v3 在場、排除結算日與隔天）依訊號日 RV20 分組
事件報酬＝台指期近月 隔天開→第 5 天收（不含停損），2018-06～
用法：python -X utf8 backtest/research_467_F依RV.py
"""
import csv
import io
import contextlib
import importlib.util
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


with contextlib.redirect_stdout(io.StringIO()):
    m127 = load("r127", "research_127_外資期貨交易淨額.py")
    S = load("r459", "research_459_P依RV倍數長歷史.py")
    V = load("r411", "research_411_實際配置含V.py")
ST = {d: int(V.st[k]) for k, d in enumerate(V.ds)}
flow, oi = {}, {}
for r in csv.DictReader(open(os.path.join(HERE, "tx_inst_oi.csv"), encoding="utf-8")):
    if r["investor"] == "外資":
        flow[r["date"]] = int(r["long_vol"]) - int(r["short_vol"])
        oi[r["date"]] = int(r["long_oi"]) - int(r["short_oi"])
ods = sorted(oi)
doi = {ods[k]: oi[ods[k]] - oi[ods[k - 1]] for k in range(1, len(ods))}
zo, zf = m127.zmap(doi), m127.zmap(flow)
dates, day, near = S.dates, S.day, S.near
last = {}
for d in dates:
    for m in day[d]:
        last[m] = d
settle = set(last.values())
rows = []
for k, d in enumerate(dates[:-6]):
    if d in settle or (k and dates[k - 1] in settle):
        continue
    a, b = zo.get(d), zf.get(d)
    st = ST.get(d)
    if a is None or b is None or not (a > 1.5 and b > 1.5) or st != 1:
        continue
    m = near[d]
    o, c = day[dates[k + 1]].get(m), day[dates[k + 5]].get(m)
    if o and c:
        rows.append((d, S.rv[k], (c[3] - o[0] - 3) / o[0]))
v = np.array([x[1] for x in rows])
r = np.array([x[2] for x in rows])
L = [f"研究 467：F 外資雙指標（{len(r)} 筆）依訊號日 RV20", ""]
for lab, g in (("<15%", v < 0.15), ("15～23%", (v >= 0.15) & (v < 0.23)), ("≥23%", v >= 0.23)):
    L.append(f"RV {lab:7s} {g.sum():3d} 筆 平均 {r[g].mean():+.2%} 勝率 {np.mean(r[g] > 0):.0%}")
o = "\n".join(L)
print(o)
open(os.path.join(HERE, "結果_研究467_F依RV.txt"), "w", encoding="utf-8").write(o + "\n")
