"""研究 538：日內順勢（空手＋VIX≥18、1x 名目）的叢集風險，以及與 P／D／V 期貨加碼合計的最差 5／10／20 日
接研究 414：P／D／V 在崩跌中最差 5 日 -12.5%；日內順勢在崩跌時多半做空，看會加深還是抵銷
用法：python -X utf8 backtest/research_538_intraday_cluster_risk.py
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


def roll_worst(x, w, D):
    c = np.concatenate([[0], np.cumsum(x)]); s = c[w:] - c[:-w]; j = int(np.argmin(s))
    return s[j], D[j], D[j + w - 1]


def main():
    R = A.R
    D = [str(x)[:10] for x in R.D]
    fut = R.padd + R.dadd + A.vadd
    days = M.load_idx()
    vix = yahoo("VIX.json"); vk = np.array(sorted(vix))
    dd = [str(x)[:10] for x in S138.DAYS]; st = dict(zip(dd, S138.ST)); keys = np.array(sorted(st))
    intr = np.zeros(len(D))
    for i, d in enumerate(D):
        if d in days and st[keys[np.searchsorted(keys, d) - 1]] == 0 and vix[vk[np.searchsorted(vk, d) - 1]] >= 18:
            t = trade(days[d])
            if t:
                intr[i] = t[1] / 100
    m = np.array([d >= "2010-01-04" for d in D]); Dm = [d for d, k in zip(D, m) if k]
    out = [__doc__]
    for lab, x in (("日內 1x", intr[m]), ("P＋D＋V", fut[m]), ("P＋D＋V＋日內 1x", fut[m] + intr[m])):
        parts = []
        for w in (1, 5, 10, 20):
            v, a, b = roll_worst(x, w, Dm)
            parts.append(f"{w} 日 {v*100:+.1f}%（{a}～{b}）")
        out.append(f"  {lab:16s}：" + "｜".join(parts))
    # 崩跌段：日內與 P／D／V 同期
    for a, b in (("2011-08-01", "2011-08-31"), ("2015-08-01", "2015-08-31"), ("2020-03-01", "2020-03-31"), ("2022-01-01", "2022-10-31"), ("2025-04-01", "2025-04-30"), ("2026-11-01", "2026-11-30")):
        k = np.array([a <= d <= b for d in D])
        out.append(f"  {a[:7]}～{b[:7]}：P＋D＋V {fut[k].sum()*100:+.1f}%｜日內 {intr[k].sum()*100:+.1f}%（{(intr[k]!=0).sum()} 筆）")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究538_日內叢集風險.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
