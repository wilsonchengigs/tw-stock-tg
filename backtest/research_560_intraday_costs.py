"""研究 560：日內順勢最終版（主策略空手＋VIX≥18，D30＋E 09:30～12:30，反向 0.75% 停損，13:25 出）對成本與停損滑價的敏感度
成本（來回）3／5／8 點；停損觸發後再多滑 0／5／10 點；全期 2010～ 與 2024～
用法：python -X utf8 backtest/research_560_intraday_costs.py
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_522_intraday_trend_robust as M
from research_514_pattern_regime import yahoo
import research_138_金字塔加碼與分段停損 as S138
CM = 265


def trade(a, cost, slip):
    o = M.at(a, 5); mins = a[:, 0].astype(int); cl = a[:, 1]; cand = []
    tr = M.at(a, 90) / o - 1
    if abs(tr) >= 0.005:
        cand.append((90, 1 if tr > 0 else -1))
    idx = np.nonzero((mins >= 30) & (mins <= 210) & (np.abs(cl / o - 1) >= 0.01))[0]
    if len(idx):
        cand.append((int(mins[idx[0]]), 1 if cl[idx[0]] > o else -1))
    if not cand:
        return None
    mm, s = min(cand); e = M.at(a, mm); lvl = e * (1 - s * 0.0075)
    hit = np.nonzero((mins > mm) & (mins <= CM) & (s * (cl - lvl) <= 0))[0]
    if len(hit):
        return (s * (cl[hit[0]] / e - 1) - (cost + slip) / e) * 100
    return (s * (M.at(a, CM) / e - 1) - cost / e) * 100


def main():
    days = M.load_idx(); ds = sorted(days)
    vix = yahoo("VIX.json"); vk = np.array(sorted(vix))
    dd = [str(x)[:10] for x in S138.DAYS]; st = dict(zip(dd, S138.ST)); keys = np.array(sorted(st))
    good = [d for d in ds if st[keys[np.searchsorted(keys, d) - 1]] == 0 and vix[vk[np.searchsorted(vk, d) - 1]] >= 18]
    out = [__doc__]
    for cost in (3, 5, 8):
        for slip in (0, 5, 10):
            for lab, sel in (("2010～", good), ("2024～", [d for d in good if d >= "2024"])):
                x = np.array([r for d in sel if (r := trade(days[d], cost, slip)) is not None])
                out.append(f"  成本 {cost} 點 停損滑 {slip:2d} 點 {lab}：{len(x)} 筆 每筆 {x.mean():+.3f}% t {x.mean()/(x.std(ddof=1)/np.sqrt(len(x))):+.2f}")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究560_日內成本敏感度.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
