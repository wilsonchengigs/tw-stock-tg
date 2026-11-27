"""研究 422：台股趨勢性偏弱期（研究 217：8 年滾動 VR(26) 在 2016～2020 結束時 < 1）使用者實際配置的表現
期間 2011～2019（主策略水下期 2011–2017 ＋ 2018–2019）；主策略 1.7x、＋P＋D＋V（研究 411 序列）；對照 0050（加權含息 1x 近似）
用法：python -X utf8 backtest/research_422_弱趨勢期表現.py
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
bt = R.bt
yrs = R.yrs
i0 = next(i for i, d in enumerate(bt.DAYS) if d >= "2002-01-01")
r1 = np.array(bt.R1[i0:i0 + len(R.D)])
L = ["研究 422：台股弱趨勢期（2011～2019）使用者實際配置的表現", ""]
for lab, lo, hi in (("2011～2019", "2011", "2020"), ("2011～2017（主策略水下期）", "2011", "2018"), ("2020～2026", "2020", "2027")):
    m = (yrs >= lo) & (yrs < hi)
    row = []
    for nm, r in (("主策略 1.7x", R.main), ("全部（＋P＋D＋V）", R.main + R.padd + R.dadd + V.vadd), ("0050 近似", r1)):
        eq = np.cumprod(1 + r[m])
        row.append(f"{nm} {eq[-1] ** (bt.TD / m.sum()) - 1:+.1%}／{(eq / np.maximum.accumulate(eq) - 1).min():.0%}")
    L.append(f"{lab}：" + "｜".join(row))
r = R.main + R.padd + R.dadd + V.vadd
L.append("\n逐年（全部 vs 0050 近似）：" + "  ".join(f"{y}:{np.prod(1 + r[yrs == y]) - 1:+.0%}/{np.prod(1 + r1[yrs == y]) - 1:+.0%}" for y in [str(x) for x in range(2011, 2020)]))
out = "\n".join(L)
print(out)
open(os.path.join(HERE, "結果_研究422_弱趨勢期表現.txt"), "w", encoding="utf-8").write(out + "\n")
