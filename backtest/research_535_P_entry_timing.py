"""研究 535：P（前晚 S&P 跌 ≥2%）進場時點：09:05 直接 vs 10:30 才進（全部／只在 09:05→10:30 沒跌 ≥0.5% 時）
出場都是隔天 09:05；成本 3 點；加權 1 分 K 近似（實際 P 是台指期 08:45 進，這裡比較相對差異）
另列：10:30 前已跌 ≥0.5% 的日子，09:05 進的 P 結果（＝研究 527 的有訊號日）
用法：python -X utf8 backtest/research_535_P_entry_timing.py
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
    rows = []
    for d in ds:
        i = np.searchsorted(sk, d) - 1
        if i < 1 or d not in nxt or spx[sk[i]] / spx[sk[i - 1]] - 1 > -0.02:
            continue
        a = days[d]; o = M.at(a, 5); m = M.at(a, 90); n = M.at(days[nxt[d]], 5)
        rows.append((d, n / o - 1 - 3 / o, n / m - 1 - 3 / m, m / o - 1))
    out = [__doc__, f"P 日 {len(rows)} 天"]
    r905 = np.array([r[1] for r in rows]) * 100; r1030 = np.array([r[2] for r in rows]) * 100; mv = np.array([r[3] for r in rows])
    weak = mv <= -0.005
    cond = np.where(weak, 0.0, r1030)
    for lab, x in (("09:05 直接進", r905), ("10:30 才進（全部）", r1030), ("10:30 且沒跌 ≥0.5% 才進", cond)):
        out.append(f"  {lab}：每筆 {x.mean():+.3f}% 勝率 {(x>0).mean()*100:.0f}% 最差 {x.min():+.2f}%｜2010～17 {x[[r[0]<'2018' for r in rows]].mean():+.3f} 2018～ {x[[r[0]>='2018' for r in rows]].mean():+.3f}")
    out.append(f"  10:30 前已跌 ≥0.5%：{weak.sum()} 天，09:05 進的 P {r905[weak].mean():+.3f}%、10:30 進 {r1030[weak].mean():+.3f}%")
    out.append(f"  其餘：{(~weak).sum()} 天，09:05 進 {r905[~weak].mean():+.3f}%、10:30 進 {r1030[~weak].mean():+.3f}%")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究535_P進場時點.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
