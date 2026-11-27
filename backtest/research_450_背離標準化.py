"""研究 450：台美背離改用波動標準化門檻（背離 ÷ 台股近 20 日日報酬標準差×√20）vs 固定 -10%
事件去叢集 20 天；結果＝研究 204b 的同跌幅超額（5 日）；z 門檻 -1.5／-2／-2.5／-3；12 檢定家族不另做（描述性比較）
用法：python -X utf8 backtest/research_450_背離標準化.py
"""
import io
import contextlib
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
with contextlib.redirect_stdout(io.StringIO()):
    import research_206_台美背離延伸 as R
TW, N = R.TW, R.N
gap = R.GAP["GSPC"]
r1 = np.r_[0, TW[1:] / TW[:-1] - 1]
vol20 = np.array([r1[max(1, k - 19):k + 1].std() * np.sqrt(20) if k >= 20 else np.nan for k in range(N)])
z = gap / vol20
EX = R.EX[("GSPC", 5)]
F5 = R.F[5]
L = ["研究 450：台美背離 固定門檻 vs 波動標準化門檻（5 日同跌幅超額；去叢集 20 天）", ""]


def show(lab, cond):
    ev = R.events(cond)
    x = EX[ev]
    x = x[~np.isnan(x)]
    f = F5[ev]
    f = f[~np.isnan(f)]
    t = x.mean() / (x.std() / np.sqrt(len(x))) if len(x) > 2 else np.nan
    seg = [np.nanmean([EX[k] for k in ev if lo <= R.DAYS[k] < hi]) for lo, hi in (("1998", "2013"), ("2013", "2099"))]
    L.append(f"{lab}：{len(ev)} 次 原始 {f.mean():+.2%} 超額 {x.mean():+.2%}（t {t:+.1f}）勝率 {np.mean(f > 0):.0%}  兩段超額 {seg[0]:+.2%}／{seg[1]:+.2%}")


show("固定 ≤-10%（現行）", gap <= -0.10)
for k in (1.5, 2.0, 2.5, 3.0):
    show(f"標準化 z ≤-{k}", z <= -k)
show("固定 ≤-10% 且 z ≤-1.5", (gap <= -0.10) & (z <= -1.5))
L.append(f"\n現況 {R.DAYS[-1]}：背離 {gap[-1]:+.1%}、20 日波動 {vol20[-1]:.1%}、z {z[-1]:+.2f}")
out = "\n".join(L)
print(out)
open(os.path.join(HERE, "結果_研究450_背離標準化.txt"), "w", encoding="utf-8").write(out + "\n")
