"""研究 416：V 爆量收黑加碼的滾動前進驗證
事件：v3 在場、成交金額 ≥ k 倍前 20 日均且加權收黑；報酬＝隔天收盤 → 第 H 天收盤（加權，扣 0.1%）；持有中不重複；v3 出場不提前平（簡化）
候選 k 1.3／1.5／1.7／2.0 × H 5／10；每年 Y（2004～2026）用 Y 之前事件挑每筆平均最高（≥6 筆）套到 Y 年；對照固定 k1.5／H10
用法：python -X utf8 backtest/research_416_V滾動前進.py
"""
import io
import contextlib
import os
import sys
from collections import Counter

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
with contextlib.redirect_stdout(io.StringIO()):
    import research_138_金字塔加碼與分段停損 as R138  # noqa: E402
    import research_141_加碼總曝險上限 as R141  # noqa: E402
R139 = R141.R139
bt = R138.bt
DAYS, PX, ST, N = R138.DAYS, np.array(R138.PX), np.array(R138.ST), R138.N
AMT = np.array([R139.AMT.get(d, np.nan) for d in DAYS])
vr = np.full(N, np.nan)
for i in range(20, N):
    base = AMT[i - 20:i]
    base = base[~np.isnan(base)]
    if len(base) >= 16 and not np.isnan(AMT[i]):
        vr[i] = AMT[i] / base.mean()
down = np.r_[False, PX[1:] < PX[:-1]]


def events(k, H):
    out, i = [], 0
    while i < N - H - 1:
        if ST[i] == 1 and down[i] and vr[i] >= k:
            out.append((i, PX[i + 1 + H] / PX[i + 1] - 1 - 0.001))
            i += H + 1
        else:
            i += 1
    return out


C = {(k, H): events(k, H) for k in (1.3, 1.5, 1.7, 2.0) for H in (5, 10)}
wf, fixed, picks = [], [], []
for Y in range(2004, 2027):
    y = str(Y)
    best, bm = None, -9
    for key, ev in C.items():
        past = [r for i, r in ev if DAYS[i][:4] < y]
        if len(past) >= 6 and np.mean(past) > bm:
            best, bm = key, np.mean(past)
    if best is None:
        continue
    picks.append((y, best))
    wf += [r for i, r in C[best] if DAYS[i][:4] == y]
    fixed += [r for i, r in C[(1.5, 10)] if DAYS[i][:4] == y]
wf, fixed = np.array(wf), np.array(fixed)
inmk = [PX[i + 11] / PX[i + 1] - 1 for i in range(N - 11) if ST[i] == 1 and DAYS[i] >= "2004"]
L = ["研究 416：V 滾動前進驗證（2004～2026 樣本外；加權隔天收盤進、扣 0.1%）", ""]
L.append(f"滾動挑選：{len(wf)} 筆 每筆 {wf.mean():+.2%} 勝率 {np.mean(wf > 0):.0%} 累積 {np.prod(1 + wf) - 1:+.0%}")
L.append(f"固定 k1.5／H10：{len(fixed)} 筆 每筆 {fixed.mean():+.2%} 勝率 {np.mean(fixed > 0):.0%} 累積 {np.prod(1 + fixed) - 1:+.0%}")
L.append(f"對照：在場任一日 10 日平均 {np.mean(inmk):+.2%}")
L.append("每年挑到：" + "、".join(f"k{k[0]}/H{k[1]}×{v}" for k, v in Counter(p for _, p in picks).most_common()))
out = "\n".join(L)
print(out)
open(os.path.join(HERE, "結果_研究416_V滾動前進.txt"), "w", encoding="utf-8").write(out + "\n")
