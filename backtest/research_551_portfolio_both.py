"""研究 551：完整配置（研究 411）＋日內順勢 1x（空手＋VIX≥18，研究 537）＋在場高 VIX 隔夜 1x（VIX≥28，研究 547）
期間 2010～（日內資料起點）；年化、回檔、逐年
用法：python -X utf8 backtest/research_551_portfolio_both.py
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
from research_544_overnight_vs_day import load


def main():
    R = A.R; bt = A.bt
    base = R.main + R.padd + R.dadd + A.vadd
    D = [str(x)[:10] for x in R.D]; idx = {d: i for i, d in enumerate(D)}
    vix = yahoo("VIX.json"); vk = np.array(sorted(vix))
    dd = [str(x)[:10] for x in S138.DAYS]; st = dict(zip(dd, S138.ST)); keys = np.array(sorted(st))
    def state(d): return st[keys[np.searchsorted(keys, d) - 1]]
    def vprev(d): return vix[vk[np.searchsorted(vk, d) - 1]]
    days = M.load_idx(); intr = np.zeros(len(D))
    for d, i in idx.items():
        if d in days and state(d) == 0 and vprev(d) >= 18:
            t = trade(days[d])
            if t:
                intr[i] = t[1] / 100
    b = load(); ds = sorted(b); night = np.zeros(len(D))
    for p, d in zip(ds, ds[1:]):
        if b[p][1] == b[d][1] and d in idx and state(p) == 1 and vprev(p) >= 28:
            night[idx[d]] += b[d][2] / b[p][3] - 1 - 3 / b[p][3]
    m = np.array([d >= "2010-01-04" for d in D]); yrs = np.array([d[:4] for d in D])
    out = [__doc__]
    for lab, r in (("現行", base), ("＋日內 1x", base + intr), ("＋隔夜 1x", base + night), ("＋日內＋隔夜", base + intr + night)):
        x = r[m]; eq = np.cumprod(1 + x)
        cg = eq[-1] ** (bt.TD / len(x)) - 1; mdd = (eq / np.maximum.accumulate(eq) - 1).min()
        ys = "  ".join(f"{y[2:]}:{(np.prod(1 + r[m & (yrs == y)]) - 1)*100:+.0f}" for y in sorted(set(yrs[m])))
        out.append(f"  {lab:12s} 年化 {cg:.1%} 回檔 {mdd:.1%}｜{ys}")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究551_配置加兩候選.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
