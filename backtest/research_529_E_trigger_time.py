"""研究 529：日內順勢 E（盤中第一次比 09:05 漲跌 ≥1% → 順勢）依觸發時段
時段 09:06～09:30／09:30～10:30／10:30～11:30／11:30～12:30／12:30～13:00；反向 0.75% 停損、13:25 出、成本 3 點
全部日子與前一晚 VIX≥18；另列做空／做多
用法：python -X utf8 backtest/research_529_E_trigger_time.py
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_522_intraday_trend_robust as M
from research_514_pattern_regime import yahoo
CM = 265


def main():
    days = M.load_idx(); ds = sorted(days)
    vix = yahoo("VIX.json"); vk = np.array(sorted(vix))
    vhi = {d: vix[vk[np.searchsorted(vk, d) - 1]] >= 18 for d in ds}
    rows = []
    for d in ds:
        a = days[d]; o = M.at(a, 5); mins = a[:, 0].astype(int); cl = a[:, 1]
        idx = np.nonzero((mins >= 6) & (mins <= 240) & (np.abs(cl / o - 1) >= 0.01))[0]
        if not len(idx):
            continue
        j = idx[0]; mm = int(mins[j]); s = 1 if cl[j] > o else -1; e = cl[j]; lvl = e * (1 - s * 0.0075)
        hit = np.nonzero((mins > mm) & (mins <= CM) & (s * (cl - lvl) <= 0))[0]
        r = s * (cl[hit[0]] / e - 1) - 5 / e if len(hit) else s * (M.at(a, CM) / e - 1) - 3 / e
        rows.append((d, mm, s, r * 100))
    out = [__doc__]
    B = [(6, 30, "09:06～09:30"), (30, 90, "09:30～10:30"), (90, 150, "10:30～11:30"), (150, 210, "11:30～12:30"), (210, 241, "12:30～13:00")]
    for gate in (False, True):
        out.append(f"\n===== {'VIX≥18' if gate else '全部日子'} =====")
        for lo, hi, lab in B:
            for sd, sl in ((0, "合計"), (-1, "做空"), (1, "做多")):
                x = np.array([r for d, mm, s, r in rows if lo <= mm < hi and (vhi[d] or not gate) and (sd == 0 or s == sd)])
                if len(x) < 10:
                    continue
                out.append(f"  {lab} {sl}：{len(x):4d} 筆 每筆 {x.mean():+.3f}% t {x.mean()/(x.std(ddof=1)/np.sqrt(len(x))):+.2f} 勝率 {(x>0).mean()*100:.0f}%")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究529_E觸發時段.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
