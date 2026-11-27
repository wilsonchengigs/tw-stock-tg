"""研究 540：週末（週五收盤 → 下週一開盤）與一般隔夜報酬，依主策略狀態×前一晚 VIX
加權 1 分 K（2010～）：收盤 13:30 → 下個交易日 09:05；週末＝相隔 ≥3 天；另列台指期日盤收盤→隔天開盤（tx_daily_ohlc，含夜盤時期）
用法：python -X utf8 backtest/research_540_weekend_by_state.py
"""
import os, sys, datetime as dt
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_522_intraday_trend_robust as M
from research_514_pattern_regime import yahoo
import research_138_金字塔加碼與分段停損 as S138


def main():
    days = M.load_idx(); ds = sorted(days)
    vix = yahoo("VIX.json"); vk = np.array(sorted(vix))
    dd = [str(x)[:10] for x in S138.DAYS]; st = dict(zip(dd, S138.ST)); keys = np.array(sorted(st))
    rows = []
    for a, b in zip(ds, ds[1:]):
        gap = (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days
        state = st[keys[np.searchsorted(keys, a, side="right") - 1]]
        v = vix[vk[np.searchsorted(vk, a, side="right") - 1]]  # 週五當天（美國）收盤前已知的最後 VIX：用台灣日期 a 當天或之前
        r = (M.at(days[b], 5) / M.at(days[a], 270) - 1) * 100
        rows.append((a, gap >= 3, state, v, r))
    out = [__doc__]
    for wk, wl in ((True, "週末"), (False, "平日隔夜")):
        out.append(f"\n===== {wl} =====")
        for stv, sl in ((None, "全部"), (1, "在場"), (0, "空手")):
            for vl, vh, hl in ((0, 999, ""), (0, 18, " VIX<18"), (18, 25, " VIX18～25"), (25, 999, " VIX≥25")):
                x = np.array([r for a, w, s, v, r in rows if w == wk and (stv is None or s == stv) and vl <= v < vh])
                if len(x) < 20:
                    continue
                out.append(f"  {sl}{hl:10s} {len(x):4d} 次 平均 {x.mean():+.3f}% t {x.mean()/(x.std(ddof=1)/np.sqrt(len(x))):+.2f} 上漲比例 {(x>0).mean()*100:.0f}% 標準差 {x.std():.2f}%")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究540_週末依狀態.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
