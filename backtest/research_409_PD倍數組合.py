"""研究 409：P × D 倍數組合（主策略 1.7x 為基準；2002～；研究 407 的逐筆損益）
P 0.5／1／1.5 × D 0／0.5／1／1.5：年化、最大回檔、P＋D 同一天出場的最差合計
用法：python -X utf8 backtest/research_409_PD倍數組合.py
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

L = ["研究 409：P × D 倍數（主策略 1.7x；2002～；年化／最大回檔／短線單日最差）", "P＼D " + "".join(f"{d:>22}" for d in ("0x", "0.5x", "1x", "1.5x"))]
for p in (0.5, 1.0, 1.5):
    row = []
    for d in (0, 0.5, 1.0, 1.5):
        r = R.main + p * R.padd + d / 0.5 * R.dadd
        eq = np.cumprod(1 + r)
        cg = eq[-1] ** (R.bt.TD / len(r)) - 1
        mdd = (eq / np.maximum.accumulate(eq) - 1).min()
        w = (p * R.padd + d / 0.5 * R.dadd).min()
        row.append(f"{cg:5.1%}／{mdd:6.1%}／{w:+.0%}")
    L.append(f"P {p}x " + "".join(f"{x:>22}" for x in row))
nz = R.dadd != 0
L.append(f"\nD 筆數（2002～）：{int(nz.sum())}；D 0.5x 每筆平均 {R.dadd[nz].mean():+.2%}（資金）")
out = "\n".join(L)
print(out)
open(os.path.join(HERE, "結果_研究409_PD倍數組合.txt"), "w", encoding="utf-8").write(out + "\n")
