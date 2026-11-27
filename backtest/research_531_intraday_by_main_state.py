"""研究 531：日內順勢 D30+E 依主策略 v3 狀態（前一天收盤後：在場／空手）與方向分組
D30＋E（09:30～12:30 觸發）、一天最多 1 口、反向 0.75% 停損、13:25 出、成本 3 點；全部日子與 VIX≥18
目的：在場時做空等於部分避險、空手時做多等於加碼；看哪一格有效、要不要限制
用法：python -X utf8 backtest/research_531_intraday_by_main_state.py
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_522_intraday_trend_robust as M
from research_514_pattern_regime import yahoo
import research_138_金字塔加碼與分段停損 as S138
CM = 265


def trade(a):
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
    r = s * (cl[hit[0]] / e - 1) - 5 / e if len(hit) else s * (M.at(a, CM) / e - 1) - 3 / e
    return s, r * 100


def main():
    days = M.load_idx(); ds = sorted(days)
    vix = yahoo("VIX.json"); vk = np.array(sorted(vix))
    vhi = {d: vix[vk[np.searchsorted(vk, d) - 1]] >= 18 for d in ds}
    dd = [str(x)[:10] for x in S138.DAYS]
    st = dict(zip(dd, S138.ST))
    keys = np.array(sorted(st))
    def state_prev(d):
        i = np.searchsorted(keys, d) - 1
        return st[keys[i]] if i >= 0 else None
    rows = []
    for d in ds:
        t = trade(days[d])
        if t:
            rows.append((d, state_prev(d), t[0], t[1]))
    out = [__doc__, f"主策略日期 {dd[0]}～{dd[-1]}"]
    for gate in (False, True):
        out.append(f"\n===== {'VIX≥18' if gate else '全部日子'} =====")
        for stv, sl in ((1, "主策略在場"), (0, "主策略空手")):
            for sd, dl in ((0, "合計"), (1, "做多"), (-1, "做空")):
                x = np.array([r for d, s0, s, r in rows if s0 == stv and (vhi[d] or not gate) and (sd == 0 or s == sd)])
                if len(x) < 10:
                    continue
                out.append(f"  {sl} {dl}：{len(x):4d} 筆 每筆 {x.mean():+.3f}% t {x.mean()/(x.std(ddof=1)/np.sqrt(len(x))):+.2f} 勝率 {(x>0).mean()*100:.0f}%｜內 {x[[d<'2018' for d,s0,s,r in rows if s0==stv and (vhi[d] or not gate) and (sd==0 or s==sd)]].mean():+.3f} 外 {x[[d>='2018' for d,s0,s,r in rows if s0==stv and (vhi[d] or not gate) and (sd==0 or s==sd)]].mean():+.3f}")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究531_日內順勢依主策略狀態.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
