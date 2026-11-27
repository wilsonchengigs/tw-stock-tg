"""研究 408：P 恐慌做多的倍數，在使用者實際配置（主策略 1.7x＋D 0.5x）與 2002～ 長歷史下重估（研究 170 只用 2018～）
P 倍數 0／0.5／1／1.5／2；年化、最大回檔、最差單筆（占資金）、兩段
用法：python -X utf8 backtest/research_408_P倍數長歷史.py
"""
import io
import contextlib
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
with contextlib.redirect_stdout(io.StringIO()):
    import research_407_實際配置長歷史 as R  # noqa: E402

yrs = R.yrs
L = ["研究 408：P 倍數（主策略 1.7x＋D 0.5x 為基準；2002～）", ""]
for u in (0, 0.5, 1.0, 1.5, 2.0):
    r = R.main + u * R.padd + R.dadd
    eq = np.cumprod(1 + r)
    cg = eq[-1] ** (R.bt.TD / len(r)) - 1
    mdd = (eq / np.maximum.accumulate(eq) - 1).min()
    seg = []
    for lo, hi in (("2002", "2013"), ("2013", "2099")):
        m = (yrs >= lo) & (yrs < hi)
        x = np.cumprod(1 + r[m])
        seg.append(f"{x[-1] ** (R.bt.TD / m.sum()) - 1:.1%}")
    worst = (u * R.padd).min()
    L.append(f"P {u}x：年化 {cg:5.1%}  回檔 {mdd:6.1%}  P 最差單筆 {worst:+.1%}｜2002–2012 {seg[0]}｜2013～ {seg[1]}")
out = "\n".join(L)
print(out)
open(os.path.join(HERE, "結果_研究408_P倍數長歷史.txt"), "w", encoding="utf-8").write(out + "\n")
