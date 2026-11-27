"""研究 424：主策略 v3 2x ＋ S&P500 長抱（台幣計；價格＋股息約 1.8%／年×70% 預扣後）每日再平衡；2004～（TWD.json 起）
用法：python -X utf8 backtest/research_424_主策略混美股.py
"""
import bisect
import json
import os
import sys
from datetime import datetime, timedelta, timezone

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


def load(f, tz):
    g = json.load(open(os.path.join(HERE, f + ".json")))
    rows = [(datetime.fromtimestamp(t, timezone(timedelta(hours=tz))).strftime("%Y-%m-%d"), p) for t, p in zip(g["timestamp"], g["indicators"]["quote"][0]["close"]) if p]
    d, p = [x for x, _ in rows], [x for _, x in rows]
    return np.array([p[bisect.bisect_left(d, x) - 1] if bisect.bisect_left(d, x) > 0 else np.nan for x in D])


fx = load("TWD", 8)
fx = np.where((fx < 20) | (fx > 45), np.nan, fx)  # TWD.json 有壞值（2011-10-24 1.80、2014-12-31 3.67）
for k in range(1, len(fx)):
    if np.isnan(fx[k]):
        fx[k] = fx[k - 1]
sp = load("GSPC", -5) * fx
us = np.r_[0.0, sp[1:] / sp[:-1] - 1] + 0.018 * 0.7 / 252
yrs = np.array([d[:4] for d in D])
ok = (yrs >= "2004") & ~np.isnan(us)
us = np.nan_to_num(us)


def st(r, lo, hi):
    m = ok & (yrs >= lo) & (yrs < hi)
    eq = np.cumprod(1 + r[m])
    return eq[-1] ** (bt.TD / m.sum()) - 1, (eq / np.maximum.accumulate(eq) - 1).min()


L = ["研究 424：主策略 v3 2x ＋ S&P500 長抱（台幣）混合（年化／回檔）", "美股比例｜2004～｜2011～2019（台股弱趨勢）｜2020～"]
for w in (0, 0.2, 0.3, 0.5, 1.0):
    r = (1 - w) * v3 + w * us
    L.append(f"{w:.0%}｜" + "｜".join(f"{c:.1%}／{m:.0%}" for c, m in (st(r, "2004", "2099"), st(r, "2011", "2020"), st(r, "2020", "2099"))))
out = "\n".join(L)
print(out)
open(os.path.join(HERE, "結果_研究424_主策略混美股.txt"), "w", encoding="utf-8").write(out + "\n")
