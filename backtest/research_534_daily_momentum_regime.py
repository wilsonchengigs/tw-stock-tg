"""研究 534：跨日順勢或反轉，依主策略狀態×VIX 分組
用加權 1 分 K（2010～）：今天日盤報酬（09:05→13:30）方向 s、幅度 ≥0／0.5／1% →
  (a) 隔夜：今天 13:30 → 隔天 09:05；(b) 隔天日盤：隔天 09:05 → 13:30；(c) 今天 13:30 → 隔天 13:30
回報 s×報酬（正＝順勢、負＝反轉），成本不計（看方向性）；四格（在場／空手 × VIX<18／≥18）
用法：python -X utf8 backtest/research_534_daily_momentum_regime.py
"""
import os, sys
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
    o = {d: M.at(days[d], 5) for d in ds}; c = {d: M.at(days[d], 270) for d in ds}
    rows = []
    for a, b in zip(ds, ds[1:]):
        r0 = c[a] / o[a] - 1
        s = 1 if r0 > 0 else -1
        # 狀態與 VIX 用「今天收盤後」可知的：主策略今天的狀態、今晚之前最後一個美國 VIX（今天台灣日期之前）
        state = st[keys[np.searchsorted(keys, a, side="right") - 1]]
        v = vix[vk[np.searchsorted(vk, a) - 1]]
        rows.append((a, abs(r0), state, v >= 18, s * (o[b] / c[a] - 1) * 100, s * (c[b] / o[b] - 1) * 100, s * (c[b] / c[a] - 1) * 100))
    out = [__doc__]
    for th in (0, 0.005, 0.01):
        out.append(f"\n===== 今天日盤 |漲跌| ≥{th*100:.1f}% =====")
        for stv, sl in ((None, "全部"), (1, "在場"), (0, "空手")):
            for hv, hl in ((None, ""), (False, " VIX<18"), (True, " VIX≥18")):
                sel = [r for r in rows if r[1] >= th and (stv is None or r[2] == stv) and (hv is None or r[3] == hv)]
                if len(sel) < 30 or (stv is None and hv is not None):
                    continue
                x = np.array([[r[4], r[5], r[6]] for r in sel])
                tt = x.mean(0) / (x.std(0, ddof=1) / np.sqrt(len(x)))
                out.append(f"  {sl}{hl:8s} {len(x):4d} 天｜隔夜 {x[:,0].mean():+.3f}%（t {tt[0]:+.1f}）隔天日盤 {x[:,1].mean():+.3f}%（t {tt[1]:+.1f}）收到收 {x[:,2].mean():+.3f}%（t {tt[2]:+.1f}）")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究534_跨日順勢依狀態.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
