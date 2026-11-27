"""研究 414：期貨加碼（P 1x＋D 0.5x＋V 1x）的叢集風險：滾動 5／10／20 個交易日的合計損益（占總資金）最差值與日期
資料：研究 407／411 的逐筆損益（記在出場日）；2002～
用法：python -X utf8 backtest/research_414_加碼叢集風險.py
"""
import io
import contextlib
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
with contextlib.redirect_stdout(io.StringIO()):
    import research_411_實際配置含V as V  # noqa: E402
R = V.R
ov = R.padd + R.dadd + V.vadd
D = R.D
L = ["研究 414：期貨加碼叢集風險（P 1x＋D 0.5x＋V 1x，占總資金；2002～）", ""]
for w in (5, 10, 20):
    roll = np.convolve(ov, np.ones(w), "valid")
    order = np.argsort(roll)
    picked = []
    for k in order:
        if all(abs(k - j) > w for j in picked):
            picked.append(k)
        if len(picked) == 3:
            break
    L.append(f"滾動 {w:2d} 日最差 3 段：" + "、".join(f"{D[k]}～{D[k + w - 1]} {roll[k]:+.1%}" for k in picked)
             + f"｜95 分位 {np.quantile(roll, 0.05):+.1%}")
nz = ov != 0
L.append(f"\n加碼出場日 {nz.sum()} 天；單日合計最差 {ov.min():+.1%}（{D[int(np.argmin(ov))]}）")
yrs = R.yrs
L.append("逐年加碼合計：" + "  ".join(f"{y}:{ov[yrs == y].sum():+.0%}" for y in sorted(set(yrs))))
out = "\n".join(L)
print(out)
open(os.path.join(HERE, "結果_研究414_加碼叢集風險.txt"), "w", encoding="utf-8").write(out + "\n")
