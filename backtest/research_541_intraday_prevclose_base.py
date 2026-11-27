"""研究 541：日內順勢改用「比昨收漲跌 %」當基準（看盤軟體直接顯示的數字）
版本：
  A 原版：10:30 比 09:05 ≥0.5% 或 09:30～12:30 第一次比 09:05 ±1%
  B 昨收版：10:30 比昨收 ≥x 或 09:30～12:30 第一次比昨收 ±y（x 0.5／1、y 1／1.5／2）
  C 雙條件：10:30 比 09:05 與比昨收同方向且都 ≥0.5%
一天 1 口、反向 0.75% 停損、13:25 出、成本 3 點；全部與「空手＋VIX≥18」
用法：python -X utf8 backtest/research_541_intraday_prevclose_base.py
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_522_intraday_trend_robust as M
from research_514_pattern_regime import yahoo
import research_138_金字塔加碼與分段停損 as S138
CM = 265


def run(a, base, xd, xe, both=None):
    mins = a[:, 0].astype(int); cl = a[:, 1]; cand = []
    tr = M.at(a, 90) / base - 1
    ok = abs(tr) >= xd
    if both is not None:
        tr2 = M.at(a, 90) / both - 1
        ok = ok and abs(tr2) >= xd and np.sign(tr2) == np.sign(tr)
    if ok:
        cand.append((90, 1 if tr > 0 else -1))
    if xe:
        idx = np.nonzero((mins >= 30) & (mins <= 210) & (np.abs(cl / base - 1) >= xe))[0]
        if len(idx):
            cand.append((int(mins[idx[0]]), 1 if cl[idx[0]] > base else -1))
    if not cand:
        return None
    mm, s = min(cand); e = M.at(a, mm); lvl = e * (1 - s * 0.0075)
    hit = np.nonzero((mins > mm) & (mins <= CM) & (s * (cl - lvl) <= 0))[0]
    r = s * (cl[hit[0]] / e - 1) - 5 / e if len(hit) else s * (M.at(a, CM) / e - 1) - 3 / e
    return r * 100


def main():
    days = M.load_idx(); ds = sorted(days)
    vix = yahoo("VIX.json"); vk = np.array(sorted(vix))
    dd = [str(x)[:10] for x in S138.DAYS]; st = dict(zip(dd, S138.ST)); keys = np.array(sorted(st))
    good = {d: st[keys[np.searchsorted(keys, d) - 1]] == 0 and vix[vk[np.searchsorted(vk, d) - 1]] >= 18 for d in ds}
    prev = dict(zip(ds[1:], [M.at(days[d], 270) for d in ds[:-1]]))
    vers = [("A 原版（比 09:05）0.5／1", lambda a, pc: run(a, M.at(a, 5), 0.005, 0.01))]
    for xd in (0.005, 0.01):
        for xe in (0.01, 0.015, 0.02):
            vers.append((f"B 比昨收 {xd*100:.1f}／{xe*100:.1f}", lambda a, pc, xd=xd, xe=xe: run(a, pc, xd, xe)))
    vers.append(("B 比昨收 只看 10:30 ≥1%", lambda a, pc: run(a, pc, 0.01, None)))
    vers.append(("C 10:30 比 09:05 與比昨收都 ≥0.5%", lambda a, pc: run(a, M.at(a, 5), 0.005, None, both=pc)))
    out = [__doc__]
    for gate in (False, True):
        out.append(f"\n===== {'空手＋VIX≥18' if gate else '全部日子'} =====")
        for lab, f in vers:
            x = np.array([r for d in ds[1:] if (good[d] or not gate) and (r := f(days[d], prev[d])) is not None])
            yrs = {}
            out.append(f"  {lab:30s} {len(x):4d} 筆（{len(x)/17:.0f}/年）每筆 {x.mean():+.3f}% t {x.mean()/(x.std(ddof=1)/np.sqrt(len(x))):+.2f} 勝率 {(x>0).mean()*100:.0f}% 合計 {x.sum():+.0f}%")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究541_日內順勢昨收基準.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
