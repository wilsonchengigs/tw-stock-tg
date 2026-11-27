"""研究 404：保護性賣權——v3 在場時每 21 個交易日買 1 個月期價外賣權（保護 2x 名目）
權利金：Black-Scholes（r＝1%），波動率＝台指 VIX（vixtwn.csv）× 偏斜加成（5% 價外 ×1.10、10% 價外 ×1.20），再加 5% 買賣價差；到期以加權收盤結算
只在 v3 在場時買（每段在場期第一天開始、每 21 天換）；v3 出場時賣權留到到期（保守：不提前賣回）
比較：v3 2x、＋5% 價外、＋10% 價外；全期 2002～、兩段、崩跌年（2008、2011、2015、2018、2020、2022、2026）
用法：python -X utf8 backtest/research_404_保護性賣權.py
"""
import csv
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import strategy_v3 as V  # noqa: E402
import research_138_金字塔加碼與分段停損 as R138  # noqa: E402

bt = V.bt
_, _, e = V.run("2002-01-01", bt.DAYS[-1], curve=True)
e = np.asarray(e)
i0 = next(i for i, d in enumerate(bt.DAYS) if d >= "2002-01-01")
D = bt.DAYS[i0:i0 + len(e)]
base = np.r_[0.0, e[1:] / e[:-1] - 1]
PX = np.array(bt.PX[i0:i0 + len(e)])
ST = np.array(R138.ST[i0:i0 + len(e)])
vx = {r["date"]: float(r["vix"]) for r in csv.DictReader(open(os.path.join(HERE, "vixtwn.csv")))}
VIX = np.array([vx.get(d, np.nan) for d in D])
for k in range(1, len(VIX)):
    if np.isnan(VIX[k]):
        VIX[k] = VIX[k - 1]


def put_price(S, K, sig, T=21 / 252, r=0.01):
    d1 = (math.log(S / K) + (r + sig * sig / 2) * T) / (sig * math.sqrt(T))
    d2 = d1 - sig * math.sqrt(T)
    N = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))  # noqa: E731
    return K * math.exp(-r * T) * N(-d2) - S * N(-d1)


def hedge(otm, skew):
    """回傳每日加到資金的報酬（權利金在買進日扣、到期日加回內含價值），名目＝2x"""
    add = np.zeros(len(e))
    t = 1
    cost_sum = pay_sum = 0.0
    n = 0
    while t < len(e) - 1:
        if ST[t - 1] == 1 and not np.isnan(VIX[t]):
            S = PX[t]
            K = S * (1 - otm)
            prem = put_price(S, K, VIX[t] / 100 * skew) * 1.05
            end = min(t + 21, len(e) - 1)
            pay = max(K - PX[end], 0)
            add[t] -= 2 * prem / S
            add[end] += 2 * pay / S
            cost_sum += 2 * prem / S
            pay_sum += 2 * pay / S
            n += 1
            t = end
        else:
            t += 1
    return add, cost_sum, pay_sum, n


def stats(r, a, b):
    m = np.array([a <= d <= b for d in D])
    x = r[m]
    eq = np.cumprod(1 + x)
    return eq[-1] ** (bt.TD / len(x)) - 1, (eq / np.maximum.accumulate(eq) - 1).min()


SEG = (("2002～", "2002-01-01", "2099"), ("2002–2012", "2002-01-01", "2012-12-31"), ("2013～", "2013-01-01", "2099"))
yrs = np.array([d[:4] for d in D])
L = ["研究 404：保護性賣權（權利金用台指 VIX 套 BS 估計；名目 2x；到期結算）", "期間：" + "｜".join(s[0] for s in SEG)]
L.append("v3 2x：" + "｜".join(f"{c:.1%}／{m:.1%}" for c, m in (stats(base, a, b) for _, a, b in SEG)))
CR = ("2008", "2011", "2015", "2018", "2020", "2022", "2026")
for otm, skew in ((0.05, 1.10), (0.10, 1.20)):
    add, cost, pay, n = hedge(otm, skew)
    r = base + add
    L.append(f"＋{otm:.0%} 價外賣權：" + "｜".join(f"{c:.1%}／{m:.1%}" for c, m in (stats(r, a, b) for _, a, b in SEG))
             + f"｜{n} 次、總權利金 {cost:.0%}、總理賠 {pay:.0%}（理賠／權利金 {pay / cost:.2f}）")
    L.append("   崩跌年 v3→加保險：" + "  ".join(f"{y}:{np.prod(1 + base[yrs == y]) - 1:+.0%}→{np.prod(1 + r[yrs == y]) - 1:+.0%}" for y in CR))
out = "\n".join(L)
print(out)
open(os.path.join(HERE, "結果_研究404_保護性賣權.txt"), "w", encoding="utf-8").write(out + "\n")
