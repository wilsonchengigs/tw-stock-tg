"""研究 568：日內順勢（主策略空手＋VIX≥18）第一筆被 0.75% 停損後，反手第二筆
第二筆：停損後到 12:30 前，價格比 09:05 反方向 ≥1% → 反手進、同樣 0.75% 停損、13:25 出；另版：停損後同方向再破 ±1% 重進
用法：python -X utf8 backtest/research_568_intraday_reentry.py
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_522_intraday_trend_robust as M
from research_514_pattern_regime import yahoo
import research_138_金字塔加碼與分段停損 as S138
CM = 265


def leg(mins, cl, mm, s, e):
    lvl = e * (1 - s * 0.0075)
    hit = np.nonzero((mins > mm) & (mins <= CM) & (s * (cl - lvl) <= 0))[0]
    if len(hit):
        return s * (cl[hit[0]] / e - 1) - 5 / e, int(mins[hit[0]])
    return s * (cl[np.searchsorted(mins, CM)] / e - 1) - 3 / e, None


def run(a):
    o = M.at(a, 5); mins = a[:, 0].astype(int); cl = a[:, 1]; cand = []
    tr = M.at(a, 90) / o - 1
    if abs(tr) >= 0.005:
        cand.append((90, 1 if tr > 0 else -1))
    idx = np.nonzero((mins >= 30) & (mins <= 210) & (np.abs(cl / o - 1) >= 0.01))[0]
    if len(idx):
        cand.append((int(mins[idx[0]]), 1 if cl[idx[0]] > o else -1))
    if not cand:
        return None
    mm, s = min(cand); r1, stop_m = leg(mins, cl, mm, s, M.at(a, mm))
    rev = same = None
    if stop_m is not None:
        for sd, key in ((-s, "rev"), (s, "same")):
            j = np.nonzero((mins > stop_m) & (mins <= 210) & (sd * (cl / o - 1) >= 0.01))[0]
            if len(j):
                r2, _ = leg(mins, cl, int(mins[j[0]]), sd, cl[j[0]])
                if key == "rev": rev = r2
                else: same = r2
    return r1, stop_m is not None, rev, same


def main():
    days = M.load_idx(); ds = sorted(days)
    vix = yahoo("VIX.json"); vk = np.array(sorted(vix))
    dd = [str(x)[:10] for x in S138.DAYS]; st = dict(zip(dd, S138.ST)); keys = np.array(sorted(st))
    R = [r for d in ds if st[keys[np.searchsorted(keys, d) - 1]] == 0 and vix[vk[np.searchsorted(vk, d) - 1]] >= 18 and (r := run(days[d]))]
    out = [__doc__]
    r1 = np.array([r[0] for r in R]) * 100; stopped = np.array([r[1] for r in R])
    out.append(f"第一筆 {len(R)} 筆 每筆 {r1.mean():+.3f}%；被停損 {stopped.sum()} 筆（{stopped.mean()*100:.0f}%）")
    for k, lab in ((2, "反手"), (3, "同向重進")):
        x = np.array([r[k] for r in R if r[k] is not None]) * 100
        if len(x) > 3:
            out.append(f"  停損後{lab}：{len(x)} 筆 每筆 {x.mean():+.3f}% t {x.mean()/(x.std(ddof=1)/np.sqrt(len(x))):+.2f} 勝率 {(x>0).mean()*100:.0f}%")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究568_日內停損後再進.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
