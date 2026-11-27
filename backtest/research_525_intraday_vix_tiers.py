"""研究 525：日內順勢 D30+E（一天最多 1 口、取最早訊號）依前一晚 VIX 分級
VIX 分級 <15／15～18／18～22／22～28／≥28；每級每筆報酬%、標準差、夏普（每筆）、全凱利槓桿（均值÷變異數，名目÷資金的倍數）
13:25 出（保守）與 13:30；兩段（2010～2017／2018～）
用法：python -X utf8 backtest/research_525_intraday_vix_tiers.py
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_522_intraday_trend_robust as M
from research_514_pattern_regime import yahoo


def merged(days, cm):
    res = {}
    for d, a in days.items():
        o = M.at(a, 5); cand = []
        tr = M.at(a, 90) / o - 1
        if abs(tr) >= 0.005:
            cand.append((90, 1 if tr > 0 else -1, M.at(a, 90)))
        for mm, cl in a:
            if 6 <= mm <= 240 and abs(cl / o - 1) >= 0.01:
                cand.append((int(mm), 1 if cl > o else -1, cl)); break
        if cand:
            mm, s, e = min(cand)
            res[d] = s * (M.at(a, cm) / e - 1) - 3 / e
    return res


def main():
    days = M.load_idx()
    vix = yahoo("VIX.json"); vk = np.array(sorted(vix))
    v = {d: vix[vk[np.searchsorted(vk, d) - 1]] for d in days}
    out = [__doc__]
    bins = [(0, 15), (15, 18), (18, 22), (22, 28), (28, 999)]
    for cm, lab in ((265, "13:25"), (270, "13:30")):
        R = merged(days, cm)
        out.append(f"\n===== {lab} 出 =====")
        for lo, hi in bins:
            for seg, f in (("全期", lambda d: True), ("2010～17", lambda d: d < "2018"), ("2018～", lambda d: d >= "2018")):
                x = np.array([r for d, r in R.items() if lo <= v[d] < hi and f(d)]) * 100
                if len(x) < 10:
                    continue
                out.append(f"  VIX {lo:>2}～{hi if hi<999 else '':<3} {seg:8s} {len(x):4d} 筆 每筆 {x.mean():+.3f}% 標準差 {x.std():.2f}% 每筆夏普 {x.mean()/x.std():+.3f} 全凱利槓桿 {x.mean()/x.var()*100:+.1f} 倍 勝率 {(x>0).mean()*100:.0f}%")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究525_日內順勢VIX分級.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
