"""研究 561：日內順勢（主策略空手＋VIX≥18）依進場當下可知的訊號類型分組（初版用了「之後有沒有再觸發 E」的未來資訊，已改）
E 在 10:30 前觸發／10:30 由 D30 進（漲跌 0.5～0.75%、0.75～1%）／10:30 後才由 E 觸發
進場一律取最早訊號；反向 0.75% 停損、13:25 出、成本 3 點
用法：python -X utf8 backtest/research_561_intraday_signal_types.py
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_522_intraday_trend_robust as M
from research_514_pattern_regime import yahoo
import research_138_金字塔加碼與分段停損 as S138
from research_531_intraday_by_main_state import trade


def kinds(a):
    o = M.at(a, 5); mins = a[:, 0].astype(int); cl = a[:, 1]
    tr = M.at(a, 90) / o - 1
    d = (1 if tr > 0 else -1) if abs(tr) >= 0.005 else 0
    idx = np.nonzero((mins >= 30) & (mins <= 210) & (np.abs(cl / o - 1) >= 0.01))[0]
    e = (1 if cl[idx[0]] > o else -1) if len(idx) else 0
    em = int(mins[idx[0]]) if len(idx) else None
    return d, e, em


def main():
    days = M.load_idx(); ds = sorted(days)
    vix = yahoo("VIX.json"); vk = np.array(sorted(vix))
    dd = [str(x)[:10] for x in S138.DAYS]; st = dict(zip(dd, S138.ST)); keys = np.array(sorted(st))
    g = {"09:30～10:29 由 E 進場": [], "10:30 進場、漲跌 0.5～0.75%": [], "10:30 進場、漲跌 0.75～1%": [], "10:31～12:30 由 E 進場（10:30 時 <0.5%）": []}
    for d in ds:
        if st[keys[np.searchsorted(keys, d) - 1]] != 0 or vix[vk[np.searchsorted(vk, d) - 1]] < 18:
            continue
        t = trade(days[d])
        if not t:
            continue
        dk, ek, em = kinds(days[d])
        a = days[d]; mv = abs(M.at(a, 90) / M.at(a, 5) - 1)
        if ek and em < 90:
            k = "09:30～10:29 由 E 進場"
        elif dk:
            k = "10:30 進場、漲跌 0.5～0.75%" if mv < 0.0075 else "10:30 進場、漲跌 0.75～1%"
        else:
            k = "10:31～12:30 由 E 進場（10:30 時 <0.5%）"
        g[k].append(t[1])
    out = [__doc__]
    for k, v in g.items():
        x = np.array(v)
        if len(x) > 5:
            out.append(f"  {k:16s} {len(x):4d} 筆 每筆 {x.mean():+.3f}% t {x.mean()/(x.std(ddof=1)/np.sqrt(len(x))):+.2f} 勝率 {(x>0).mean()*100:.0f}%")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究561_日內訊號類型.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
