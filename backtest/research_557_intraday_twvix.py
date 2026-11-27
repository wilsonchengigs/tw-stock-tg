"""研究 557：日內順勢（主策略空手＋VIX 開關）改用台指 VIX（前一交易日收盤）
D30＋E（09:30～12:30）、反向 0.75% 停損、13:25 出；台 VIX 門檻 18～28 vs 美國 VIX≥18
用法：python -X utf8 backtest/research_557_intraday_twvix.py
"""
import os, sys, csv
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_522_intraday_trend_robust as M
from research_514_pattern_regime import yahoo
import research_138_金字塔加碼與分段停損 as S138
from research_531_intraday_by_main_state import trade


def main():
    days = M.load_idx(); ds = sorted(days)
    us = yahoo("VIX.json"); uk = np.array(sorted(us))
    tw = {r["date"]: float(r["vix"]) for r in csv.DictReader(open(os.path.join(HERE, "vixtwn.csv"), encoding="utf-8")) if r["vix"] not in ("", "-")}
    tk = np.array(sorted(tw))
    dd = [str(x)[:10] for x in S138.DAYS]; st = dict(zip(dd, S138.ST)); keys = np.array(sorted(st))
    rows = []
    for d in ds:
        t = trade(days[d])
        if not t:
            continue
        k = np.searchsorted(tk, d) - 1
        if k < 0:
            continue
        rows.append((d, st[keys[np.searchsorted(keys, d) - 1]], us[uk[np.searchsorted(uk, d) - 1]], tw[tk[k]], t[1]))
    s = np.array([r[1] for r in rows]); u = np.array([r[2] for r in rows]); w = np.array([r[3] for r in rows]); x = np.array([r[4] for r in rows])
    d_ = np.array([r[0] for r in rows])
    out = [__doc__]
    for lab, m in [("空手＋美 VIX≥18", (s == 0) & (u >= 18))] + [(f"空手＋台 VIX≥{th}", (s == 0) & (w >= th)) for th in (18, 20, 22, 25, 28)]:
        out.append(f"  {lab:14s} {m.sum():4d} 筆（{m.sum()/17:.0f}/年）每筆 {x[m].mean():+.3f}% t {x[m].mean()/(x[m].std(ddof=1)/np.sqrt(m.sum())):+.2f} 勝率 {(x[m]>0).mean()*100:.0f}%｜2010–17 {x[m & (d_<'2018')].mean():+.3f} 2018～ {x[m & (d_>='2018')].mean():+.3f}｜其餘空手日 {x[(s==0)&~m].mean():+.3f}%")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究557_日內台指VIX.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
