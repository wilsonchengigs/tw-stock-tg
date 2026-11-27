"""研究 406：備兌買權——v3 在場時每 21 個交易日賣 1 個月期價外買權（名目 u＝1x／2x），權利金 BS（VIX×0.9，買權偏斜較低）×0.95
到期以加權收盤結算（被履約就付出 max(S−K,0)）；全期／兩段；大漲年（2003、2006、2009、2017、2020、2023、2024、2025）
用法：python -X utf8 backtest/research_406_備兌買權.py
"""
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_404_保護性賣權 as R  # noqa: E402

base, PX, ST, VIX, D, e = R.base, R.PX, R.ST, R.VIX, R.D, R.e


def call_price(S, K, sig, T=21 / 252, r=0.01):
    return R.put_price(S, K, sig, T, r) + S - K * math.exp(-r * T)


def run(otm, u):
    add = np.zeros(len(e))
    t = 1
    prem_sum = pay_sum = 0.0
    while t < len(e) - 1:
        if ST[t - 1] == 1:
            S = PX[t]
            K = S * (1 + otm)
            prem = call_price(S, K, VIX[t] / 100 * 0.9) * 0.95
            end = min(t + 21, len(e) - 1)
            pay = max(PX[end] - K, 0)
            add[end] += u * (prem - pay) / S
            prem_sum += u * prem / S
            pay_sum += u * pay / S
            t = end
        else:
            t += 1
    return add, prem_sum, pay_sum


yrs = np.array([d[:4] for d in D])
UP = ("2003", "2006", "2009", "2017", "2020", "2023", "2024", "2025")
L = ["研究 406：備兌買權（v3 在場時賣 1 個月期價外買權；BS 估價）", "期間：" + "｜".join(s[0] for s in R.SEG)]
L.append("v3 2x：" + "｜".join(f"{c:.1%}／{m:.1%}" for c, m in (R.stats(base, a, b) for _, a, b in R.SEG)))
for otm in (0.05, 0.10):
    for u in (1.0, 2.0):
        add, ps, pp = run(otm, u)
        r = base + add
        L.append(f"賣 {otm:.0%} 價外 {u}x：" + "｜".join(f"{c:.1%}／{m:.1%}" for c, m in (R.stats(r, a, b) for _, a, b in R.SEG))
                 + f"｜收權利金 {ps:.0%}、被履約付出 {pp:.0%}")
        if otm == 0.05 and u == 2.0:
            L.append("   大漲年 v3→賣買權：" + "  ".join(f"{y}:{np.prod(1 + base[yrs == y]) - 1:+.0%}→{np.prod(1 + r[yrs == y]) - 1:+.0%}" for y in UP))
out = "\n".join(L)
print(out)
open(os.path.join(HERE, "結果_研究406_備兌買權.txt"), "w", encoding="utf-8").write(out + "\n")
