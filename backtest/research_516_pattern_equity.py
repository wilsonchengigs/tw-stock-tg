"""研究 516：VIX≥18 盤中型態（研究 515）的小台資金曲線
- 交易：前一晚 VIX≥18；|跳空|>0.3% 日第 2 頭較低＋破頸線做空；開高日第 2 底較高＋站上頸線做多（同一天兩個都有就都做）
- 轉折 0.25×ADR20、E2、12:00 前進場；出場：收盤／停損 T2／停損 T1；成本 3 點
- 以點數計（%×當天開盤指數），小台每點 50 元；每年點數、最大回檔（點）、最長連敗、最差單筆
- 與 P（前一晚 S&P 跌≥2% → 當天 08:45 做多抱到隔天）同一天的筆數與結果：做空型態會與 P 方向相反
- 延後 5 分鐘進場的保守版本
用法：python -X utf8 backtest/research_516_pattern_equity.py
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
    spx = yahoo("GSPC.json"); sk = np.array(sorted(spx))

    def vprev(d):
        i = np.searchsorted(vk, d) - 1
        return vix[vk[i]] if i >= 0 else 0

    def spx_prev(d):
        i = np.searchsorted(sk, d) - 1
        return (spx[sk[i]] / spx[sk[i - 1]] - 1) * 100 if i >= 1 else 0
    out = [__doc__]
    for delay in (0, 5):
        trades = {}
        for side, gf in ((-1, lambda g: abs(g) > 0.003), (1, lambda g: g > 0.003)):
            for s in R.setups(days, gaps, adr, side, "相對", 0.25, "E2", delay=delay):
                if s["minute"] <= 180 + delay and gf(s["gap"]) and vprev(s["day"]) >= 18:
                    px = days[s["day"]][0, 3]
                    trades.setdefault(s["day"], []).append((side, {k: v / 100 * px for k, v in s["pnl"].items()}))
        out.append(f"\n===== 延後 {delay} 分進場 =====")
        for st in ("無", "T2", "T1"):
            seq = []
            for d in sorted(trades):
                for side, pts in trades[d]:
                    seq.append((d, side, pts[(st, None)]))
            pts = np.array([x[2] for x in seq]); eq = np.cumsum(pts)
            dd = (eq - np.maximum.accumulate(np.concatenate([[0], eq]))[1:]).min()
            streak = cur = 0
            for x in pts:
                cur = cur + 1 if x <= 0 else 0; streak = max(streak, cur)
            yrs = sorted(set(x[0][:4] for x in seq))
            ys = {y: sum(x[2] for x in seq if x[0][:4] == y) for y in yrs}
            nyr = (len(set(x[0] for x in seq)) and (int(yrs[-1]) - int(yrs[0]) + 1))
            out.append(f"[停損 {st}] {len(seq)} 筆（約 {len(seq)/nyr:.1f} 筆／年）勝率 {(pts>0).mean()*100:.1f}% 平均 {pts.mean():+.1f} 點 合計 {pts.sum():+.0f} 點（小台 {pts.sum()*50/1e4:+.0f} 萬）")
            out.append(f"   最大回檔 {dd:.0f} 點（小台 {dd*50/1e4:.1f} 萬）、最長連敗 {streak} 筆、最差單筆 {pts.min():.0f} 點、最好 {pts.max():.0f} 點、標準差 {pts.std():.0f} 點")
            out.append("   逐年點數：" + "  ".join(f"{y}:{ys[y]:+.0f}" for y in yrs))
            if st == "無":
                pd_ = [x for x in seq if spx_prev(x[0]) <= -2]
                if pd_:
                    a = np.array([x[2] for x in pd_])
                    out.append(f"   與 P 同日（前晚 S&P ≤-2%）：{len(pd_)} 筆（做空 {sum(1 for x in pd_ if x[1]<0)}）平均 {a.mean():+.0f} 點、勝率 {(a>0).mean()*100:.0f}%")
                rec = [x for x in seq if x[0] >= "2024-01-01"]
                a = np.array([x[2] for x in rec])
                out.append(f"   2024～：{len(rec)} 筆 平均 {a.mean():+.0f} 點 勝率 {(a>0).mean()*100:.0f}%（點數隨指數水準放大）")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究516_型態資金曲線.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
