"""研究 542：日內順勢的基準時點 09:00／09:05／09:10／09:15／09:30（D30 10:30 ≥0.5%、E 09:30～12:30 第一次 ±1%）
一天 1 口、反向 0.75% 停損、13:25 出、成本 3 點；全部與「空手＋VIX≥18」
用法：python -X utf8 backtest/research_542_intraday_base_time.py
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_522_intraday_trend_robust as M
from research_514_pattern_regime import yahoo
import research_138_金字塔加碼與分段停損 as S138
from research_541_intraday_prevclose_base import run


def main():
    days = M.load_idx(); ds = sorted(days)
    vix = yahoo("VIX.json"); vk = np.array(sorted(vix))
    dd = [str(x)[:10] for x in S138.DAYS]; st = dict(zip(dd, S138.ST)); keys = np.array(sorted(st))
    good = {d: st[keys[np.searchsorted(keys, d) - 1]] == 0 and vix[vk[np.searchsorted(vk, d) - 1]] >= 18 for d in ds}
    out = [__doc__]
    for gate in (False, True):
        out.append(f"\n===== {'空手＋VIX≥18' if gate else '全部日子'} =====")
        for bm, lab in ((0, "09:00"), (5, "09:05"), (10, "09:10"), (15, "09:15"), (30, "09:30")):
            x = np.array([r for d in ds if (good[d] or not gate) and (r := run(days[d], M.at(days[d], bm), 0.005, 0.01)) is not None])
            out.append(f"  基準 {lab}：{len(x):4d} 筆 每筆 {x.mean():+.3f}% t {x.mean()/(x.std(ddof=1)/np.sqrt(len(x))):+.2f} 勝率 {(x>0).mean()*100:.0f}%")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究542_日內順勢基準時點.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
