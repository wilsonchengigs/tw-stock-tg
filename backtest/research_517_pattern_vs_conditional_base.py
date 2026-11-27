"""研究 517：VIX≥18 盤中型態 vs「同條件日子、同一分鐘直接進場」
研究 512 發現型態對「開低日同分鐘直接空」只多 +37 點。這裡把基準縮到同樣條件（前晚 VIX≥18、同跳空方向 >0.3%），
看型態本身還多出多少；若多出 ≈0，代表賺的是「高 VIX 跳空日盤中偏弱」，型態只是進場時點，可用更簡單的規則
基準：同條件所有日子從同一分鐘收盤抱到 13:30 的平均（做空取負）；另做「同條件日子 09:30 直接進」的簡單規則
用法：python -X utf8 backtest/research_517_pattern_vs_conditional_base.py
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_511_higher_low as R
from research_514_pattern_regime import yahoo


def t(x):
    x = np.asarray(x); return x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))


def main():
    gaps = R.tx_gaps(); days = R.load_days(); adr = R.adr20(days)
    vix = yahoo("VIX.json"); vk = np.array(sorted(vix))

    def vprev(d):
        i = np.searchsorted(vk, d) - 1
        return vix[vk[i]] if i >= 0 else 0
    out = [__doc__]
    for side, name, gf in ((-1, "開低做空", lambda g: g < -0.003), (-1, "開高做空", lambda g: g > 0.003), (1, "開高做多", lambda g: g > 0.003)):
        cond = [d for d in days if d in gaps and d in adr and gf(gaps[d]) and vprev(d) >= 18]
        # 條件日的同分鐘基準
        acc = np.zeros(271); n = np.zeros(271)
        for d in cond:
            a = days[d]; m = a[:, 0].astype(int); c = a[:, 3]; ok = (m >= 0) & (m <= 270)
            acc[m[ok]] += (c[-1] / c[ok] - 1) * 100; n[m[ok]] += 1
        base = acc / np.maximum(n, 1)
        S = [s for s in R.setups(days, gaps, adr, side, "相對", 0.25, "E2") if s["minute"] <= 180 and gf(s["gap"]) and vprev(s["day"]) >= 18]
        p = np.array([s["pnl"][("無", None)] for s in S])
        ex = p - np.array([side * base[s["minute"]] for s in S])
        ins = np.array([s["day"] < R.SPLIT for s in S])
        out.append(f"\n===== {name}（條件日 {len(cond)} 天，型態 {len(S)} 筆）")
        out.append(f"  型態：平均 {p.mean():+.3f}% t {t(p):+.2f}｜扣條件日同分鐘基準 {ex.mean():+.3f}%（≈{ex.mean()*390:+.0f} 點）t {t(ex):+.2f}｜內 {ex[ins].mean():+.3f} 外 {ex[~ins].mean():+.3f}")
        # 不看型態的簡單規則：條件日某時點直接進場抱到收盤
        for hm, mm in (("09:05", 5), ("09:30", 30), ("10:00", 60), ("10:30", 90)):
            r = []
            for d in cond:
                a = days[d]; m = a[:, 0].astype(int); c = a[:, 3]
                j = np.searchsorted(m, mm)
                if j < len(c) - 1:
                    r.append(side * (c[-1] / c[j] - 1) * 100 - 3 / c[j] * 100)
            r = np.array(r)
            out.append(f"  簡單規則 {hm} 直接進：{len(r)} 天 平均 {r.mean():+.3f}%（≈{r.mean()*390:+.0f} 點）t {t(r):+.2f} 勝率 {(r>0).mean()*100:.0f}%")
        # 有型態的日子 vs 沒型態的日子（同條件），從 10:00 抱到收盤
        pd_ = set(s["day"] for s in S)
        for lab, ds in (("有型態的日子", [d for d in cond if d in pd_]), ("沒型態的日子", [d for d in cond if d not in pd_])):
            r = []
            for d in ds:
                a = days[d]; m = a[:, 0].astype(int); c = a[:, 3]; j = np.searchsorted(m, 60)
                r.append(side * (c[-1] / c[j] - 1) * 100)
            r = np.array(r)
            out.append(f"  {lab} 10:00→收盤：{len(r)} 天 平均 {r.mean():+.3f}% t {t(r):+.2f}")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究517_型態對條件基準.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
