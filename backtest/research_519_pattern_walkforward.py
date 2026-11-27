"""研究 519：盤中型態＋VIX 開關的滾動前進
- 參數格：美國 VIX 門檻 {無, 14, 16, 18, 20, 22} × 轉折 {0.2, 0.25, 0.3}×ADR20；做空（|跳空|>0.3%）與做多（開高）分開挑
- 每年年初只用之前所有年份挑「每筆平均點數（未扣基準，扣成本 3 點）× 筆數」＝合計 % 最高、且筆數 ≥30 的組合，套到當年
- 另一版挑法：過去的 t 值（每筆平均÷標準誤）最高，偏向每筆品質而非總量
- 2013 起逐年；比較：滾動挑 vs 固定 VIX18／0.25（研究 515 的選擇，有後見之明）vs 不設 VIX 開關
用法：python -X utf8 backtest/research_519_pattern_walkforward.py
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_511_higher_low as R
from research_514_pattern_regime import yahoo


def main():
    gaps = R.tx_gaps(); days = R.load_days(); adr = R.adr20(days)
    vix = yahoo("VIX.json"); vk = np.array(sorted(vix))

    def vprev(d):
        i = np.searchsorted(vk, d) - 1
        return vix[vk[i]] if i >= 0 else 0
    TH = [0, 14, 16, 18, 20, 22]; RV = [0.2, 0.25, 0.3]
    out = [__doc__]
    for side, name, gf in ((-1, "做空", lambda g: abs(g) > 0.003), (1, "做多", lambda g: g > 0.003)):
        trades = {}
        for rv in RV:
            S = [s for s in R.setups(days, gaps, adr, side, "相對", rv, "E2") if s["minute"] <= 180 and gf(s["gap"])]
            trades[rv] = [(s["day"], vprev(s["day"]), s["pnl"][("無", None)]) for s in S]
        yrs = sorted(set(d[:4] for d in days))
        res = {"滾動(合計)": [], "滾動(t值)": [], "固定18/0.25": [], "無開關/0.25": []}
        picks = []; picks2 = []
        for y in yrs:
            if y < "2013":
                continue
            best = None
            for th in TH:
                for rv in RV:
                    past = [p for d, v, p in trades[rv] if d[:4] < y and v >= th]
                    if len(past) < 30:
                        continue
                    sc = sum(past)
                    if best is None or sc > best[0]:
                        best = (sc, th, rv)
            best2 = None
            for th2 in TH:
                for rv2 in RV:
                    past = np.array([p for d, v, p in trades[rv2] if d[:4] < y and v >= th2])
                    if len(past) < 30:
                        continue
                    sc = past.mean() / (past.std(ddof=1) / np.sqrt(len(past)))
                    if best2 is None or sc > best2[0]:
                        best2 = (sc, th2, rv2)
            picks2.append(f"{y}:VIX{best2[1]}/{best2[2]}")
            res["滾動(t值)"] += [(y, p) for d, v, p in trades[best2[2]] if d[:4] == y and v >= best2[1]]
            _, th, rv = best
            picks.append(f"{y}:VIX{th}/{rv}")
            res["滾動(合計)"] += [(y, p) for d, v, p in trades[rv] if d[:4] == y and v >= th]
            res["固定18/0.25"] += [(y, p) for d, v, p in trades[0.25] if d[:4] == y and v >= 18]
            res["無開關/0.25"] += [(y, p) for d, v, p in trades[0.25] if d[:4] == y]
        out.append(f"\n===== {name} =====\n  合計挑到：" + " ".join(picks) + "\n  t 值挑到：" + " ".join(picks2))
        for k, lst in res.items():
            p = np.array([x[1] for x in lst])
            ys = {}
            for y, v in lst:
                ys[y] = ys.get(y, 0) + v
            pos = sum(1 for v in ys.values() if v > 0)
            out.append(f"  {k:10s}：{len(p)} 筆 平均 {p.mean():+.3f}%（≈{p.mean()*390:+.0f} 點）t {p.mean()/(p.std(ddof=1)/np.sqrt(len(p))):+.2f} 合計 {p.sum():+.1f}%｜正的年 {pos}/{len(ys)}")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究519_型態滾動前進.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
