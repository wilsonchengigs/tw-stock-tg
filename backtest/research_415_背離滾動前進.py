"""研究 415：D 台美背離的滾動前進（walk-forward）驗證
候選 9 組：回看 W 10／20／30 日 × 門檻 8／10／12%；事件＝背離 ≤ −門檻、持有中不重複，報酬＝隔天收盤 → 第 5 天收盤（加權，扣 0.1%）
每年 Y（2003～2026）：用 1998～Y−1 的事件挑「每筆平均最高、且 ≥8 筆」的一組，套到 Y 年；對照＝固定 W20／10%
用法：python -X utf8 backtest/research_415_背離滾動前進.py
"""
import io
import contextlib
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
with contextlib.redirect_stdout(io.StringIO()):
    import research_206_台美背離延伸 as R  # noqa: E402

TW, D, N, US = R.TW, R.DAYS, R.N, R.BENCH["GSPC"]
yrs = np.array([d[:4] for d in D])


def events(W, th):
    gap = np.array([TW[k] / TW[k - W] - US[k] / US[k - W] if k >= W else np.nan for k in range(N)])
    out, k = [], W
    while k < N - 6:
        if gap[k] <= -th:
            out.append((k, TW[k + 6] / TW[k + 1] - 1 - 0.001))
            k += 6
        else:
            k += 1
    return out


C = {(W, th): events(W, th) for W in (10, 20, 30) for th in (0.08, 0.10, 0.12)}
wf, fixed, picks = [], [], []
for Y in range(2003, 2027):
    y = str(Y)
    best, bm = None, -9
    for key, ev in C.items():
        past = [r for k, r in ev if D[k][:4] < y]
        if len(past) >= 8 and np.mean(past) > bm:
            best, bm = key, np.mean(past)
    if best is None:
        continue
    picks.append((y, best))
    wf += [r for k, r in C[best] if D[k][:4] == y]
    fixed += [r for k, r in C[(20, 0.10)] if D[k][:4] == y]
wf, fixed = np.array(wf), np.array(fixed)
L = ["研究 415：D 滾動前進驗證（2003～2026 樣本外；加權隔天收盤進、第 5 天收盤出、扣 0.1%）", ""]
L.append(f"滾動挑選：{len(wf)} 筆 每筆 {wf.mean():+.2%} 勝率 {np.mean(wf > 0):.0%} 累積 {np.prod(1 + wf) - 1:+.0%}")
L.append(f"固定 W20／10%：{len(fixed)} 筆 每筆 {fixed.mean():+.2%} 勝率 {np.mean(fixed > 0):.0%} 累積 {np.prod(1 + fixed) - 1:+.0%}")
allr = np.array([TW[k + 6] / TW[k + 1] - 1 for k in range(N - 6) if D[k] >= "2003"])
L.append(f"全部日 5 日平均 {allr.mean():+.2%}")
from collections import Counter  # noqa: E402
L.append("每年挑到的組合（次數）：" + "、".join(f"W{k[0]}/{k[1]:.0%}×{v}" for k, v in Counter(p for _, p in picks).most_common()))
L.append("近年挑選：" + "、".join(f"{y}:W{p[0]}/{p[1]:.0%}" for y, p in picks[-6:]))
out = "\n".join(L)
print(out)
open(os.path.join(HERE, "結果_研究415_背離滾動前進.txt"), "w", encoding="utf-8").write(out + "\n")
