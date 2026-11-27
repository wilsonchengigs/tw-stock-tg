"""研究 533：日內順勢 D30＋E 的日曆分組（結算日、星期、長假前後、月初月底）
D30＋E（09:30～12:30）、一天 1 口、反向 0.75% 停損、13:25 出、成本 3 點；全部日子與「空手＋VIX≥18」
結算日＝每月第 3 個週三；長假＝與前一交易日相隔 ≥4 天（假後第一天）／與下一交易日相隔 ≥4 天（假前最後一天）
用法：python -X utf8 backtest/research_533_intraday_calendar.py
"""
import os, sys, datetime as dt
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_522_intraday_trend_robust as M
from research_514_pattern_regime import yahoo
import research_138_金字塔加碼與分段停損 as S138
from research_531_intraday_by_main_state import trade


def main():
    days = M.load_idx(); ds = sorted(days)
    vix = yahoo("VIX.json"); vk = np.array(sorted(vix))
    dd = [str(x)[:10] for x in S138.DAYS]; st = dict(zip(dd, S138.ST)); keys = np.array(sorted(st))
    D = [dt.date.fromisoformat(d) for d in ds]
    rows = []
    for i, d in enumerate(ds):
        t = trade(days[d])
        if not t:
            continue
        x = D[i]
        good = st[keys[np.searchsorted(keys, d) - 1]] == 0 and vix[vk[np.searchsorted(vk, d) - 1]] >= 18
        tags = {"結算日": x.weekday() == 2 and 15 <= x.day <= 21,
                "週" + "一二三四五"[x.weekday()]: True,
                "假後第一天": i > 0 and (x - D[i - 1]).days >= 4,
                "假前最後一天": i < len(D) - 1 and (D[i + 1] - x).days >= 4,
                "月初 3 天": x.day <= 3, "月底 3 天": i < len(D) - 3 and D[i + 3].month != x.month}
        rows.append((d, good, t[1], tags))
    out = [__doc__]
    for gate in (False, True):
        out.append(f"\n===== {'空手＋VIX≥18' if gate else '全部日子'} =====")
        base = np.array([r for d, g, r, tg in rows if g or not gate])
        out.append(f"  全部：{len(base)} 筆 每筆 {base.mean():+.3f}%")
        for k in ("結算日", "週一", "週二", "週三", "週四", "週五", "假後第一天", "假前最後一天", "月初 3 天", "月底 3 天"):
            x = np.array([r for d, g, r, tg in rows if (g or not gate) and tg.get(k)])
            y = np.array([r for d, g, r, tg in rows if (g or not gate) and not tg.get(k)])
            if len(x) < 8:
                out.append(f"  {k}：{len(x)} 筆太少"); continue
            out.append(f"  {k:8s}：{len(x):4d} 筆 每筆 {x.mean():+.3f}% 勝率 {(x>0).mean()*100:.0f}%｜其他 {y.mean():+.3f}%｜差 t {(x.mean()-y.mean())/np.sqrt(x.var(ddof=1)/len(x)+y.var(ddof=1)/len(y)):+.2f}")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究533_日內順勢日曆.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
