"""研究 423：主策略 v3（2x 模型價）與 0050 長抱（加權含息 1x 近似，bt.R1）每日再平衡混合
0050 比例 0／20／30／50%；全期 2002～、弱趨勢期 2011～2019、2020～；年化、回檔、落後 0050 的最長年數
用法：python -X utf8 backtest/research_423_主策略混0050.py
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import strategy_v3 as V  # noqa: E402

bt = V.bt
_, _, e = V.run("2002-01-01", bt.DAYS[-1], curve=True)
e = np.asarray(e)
i0 = next(i for i, d in enumerate(bt.DAYS) if d >= "2002-01-01")
D = bt.DAYS[i0:i0 + len(e)]
v3 = np.r_[0.0, e[1:] / e[:-1] - 1]
r1 = np.array(bt.R1[i0:i0 + len(e)])
yrs = np.array([d[:4] for d in D])


def st(r, lo, hi):
    m = (yrs >= lo) & (yrs < hi)
    eq = np.cumprod(1 + r[m])
    return eq[-1] ** (bt.TD / m.sum()) - 1, (eq / np.maximum.accumulate(eq) - 1).min()


L = ["研究 423：主策略 v3 2x ＋ 0050 長抱混合（每日再平衡；年化／回檔）", "0050 比例｜2002～｜2011～2019（弱趨勢）｜2020～｜3 年滾動落後 0050 的月份比例"]
for w in (0, 0.2, 0.3, 0.5, 1.0):
    r = (1 - w) * v3 + w * r1
    eq = np.cumprod(1 + r)
    eb = np.cumprod(1 + r1)
    lag = [(eq[k] / eq[k - 756]) < (eb[k] / eb[k - 756]) for k in range(756, len(eq), 21)]
    L.append(f"{w:.0%}｜" + "｜".join(f"{c:.1%}／{m:.0%}" for c, m in (st(r, "2002", "2099"), st(r, "2011", "2020"), st(r, "2020", "2099"))) + f"｜{np.mean(lag):.0%}")
out = "\n".join(L)
print(out)
open(os.path.join(HERE, "結果_研究423_主策略混0050.txt"), "w", encoding="utf-8").write(out + "\n")
