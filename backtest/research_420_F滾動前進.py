"""研究 420：F 外資期貨雙指標的滾動前進驗證（2018-06～，研究 141 的資料：外資未平倉變化 z 與交易淨額 z；結算日與次日排除；v3 在場）
候選 z 門檻 1.0／1.5／2.0（兩個 z 都要過）× 抱 H 5／10 天；台指期近月 隔天開盤進 → 第 H 天收盤出，扣 6 點；持有中不重複
每年 Y（2020～2026）用 Y 之前事件挑每筆最高（≥5 筆）套到 Y；對照固定 1.5／5
用法：python -X utf8 backtest/research_420_F滾動前進.py
"""
import csv
import io
import contextlib
import os
import sys
from collections import Counter

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
with contextlib.redirect_stdout(io.StringIO()):
    import research_141_加碼總曝險上限 as R141  # noqa: E402
T = R141.build()
R139, R127 = R141.R139, R141.R127
dates, day, night, near = R139.load_tx()
last_day = {}
for d in dates:
    for m in day[d]:
        last_day[m] = d
settle = set(last_day.values())
excl = settle | {dates[k + 1] for k, d in enumerate(dates[:-1]) if d in settle}
flow, oi = {}, {}
for r in csv.DictReader(open(os.path.join(HERE, "tx_inst_oi.csv"), encoding="utf-8")):
    if r["investor"] == "外資":
        flow[r["date"]] = int(r["long_vol"]) - int(r["short_vol"])
        oi[r["date"]] = int(r["long_oi"]) - int(r["short_oi"])
ods = sorted(oi)
doi = {ods[k]: oi[ods[k]] - oi[ods[k - 1]] for k in range(1, len(ods))}
zo, zf = R127.zmap(doi), R127.zmap(flow)
n = len(T)
o = np.array([t["o"] for t in T])
c = np.array([t["c"] for t in T])
st = np.array([t["st"] for t in T])
D = [t["d"] for t in T]


def events(z, H):
    out, k = [], 0
    while k < n - H - 1:
        d = D[k]
        if st[k] == 1 and d not in excl and (zo.get(d) or 0) > z and (zf.get(d) or 0) > z:
            out.append((d, c[k + H] / o[k + 1] - 1 - 6 / o[k + 1]))
            k += H + 1
        else:
            k += 1
    return out


C = {(z, H): events(z, H) for z in (1.0, 1.5, 2.0) for H in (5, 10)}
wf, fixed, picks = [], [], []
for Y in range(2020, 2027):
    y = str(Y)
    best, bm = None, -9
    for key, ev in C.items():
        past = [r for d, r in ev if d[:4] < y]
        if len(past) >= 5 and np.mean(past) > bm:
            best, bm = key, np.mean(past)
    if best is None:
        continue
    picks.append((y, best))
    wf += [r for d, r in C[best] if d[:4] == y]
    fixed += [r for d, r in C[(1.5, 5)] if d[:4] == y]
wf, fixed = np.array(wf), np.array(fixed)
inmk = [c[k + 5] / o[k + 1] - 1 for k in range(n - 6) if st[k] == 1 and D[k] >= "2020"]
L = ["研究 420：F 滾動前進驗證（2020～2026 樣本外；台指期隔天開盤進、扣 6 點）", ""]
L.append(f"滾動挑選：{len(wf)} 筆 每筆 {wf.mean():+.2%} 勝率 {np.mean(wf > 0):.0%}")
L.append(f"固定 z1.5／H5：{len(fixed)} 筆 每筆 {fixed.mean():+.2%} 勝率 {np.mean(fixed > 0):.0%}")
L.append(f"對照：在場任一日 5 日 {np.mean(inmk):+.2%}")
L.append("各候選全期：" + "、".join(f"z{k[0]}/H{k[1]} {len(v)}筆 {np.mean([r for _, r in v]):+.2%}" for k, v in C.items()))
L.append("每年挑到：" + "、".join(f"z{k[0]}/H{k[1]}×{v}" for k, v in Counter(p for _, p in picks).most_common()))
out = "\n".join(L)
print(out)
open(os.path.join(HERE, "結果_研究420_F滾動前進.txt"), "w", encoding="utf-8").write(out + "\n")
