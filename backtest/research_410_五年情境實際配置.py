"""研究 410：5 年資產情境（使用者實際配置：主策略 1.7x＋P 1x＋D 0.5x，研究 407 的 2002～ 日報酬）
區塊拔靴 10,000 條（平均區塊 60 天）；現有 100 萬、每年年底存 100 萬（投入 600 萬）；另做「只抽 2002～2017」保守版
用法：python -X utf8 backtest/research_410_五年情境實際配置.py
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
    import research_242_五年資產情境 as B  # noqa: E402

r = R.main + R.padd + R.dadd
cons = r[R.yrs < "2018"]
L = ["研究 410：5 年資產情境（實際配置：主策略 1.7x＋P 1x＋D 0.5x；現有 100 萬、每年年底存 100 萬）", ""]
for lab, x in (("2002～2026 抽樣", r), ("2002～2017 抽樣（保守）", cons)):
    e = np.prod(1 + x) ** (R.bt.TD / len(x)) - 1
    w, mdd = B.wealth(B.boot(x, seed=410))
    q = np.quantile(w, [0.1, 0.25, 0.5, 0.75, 0.9])
    L.append(f"【{lab}】歷史年化 {e:.1%}")
    L.append(f"  5 年後：10 分位 {q[0]:,.0f} 萬｜25 分位 {q[1]:,.0f}｜中位 {q[2]:,.0f}｜75 分位 {q[3]:,.0f}｜90 分位 {q[4]:,.0f} 萬")
    L.append(f"  低於投入 600 萬 {np.mean(w < 600):.0%}；期間帳面最大回檔 中位 {np.median(mdd):.0%}、最差 10% ≤ {np.quantile(mdd, 0.1):.0%}")
out = "\n".join(L)
print(out)
open(os.path.join(HERE, "結果_研究410_五年情境實際配置.txt"), "w", encoding="utf-8").write(out + "\n")
