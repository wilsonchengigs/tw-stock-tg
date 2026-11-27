"""研究 527：P（前一晚 S&P 跌 ≥2% → 當天開盤做多、抱到隔天開盤）持有當天，盤中出現順勢做空訊號要不要提早出
- P 近似：加權 09:05 進、隔天 09:05 出（1 分 K），成本 3 點
- 盤中做空訊號：D30（09:05→10:30 跌 ≥0.5%）或 E（盤中第一次跌 ≥1%，13:00 前）
- 比較：(a) 照抱 (b) 有做空訊號就在訊號那分鐘出 (c) 有訊號就出並反手空到 13:25（日內）
- 另列：P 當天有／沒有做空訊號時，P 的報酬
用法：python -X utf8 backtest/research_527_P_intraday_exit.py
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_522_intraday_trend_robust as M
from research_514_pattern_regime import yahoo


def main():
    days = M.load_idx(); ds = sorted(days); nxt = dict(zip(ds, ds[1:]))
    spx = yahoo("GSPC.json"); sk = np.array(sorted(spx))
    out = [__doc__]
    rows = []
    for d in ds:
        i = np.searchsorted(sk, d) - 1
        if i < 1 or d not in nxt:
            continue
        if spx[sk[i]] / spx[sk[i - 1]] - 1 > -0.02:
            continue
        a = days[d]; o = M.at(a, 5); n_o = M.at(days[nxt[d]], 5)
        hold = n_o / o - 1 - 3 / o
        sig = None
        if M.at(a, 90) / o - 1 <= -0.005:
            sig = 90
        for mm, cl in a:
            if 6 <= mm <= 240 and cl / o - 1 <= -0.01:
                sig = min(sig, int(mm)) if sig else int(mm); break
        if sig:
            x = M.at(a, sig)
            early = x / o - 1 - 3 / o
            flip = early + (-(M.at(a, 265) / x - 1) - 3 / x)
        else:
            early = flip = hold
        rows.append((d, hold, early, flip, sig is not None))
    h = np.array([r[1] for r in rows]) * 100; e = np.array([r[2] for r in rows]) * 100; f = np.array([r[3] for r in rows]) * 100
    sg = np.array([r[4] for r in rows])
    out.append(f"P 日（前晚 S&P ≤-2%）{len(rows)} 天，盤中出現做空訊號 {sg.sum()} 天")
    for lab, x in (("(a) 照抱到隔天", h), ("(b) 有訊號就出", e), ("(c) 有訊號出並反手空到 13:25", f)):
        out.append(f"  {lab}：每筆 {x.mean():+.3f}% 勝率 {(x>0).mean()*100:.0f}% 最差 {x.min():+.2f}%｜2010～17 {x[[r[0]<'2018' for r in rows]].mean():+.3f} 2018～ {x[[r[0]>='2018' for r in rows]].mean():+.3f}")
    out.append(f"  有訊號的日子 P 照抱：{h[sg].mean():+.3f}%（{sg.sum()} 天，勝率 {(h[sg]>0).mean()*100:.0f}%）；提早出：{e[sg].mean():+.3f}%")
    out.append(f"  沒訊號的日子 P 照抱：{h[~sg].mean():+.3f}%（{(~sg).sum()} 天，勝率 {(h[~sg]>0).mean()*100:.0f}%）")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究527_P盤中提早出.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
