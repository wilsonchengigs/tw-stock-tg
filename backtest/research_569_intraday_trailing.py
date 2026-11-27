"""研究 569：日內順勢（主策略空手＋VIX≥18）出場改良
A 原版：反向 0.75% 停損、13:25 出
B 獲利達 +x%（0.75／1／1.5）後停損移到成本
C 移動停利：從進場後最佳價回落 y%（0.75／1／1.5）出
用 1 分 K 收盤判斷；停損出多扣 2 點
用法：python -X utf8 backtest/research_569_intraday_trailing.py
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_522_intraday_trend_robust as M
from research_514_pattern_regime import yahoo
import research_138_金字塔加碼與分段停損 as S138
CM = 265


def run(a, mode, par):
    o = M.at(a, 5); mins = a[:, 0].astype(int); cl = a[:, 1]; cand = []
    tr = M.at(a, 90) / o - 1
    if abs(tr) >= 0.005:
        cand.append((90, 1 if tr > 0 else -1))
    idx = np.nonzero((mins >= 30) & (mins <= 210) & (np.abs(cl / o - 1) >= 0.01))[0]
    if len(idx):
        cand.append((int(mins[idx[0]]), 1 if cl[idx[0]] > o else -1))
    if not cand:
        return None
    mm, s = min(cand); e = M.at(a, mm); stop = e * (1 - s * 0.0075); best = e
    for m2, c in zip(mins, cl):
        if m2 <= mm or m2 > CM:
            continue
        if s * (c - best) > 0:
            best = c
        if mode == "B" and s * (best / e - 1) >= par:
            stop = e if s * (e - stop) > 0 else stop
        if mode == "C":
            tstop = best * (1 - s * par)
            if s * (tstop - stop) > 0:
                stop = tstop
        if s * (c - stop) <= 0:
            return (s * (c / e - 1) - 5 / e) * 100
    return (s * (M.at(a, CM) / e - 1) - 3 / e) * 100


def main():
    days = M.load_idx(); ds = sorted(days)
    vix = yahoo("VIX.json"); vk = np.array(sorted(vix))
    dd = [str(x)[:10] for x in S138.DAYS]; st = dict(zip(dd, S138.ST)); keys = np.array(sorted(st))
    good = [d for d in ds if st[keys[np.searchsorted(keys, d) - 1]] == 0 and vix[vk[np.searchsorted(vk, d) - 1]] >= 18]
    out = [__doc__]
    for mode, pars in (("A", [None]), ("B", [0.0075, 0.01, 0.015]), ("C", [0.0075, 0.01, 0.015])):
        for par in pars:
            x = np.array([r for d in good if (r := run(days[d], mode, par)) is not None])
            out.append(f"  {mode} {'' if par is None else f'{par*100:.2f}%'}：{len(x)} 筆 每筆 {x.mean():+.3f}% t {x.mean()/(x.std(ddof=1)/np.sqrt(len(x))):+.2f} 勝率 {(x>0).mean()*100:.0f}% 最差 {x.min():+.2f}% 標準差 {x.std():.2f}%")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究569_日內移動停利.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
