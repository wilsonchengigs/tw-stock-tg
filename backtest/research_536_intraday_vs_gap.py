"""研究 536：日內順勢 D30＋E 與開盤跳空（台指期日盤開盤 vs 前日收盤）的方向關係
分組：跳空與訊號同向（|跳空|>0.3%）／反向（|跳空|>0.3%）／平開；全部與「空手＋VIX≥18」
D30＋E（09:30～12:30）、一天 1 口、反向 0.75% 停損、13:25 出、成本 3 點
用法：python -X utf8 backtest/research_536_intraday_vs_gap.py
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_522_intraday_trend_robust as M
import research_511_higher_low as R
from research_514_pattern_regime import yahoo
import research_138_金字塔加碼與分段停損 as S138
from research_531_intraday_by_main_state import trade


def main():
    days = M.load_idx(); ds = sorted(days); gaps = R.tx_gaps()
    vix = yahoo("VIX.json"); vk = np.array(sorted(vix))
    dd = [str(x)[:10] for x in S138.DAYS]; st = dict(zip(dd, S138.ST)); keys = np.array(sorted(st))
    rows = []
    for d in ds:
        t = trade(days[d])
        if not t or d not in gaps:
            continue
        good = st[keys[np.searchsorted(keys, d) - 1]] == 0 and vix[vk[np.searchsorted(vk, d) - 1]] >= 18
        g = gaps[d]
        grp = "平開" if abs(g) <= 0.003 else ("同向" if np.sign(g) == t[0] else "反向")
        rows.append((d, good, grp, t[0], t[1]))
    out = [__doc__]
    for gate in (False, True):
        out.append(f"\n===== {'空手＋VIX≥18' if gate else '全部日子'} =====")
        for grp in ("同向", "反向", "平開"):
            for sd, sl in ((0, "合計"), (1, "做多"), (-1, "做空")):
                x = np.array([r for d, g, gp, s, r in rows if (g or not gate) and gp == grp and (sd == 0 or s == sd)])
                if len(x) < 10:
                    continue
                out.append(f"  跳空{grp} {sl}：{len(x):4d} 筆 每筆 {x.mean():+.3f}% t {x.mean()/(x.std(ddof=1)/np.sqrt(len(x))):+.2f} 勝率 {(x>0).mean()*100:.0f}%")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究536_日內順勢與跳空.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
