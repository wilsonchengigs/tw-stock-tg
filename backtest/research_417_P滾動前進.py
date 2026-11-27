"""研究 417：P 恐慌做多的滾動前進驗證（研究 148 的逐日資料：台指期 D 開 → D+1 開、扣 3 點）
候選門檻 x 1.5／2／2.5／3%：夜盤跌 ≥x 或 S&P 前一晚跌 ≥x；每年 Y（2001～2026）用 Y 之前挑每筆最高（≥15 筆）套到 Y 年；對照固定 2%
用法：python -X utf8 backtest/research_417_P滾動前進.py
"""
import importlib.util
import io
import contextlib
import os
import sys
from collections import Counter
from datetime import datetime, timedelta

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r148", os.path.join(HERE, "research_148_恐慌連續觸發.py"))
R = importlib.util.module_from_spec(spec)
with contextlib.redirect_stdout(io.StringIO()):
    spec.loader.exec_module(R)
R144 = R.R144
dates, day, night, near = R144.R139.load_tx()
US = R144.us("GSPC.json")
rows = []
for k in range(1, len(dates) - 1):
    d, pd_, d1 = dates[k], dates[k - 1], dates[k + 1]
    m = near[pd_]
    b, b1 = day[d].get(m), day[d1].get(m)
    if not (b and b1):
        continue
    nb = night[d].get(m)
    nr = (nb[3] / nb[0] - 1) if nb and nb[4] >= 1000 else None
    u = None
    for back in range(1, 5):
        kk = (datetime.fromisoformat(d) - timedelta(days=back)).strftime("%Y-%m-%d")
        if kk in US:
            u = US[kk]
            break
    rows.append((d, nr, u, (b1[0] - b[0] - 3) / b[0]))


def trades(x):
    return [(d, r) for d, nr, u, r in rows if (nr is not None and nr <= -x) or (u is not None and u <= -x)]


C = {x: trades(x) for x in (0.015, 0.02, 0.025, 0.03)}
wf, fixed, picks = [], [], []
for Y in range(2001, 2027):
    y = str(Y)
    best, bm = None, -9
    for x, tr in C.items():
        past = [r for d, r in tr if d[:4] < y]
        if len(past) >= 15 and np.mean(past) > bm:
            best, bm = x, np.mean(past)
    if best is None:
        continue
    picks.append((y, best))
    wf += [r for d, r in C[best] if d[:4] == y]
    fixed += [r for d, r in C[0.02] if d[:4] == y]
wf, fixed = np.array(wf), np.array(fixed)
allr = np.array([r for d, nr, u, r in rows if d >= "2001"])
L = ["研究 417：P 滾動前進驗證（2001～2026 樣本外；台指期 D 開 → D+1 開、扣 3 點）", ""]
L.append(f"滾動挑選：{len(wf)} 筆 每筆 {wf.mean():+.2%} 勝率 {np.mean(wf > 0):.0%} 累積(1x) {np.prod(1 + wf) - 1:+.0%}")
L.append(f"固定 2%：{len(fixed)} 筆 每筆 {fixed.mean():+.2%} 勝率 {np.mean(fixed > 0):.0%} 累積(1x) {np.prod(1 + fixed) - 1:+.0%}")
L.append(f"對照：任一日 D 開 → D+1 開 {allr.mean():+.3%}")
L.append("每年挑到：" + "、".join(f"{x:.1%}×{v}" for x, v in Counter(p for _, p in picks).most_common()))
L.append("近年：" + "、".join(f"{y}:{x:.1%}" for y, x in picks[-6:]))
out = "\n".join(L)
print(out)
open(os.path.join(HERE, "結果_研究417_P滾動前進.txt"), "w", encoding="utf-8").write(out + "\n")
