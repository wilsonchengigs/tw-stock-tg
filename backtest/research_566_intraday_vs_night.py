"""研究 566：日內順勢（主策略空手＋VIX≥18，D30＋E）與前一晚夜盤方向（15:00→05:00，開盤前已知）的關係，2017-05～
分組：夜盤漲跌 >0.5% 且與日內訊號同向／反向／夜盤 ±0.5%
用法：python -X utf8 backtest/research_566_intraday_vs_night.py
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
    night = {}
    for r in csv.DictReader(open(os.path.join(HERE, "tx_daily_ohlc.csv"), encoding="utf-8")):
        if r["session"] == "night" and r["open"] not in ("-", "") and r["close"] not in ("-", ""):
            v = int(r["volume"] or 0)
            if r["date"] not in night or v > night[r["date"]][0]:
                night[r["date"]] = (v, float(r["close"]) / float(r["open"]) - 1)
    days = M.load_idx()
    vix = yahoo("VIX.json"); vk = np.array(sorted(vix))
    dd = [str(x)[:10] for x in S138.DAYS]; st = dict(zip(dd, S138.ST)); keys = np.array(sorted(st))
    g = {}
    for d in sorted(days):
        if d not in night:
            continue
        good = st[keys[np.searchsorted(keys, d) - 1]] == 0 and vix[vk[np.searchsorted(vk, d) - 1]] >= 18
        t = trade(days[d])
        if not t:
            continue
        nr = night[d][1]
        k = "夜盤 ±0.5%" if abs(nr) <= 0.005 else ("夜盤同向" if np.sign(nr) == t[0] else "夜盤反向")
        g.setdefault((good, k), []).append(t[1])
    out = [__doc__]
    for good in (False, True):
        out.append(f"\n===== {'空手＋VIX≥18' if good else '其他日子'} =====")
        for k in ("夜盤同向", "夜盤反向", "夜盤 ±0.5%"):
            x = np.array(g.get((good, k), []))
            if len(x) > 5:
                out.append(f"  {k}：{len(x)} 筆 每筆 {x.mean():+.3f}% t {x.mean()/(x.std(ddof=1)/np.sqrt(len(x))):+.2f} 勝率 {(x>0).mean()*100:.0f}%")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究566_日內與夜盤方向.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
