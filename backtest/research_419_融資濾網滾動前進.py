"""研究 419：融資過熱濾網門檻的滾動前進驗證（strategy_v3.run 的 th／zth，2x 模型價）
候選 th 15／17.5／20% × zth 1.5／2／2.5；每個候選算 2002～ 每日報酬；每年 Y（2006～2026，濾網資料 2001 起）用 2002～Y−1 年化最高者的 Y 年報酬
對照：固定 17.5%／2、不用濾網（use_heat=False）
用法：python -X utf8 backtest/research_419_融資濾網滾動前進.py
"""
import os
import sys
from collections import Counter

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import strategy_v3 as V  # noqa: E402

bt = V.bt
END = bt.DAYS[-1]


def daily(**kw):
    _, _, e = V.run("2002-01-01", END, curve=True, **kw)
    e = np.asarray(e)
    return np.r_[0.0, e[1:] / e[:-1] - 1]


i0 = next(i for i, d in enumerate(bt.DAYS) if d >= "2002-01-01")
C = {(th, z): daily(th=th, zth=z) for th in (0.15, 0.175, 0.20) for z in (1.5, 2.0, 2.5)}
n = len(next(iter(C.values())))
D = bt.DAYS[i0:i0 + n]
yrs = np.array([d[:4] for d in D])
none = daily(use_heat=False)
wf = np.zeros(n)
picks = []
for Y in range(2006, 2027):
    y = str(Y)
    past = yrs < y
    best = max(C, key=lambda k: np.prod(1 + C[k][past]))
    picks.append((y, best))
    wf[yrs == y] = C[best][yrs == y]
sel = yrs >= "2006"


def st(x):
    eq = np.cumprod(1 + x[sel])
    return eq[-1] ** (bt.TD / sel.sum()) - 1, (eq / np.maximum.accumulate(eq) - 1).min()


L = ["研究 419：融資過熱濾網門檻滾動前進（2006～2026 樣本外；v3 2x 模型價）", ""]
L.append("滾動挑選：年化 {:.1%}、回檔 {:.1%}".format(*st(wf)))
L.append("固定 17.5%／z2：年化 {:.1%}、回檔 {:.1%}".format(*st(C[(0.175, 2.0)])))
L.append("不用濾網：年化 {:.1%}、回檔 {:.1%}".format(*st(none)))
L.append("各候選 2006～：" + "、".join(f"{k[0]:.1%}/z{k[1]} {st(v)[0]:.1%}" for k, v in C.items()))
L.append("每年挑到：" + "、".join(f"{k[0]:.1%}/z{k[1]}×{v}" for k, v in Counter(p for _, p in picks).most_common()))
out = "\n".join(L)
print(out)
open(os.path.join(HERE, "結果_研究419_融資濾網滾動前進.txt"), "w", encoding="utf-8").write(out + "\n")
