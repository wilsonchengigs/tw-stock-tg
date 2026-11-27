"""研究 405：恐慌時賣賣權（研究 404 的反面：台指隱含波動長期高於實現波動）
條件：前一天台指 VIX ≥ th（30／40）且 v3 空手；賣 1 個月期（21 個交易日）價外 otm（10／15%）賣權，名目 u＝0.5x
權利金＝BS（VIX×偏斜 1.2／1.3）× 0.95（賣方吃價差）；到期以加權收盤結算；同一時間只一口
報告：筆數、每筆損益（占資金）、勝率、最差一筆、疊在 v3 2x 上的年化／回檔；2002–2012／2013～
用法：python -X utf8 backtest/research_405_恐慌賣賣權.py
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_404_保護性賣權 as R  # noqa: E402

base, PX, ST, VIX, D, e = R.base, R.PX, R.ST, R.VIX, R.D, R.e


def run(th, otm, skew, u=0.5):
    add = np.zeros(len(e))
    trades = []
    t = 1
    while t < len(e) - 1:
        if ST[t - 1] == 0 and VIX[t - 1] >= th:
            S = PX[t]
            K = S * (1 - otm)
            prem = R.put_price(S, K, VIX[t] / 100 * skew) * 0.95
            end = min(t + 21, len(e) - 1)
            pnl = u * (prem - max(K - PX[end], 0)) / S
            add[end] += pnl
            trades.append((D[t], pnl))
            t = end
        else:
            t += 1
    return add, trades


L = ["研究 405：恐慌時賣賣權（v3 空手、VIX ≥ 門檻；名目 0.5x；權利金 BS 估、賣方扣 5%）", ""]
for th in (30, 40):
    for otm, skew in ((0.10, 1.20), (0.15, 1.30)):
        add, tr = run(th, otm, skew)
        if not tr:
            continue
        v = np.array([x for _, x in tr])
        res = []
        for _, a, b in R.SEG:
            res.append(R.stats(base + add, a, b))
        worst = min(tr, key=lambda x: x[1])
        L.append(f"VIX ≥{th} 賣 {otm:.0%} 價外：{len(v)} 筆 每筆 {v.mean():+.2%} 勝率 {np.mean(v > 0):.0%} 最差 {worst[1]:+.1%}（{worst[0]}）｜疊在 v3："
                 + "｜".join(f"{c:.1%}／{m:.1%}" for c, m in res))
L.append("v3 2x：" + "｜".join(f"{c:.1%}／{m:.1%}" for c, m in (R.stats(base, a, b) for _, a, b in R.SEG)))
out = "\n".join(L)
print(out)
open(os.path.join(HERE, "結果_研究405_恐慌賣賣權.txt"), "w", encoding="utf-8").write(out + "\n")
