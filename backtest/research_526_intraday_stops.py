"""研究 526：日內順勢 D30+E（VIX≥18、一天最多 1 口取最早訊號）的停損
停損：無／回到 09:05 開盤價／進場價反向 0.5%／0.75%／1%；用 1 分 K 收盤判斷（觸發那根收盤出，保守多扣 2 點滑價）
出場 13:25；全部日子與 VIX≥18；每筆、t、最差單筆、最大回檔（%累加）、正的年
用法：python -X utf8 backtest/research_526_intraday_stops.py
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_522_intraday_trend_robust as M
from research_514_pattern_regime import yahoo
CM = 265


def trade(a, stop):
    o = M.at(a, 5); cand = []
    tr = M.at(a, 90) / o - 1
    if abs(tr) >= 0.005:
        cand.append((90, 1 if tr > 0 else -1))
    for mm, cl in a:
        if 6 <= mm <= 240 and abs(cl / o - 1) >= 0.01:
            cand.append((int(mm), 1 if cl > o else -1)); break
    if not cand:
        return None
    mm, s = min(cand); e = M.at(a, mm)
    if stop == "無":
        lvl = None
    elif stop == "開盤價":
        lvl = o
    else:
        lvl = e * (1 - s * stop)
    for m2, cl in a:
        if m2 <= mm or m2 > CM:
            continue
        if lvl is not None and s * (cl - lvl) <= 0:
            return s * (cl / e - 1) - 5 / e
    return s * (M.at(a, CM) / e - 1) - 3 / e


def main():
    days = M.load_idx(); ds = sorted(days)
    vix = yahoo("VIX.json"); vk = np.array(sorted(vix))
    vhi = {d: vix[vk[np.searchsorted(vk, d) - 1]] >= 18 for d in ds}
    out = [__doc__]
    for gate in (True, False):
        out.append(f"\n===== {'VIX≥18' if gate else '全部日子'} =====")
        for st in ("無", "開盤價", 0.005, 0.0075, 0.01):
            lst = [(d, r) for d in ds if (vhi[d] or not gate) and (r := trade(days[d], st)) is not None]
            x = np.array([r for _, r in lst]) * 100
            eq = np.cumsum(x); dd = (eq - np.maximum.accumulate(np.concatenate([[0], eq]))[1:]).min()
            yrs = {}
            for d, r in lst:
                yrs[d[:4]] = yrs.get(d[:4], 0) + r
            lab = st if isinstance(st, str) else f"反向 {st*100:.2f}%"
            out.append(f"  停損 {lab:10s} {len(x)} 筆 每筆 {x.mean():+.3f}% t {x.mean()/(x.std(ddof=1)/np.sqrt(len(x))):+.2f} 勝率 {(x>0).mean()*100:.0f}% 最差 {x.min():+.2f}% 最大回檔 {dd:.1f}%（累加） 正的年 {sum(1 for v in yrs.values() if v>0)}/{len(yrs)}")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究526_日內順勢停損.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
