"""研究 573：日內順勢（主策略空手＋VIX≥18）只在每 N 分鐘看一次報價（N＝1／5／15／30）
E 觸發與停損都只在看盤時點（分鐘數為 N 的倍數）判斷；D30 本來就是 10:30 一次；13:25 出
用法：python -X utf8 backtest/research_573_intraday_check_freq.py
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_522_intraday_trend_robust as M
from research_514_pattern_regime import yahoo
import research_138_金字塔加碼與分段停損 as S138
CM = 265


def run(a, N):
    o = M.at(a, 5); mins = a[:, 0].astype(int); cl = a[:, 1]; look = (mins % N == 0); cand = []
    tr = M.at(a, 90) / o - 1
    if abs(tr) >= 0.005:
        cand.append((90, 1 if tr > 0 else -1))
    idx = np.nonzero(look & (mins >= 30) & (mins <= 210) & (np.abs(cl / o - 1) >= 0.01))[0]
    if len(idx):
        cand.append((int(mins[idx[0]]), 1 if cl[idx[0]] > o else -1))
    if not cand:
        return None
    mm, s = min(cand); e = M.at(a, mm); lvl = e * (1 - s * 0.0075)
    hit = np.nonzero(look & (mins > mm) & (mins <= CM) & (s * (cl - lvl) <= 0))[0]
    if len(hit):
        return (s * (cl[hit[0]] / e - 1) - 5 / e) * 100
    return (s * (M.at(a, CM) / e - 1) - 3 / e) * 100


def main():
    days = M.load_idx(); ds = sorted(days)
    vix = yahoo("VIX.json"); vk = np.array(sorted(vix))
    dd = [str(x)[:10] for x in S138.DAYS]; st = dict(zip(dd, S138.ST)); keys = np.array(sorted(st))
    good = [d for d in ds if st[keys[np.searchsorted(keys, d) - 1]] == 0 and vix[vk[np.searchsorted(vk, d) - 1]] >= 18]
    out = [__doc__]
    for N in (1, 5, 15, 30):
        x = np.array([r for d in good if (r := run(days[d], N)) is not None])
        out.append(f"  每 {N:2d} 分鐘看一次：{len(x)} 筆 每筆 {x.mean():+.3f}% t {x.mean()/(x.std(ddof=1)/np.sqrt(len(x))):+.2f} 最差 {x.min():+.2f}% 勝率 {(x>0).mean()*100:.0f}%")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究573_日內看盤頻率.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
