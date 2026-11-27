"""研究 418：主策略核心均線的滾動前進驗證（研究 217 的 sim 引擎：週五 MA_e×1.01 進、MA_x×0.975 出、2x、借貸 2%、成本 0.25%）
候選：進 40／60／80 × 出 60／80／120（出 ≥ 進）；每個候選先算全期每日報酬（狀態連續），每年 Y（2003～2026）用 1998～Y−1 年化最高的候選，取它在 Y 年的日報酬
對照：固定 60／80；買進持有 1x
用法：python -X utf8 backtest/research_418_主策略滾動前進.py
"""
import io
import contextlib
import os
import sys
from collections import Counter
from datetime import datetime

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
with contextlib.redirect_stdout(io.StringIO()):
    import research_217_主策略套亞洲市場 as R  # noqa: E402

D, P = R.MK["加權"]
n = len(P)
r = np.r_[0.0, P[1:] / P[:-1] - 1]
cs = np.r_[0, np.cumsum(P)]
wk = [datetime.fromisoformat(x).isocalendar()[:2] for x in D]
we = [k == n - 1 or wk[k + 1] != wk[k] for k in range(n)]


def daily(ne, nx, lev=2.0):
    ma = lambda k, w: (cs[k + 1] - cs[k + 1 - w]) / w if k + 1 >= w else np.nan  # noqa: E731
    out = np.zeros(n)
    state, pend = 0, None
    for k in range(130, n):
        x = (1 + lev * r[k] - (lev - 1) * R.BORROW) if state else 1.0
        if pend is not None:
            x *= 1 - R.COST * lev
            state, pend = pend, None
        out[k] = x - 1
        if we[k]:
            if state == 0 and P[k] > ma(k, ne) * 1.01:
                pend = 1
            elif state == 1 and P[k] < ma(k, nx) * 0.975:
                pend = 0
    return out


C = {(e, x): daily(e, x) for e in (40, 60, 80) for x in (60, 80, 120) if x >= e}
yrs = np.array([d[:4] for d in D])
wf = np.zeros(n)
picks = []
for Y in range(2003, 2027):
    y = str(Y)
    past = (yrs >= "1998") & (yrs < y)
    best = max(C, key=lambda k: np.prod(1 + C[k][past]))
    picks.append((y, best))
    m = yrs == y
    wf[m] = C[best][m]
sel = yrs >= "2003"


def st(x):
    eq = np.cumprod(1 + x[sel])
    return eq[-1] ** (252 / sel.sum()) - 1, (eq / np.maximum.accumulate(eq) - 1).min()


bh = r.copy()
L = ["研究 418：主策略核心均線滾動前進（2003～2026 樣本外；不含融資濾網、價格指數）", ""]
L.append("滾動挑選：年化 {:.1%}、回檔 {:.1%}".format(*st(wf)))
L.append("固定 60／80：年化 {:.1%}、回檔 {:.1%}".format(*st(C[(60, 80)])))
L.append("買進持有 1x：年化 {:.1%}、回檔 {:.1%}".format(*st(bh)))
L.append("各候選 2003～：" + "、".join(f"{k[0]}/{k[1]} {st(v)[0]:.1%}" for k, v in C.items()))
L.append("每年挑到：" + "、".join(f"{k[0]}/{k[1]}×{v}" for k, v in Counter(p for _, p in picks).most_common()))
out = "\n".join(L)
print(out)
open(os.path.join(HERE, "結果_研究418_主策略滾動前進.txt"), "w", encoding="utf-8").write(out + "\n")
