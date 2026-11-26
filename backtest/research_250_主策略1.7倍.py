"""研究 250：使用者實際配置 85% 00631L（約 1.7x）＋15% 現金 vs 研究基準 2x：v3 全期／兩段／真實價的年化與回檔
用法：python -X utf8 backtest/research_250_主策略1.7倍.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import strategy_v3 as V  # noqa: E402

L = ["研究 250：主策略 v3 槓桿 2x vs 1.7x（85% 00631L）vs 1.5x（年化／最大回檔）", "期間｜2x｜1.7x｜1.5x"]
for lab, (a, b), real in (("2002～2026", V.PER[0], False), ("2002～2012", V.PER[1], False), ("2013～2026", V.PER[2], False), ("真實價 2015-09～", V.REAL, True)):
    row = []
    for lev in (2.0, 1.7, 1.5):
        cg, mdd = V.run(a, b, real=real, lev=lev)[:2]
        row.append(f"{cg:.1%}／{mdd:.1%}")
    L.append(f"{lab}｜" + "｜".join(row))
out = "\n".join(L)
print(out)
open(os.path.join(HERE, "結果_研究250_主策略1.7倍.txt"), "w", encoding="utf-8").write(out + "\n")
