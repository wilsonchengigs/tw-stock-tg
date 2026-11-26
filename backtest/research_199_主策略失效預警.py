"""研究 199：主策略失效預警——v3 滾動績效多差才算「統計上不正常」（使用者擔心市場結構改變）

做法：
- v3 每日淨值（2002～，模型價）；對照 1x＝加權＋3% 配息（≈0050）
- 每月底算滾動 12／24／36 個月：v3 年化、v3 − 1x 年化（超額）
- 「正常範圍」：v3 日報酬做平穩區塊拔靴（平均區塊 120 天、2,000 條）得到「策略照歷史方式運作時」滾動 36 月超額的分布 → 1%／2.5%／5% 分位當門檻
  （拔靴保留 v3 與 1x 的同日配對，超額的分布才對）
- 回頭檢查：歷史上每月的滾動 36 月超額，有幾個月低於門檻（誤報）——特別是 2011–2017 長期水下
- 現況（最新月底）
用法：python -X utf8 backtest/research_199_主策略失效預警.py
"""
import importlib.util
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("v3", os.path.join(HERE, "strategy_v3.py"))
V3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V3)
bt = V3.bt
TD = bt.TD


def main():
    _, _, e = V3.run("2002-01-01", "2026-12-31", curve=True)
    i0 = next(i for i, d in enumerate(bt.DAYS) if d >= "2002-01-01")
    days = bt.DAYS[i0:i0 + len(e)]
    rs = np.array([0.0] + [e[k] / e[k - 1] - 1 for k in range(1, len(e))])
    r1 = np.array([bt.R1[i0 + k] if k else 0.0 for k in range(len(e))])
    me = [k for k in range(len(days)) if k == len(days) - 1 or days[k][:7] != days[k + 1][:7]]
    L = ["研究 199：主策略失效預警（v3 模型價 2002～；超額＝v3 年化 − 1x 加權含息年化）"]

    def roll(a, b, months):
        out = {}
        for j, k in enumerate(me):
            if j < months:
                continue
            k0 = me[j - months]
            ga = np.prod(1 + a[k0 + 1:k + 1]) ** (12 / months) - 1
            gb = np.prod(1 + b[k0 + 1:k + 1]) ** (12 / months) - 1
            out[days[k][:7]] = (ga, ga - gb)
        return out

    hist = {m: roll(rs, r1, m) for m in (12, 24, 36)}
    for m in (12, 24, 36):
        v = np.array([x[0] for x in hist[m].values()])
        ex = np.array([x[1] for x in hist[m].values()])
        L.append(f"\n【歷史 滾動 {m} 個月】{len(v)} 個月底")
        L.append(f"  v3 年化：最差 {v.min():+.1%}、5% 分位 {np.percentile(v, 5):+.1%}、中位 {np.median(v):+.1%}；低於 0 的比例 {np.mean(v < 0):.0%}")
        L.append(f"  超額：最差 {ex.min():+.1%}、5% 分位 {np.percentile(ex, 5):+.1%}、中位 {np.median(ex):+.1%}；超額 <0 的比例 {np.mean(ex < 0):.0%}")
        worst = sorted(hist[m].items(), key=lambda kv: kv[1][1])[:3]
        L.append("  超額最差的月底：" + "、".join(f"{k} {x[1]:+.1%}（v3 {x[0]:+.1%}）" for k, x in worst))

    # 區塊拔靴：36 個月超額的分布
    rng = np.random.default_rng(199)
    n = len(rs)
    T = 36 * 21
    sims_ex, sims_v = [], []
    for _ in range(2000):
        idx, pos = [], int(rng.integers(1, n))
        while len(idx) < T:
            idx.append(pos)
            pos = pos + 1 if (rng.random() > 1 / 120 and pos + 1 < n) else int(rng.integers(1, n))
        idx = np.array(idx)
        ga = np.prod(1 + rs[idx]) ** (TD / T) - 1
        gb = np.prod(1 + r1[idx]) ** (TD / T) - 1
        sims_v.append(ga)
        sims_ex.append(ga - gb)
    sims_ex, sims_v = np.array(sims_ex), np.array(sims_v)
    th = {q: np.percentile(sims_ex, q) for q in (1, 2.5, 5)}
    thv = {q: np.percentile(sims_v, q) for q in (1, 2.5, 5)}
    L.append("\n【拔靴（策略照歷史方式運作）36 個月】")
    L.append("  超額門檻：" + "、".join(f"{q}% 分位 {v:+.1%}" for q, v in th.items()) + f"；中位 {np.median(sims_ex):+.1%}")
    L.append("  v3 年化門檻：" + "、".join(f"{q}% 分位 {v:+.1%}" for q, v in thv.items()) + f"；中位 {np.median(sims_v):+.1%}")
    for q, t in th.items():
        hit = [k for k, x in hist[36].items() if x[1] < t]
        L.append(f"  歷史月底 36 月超額 < {q}% 門檻（{t:+.1%}）：{len(hit)}/{len(hist[36])} 個月" + (f"，{hit[0]}～{hit[-1]}" if hit else ""))
    for q, t in thv.items():
        hit = [k for k, x in hist[36].items() if x[0] < t]
        L.append(f"  歷史月底 36 月 v3 年化 < {q}% 門檻（{t:+.1%}）：{len(hit)}/{len(hist[36])} 個月" + (f"，{hit[0]}～{hit[-1]}" if hit else ""))
    # 2011–2017 水下期間的滾動值
    L.append("\n2011–2017 長期水下（研究 87：2011-01 → 2017-05）期間 36 月超額／v3 年化（每半年）：")
    for k, x in hist[36].items():
        if "2011-06" <= k <= "2017-12" and k[5:] in ("06", "12"):
            L.append(f"  {k}：超額 {x[1]:+.1%}、v3 {x[0]:+.1%}")
    last = list(hist[36].items())[-1]
    L.append(f"\n現況 {last[0]}：36 月 v3 {last[1][0]:+.1%}、超額 {last[1][1]:+.1%}；"
             f"24 月 {list(hist[24].values())[-1][0]:+.1%}／{list(hist[24].values())[-1][1]:+.1%}；"
             f"12 月 {list(hist[12].values())[-1][0]:+.1%}／{list(hist[12].values())[-1][1]:+.1%}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究199_主策略失效預警.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
