"""研究 537：完整配置（研究 411：主策略 1.7x＋P 1x＋D 0.5x＋V 1x）再加日內順勢（主策略空手＋VIX≥18）
日內順勢：D30＋E（09:30～12:30）、一天 1 筆、反向 0.75% 停損、13:25 出、成本 3 點；名目＝資金 × k（k 0.5／1／1.5／2）
期間 2010～（加權 1 分 K 起點）；年化、回檔、逐年差；日內筆的資金報酬記在當天
用法：python -X utf8 backtest/research_537_portfolio_with_intraday.py
"""
import io, contextlib, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
with contextlib.redirect_stdout(io.StringIO()):
    import research_411_實際配置含V as A
import research_522_intraday_trend_robust as M
from research_514_pattern_regime import yahoo
import research_138_金字塔加碼與分段停損 as S138
from research_531_intraday_by_main_state import trade


def main():
    R = A.R; bt = A.bt
    base = R.main + R.padd + R.dadd + A.vadd
    D = [str(x)[:10] for x in R.D]
    days = M.load_idx()
    vix = yahoo("VIX.json"); vk = np.array(sorted(vix))
    dd = [str(x)[:10] for x in S138.DAYS]; st = dict(zip(dd, S138.ST)); keys = np.array(sorted(st))
    intr = np.zeros(len(D)); n = 0
    for i, d in enumerate(D):
        if d not in days:
            continue
        if st[keys[np.searchsorted(keys, d) - 1]] != 0 or vix[vk[np.searchsorted(vk, d) - 1]] < 18:
            continue
        t = trade(days[d])
        if t:
            intr[i] = t[1] / 100; n += 1
    m = np.array([d >= "2010-01-04" for d in D])
    out = [__doc__, f"2010～ 共 {m.sum()} 天，日內筆數 {n}（{n/ (m.sum()/bt.TD):.1f}／年）；日期範圍 {D[0]}～{D[-1]}"]
    yrs = np.array([d[:4] for d in D])
    def stat(r):
        r = r[m]; eq = np.cumprod(1 + r)
        cg = eq[-1] ** (bt.TD / len(r)) - 1; mdd = (eq / np.maximum.accumulate(eq) - 1).min()
        return cg, mdd
    b = stat(base)
    out.append(f"  現行配置（無日內）：年化 {b[0]:.1%} 回檔 {b[1]:.1%}")
    for k in (0.5, 1.0, 1.5, 2.0):
        r = base + k * intr; s = stat(r)
        yd = []
        for y in sorted(set(yrs[m])):
            mm = m & (yrs == y)
            yd.append((y, np.prod(1 + r[mm]) / np.prod(1 + base[mm]) - 1))
        worst = min(yd, key=lambda z: z[1])
        out.append(f"  ＋日內 {k}x：年化 {s[0]:.1%}（{(s[0]-b[0])*100:+.1f} 點）回檔 {s[1]:.1%}｜逐年較好 {sum(1 for y, v in yd if v>0)}/{len(yd)}，最差年 {worst[0]} {worst[1]:+.1%}")
    k = 1.0
    out.append("  逐年（1x，日內帶來的差）：" + "  ".join(f"{y}:{(np.prod(1+(base+k*intr)[m&(yrs==y)])/np.prod(1+base[m&(yrs==y)])-1)*100:+.1f}%" for y in sorted(set(yrs[m]))))
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究537_完整配置加日內.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
