"""研究 513：不看跳空，任何一天「第 2 頭比第 1 頭低＋跌破頸線做空」／「第 2 底比第 1 底高＋站上頸線做多」
接研究 512：跳空序列平移後型態仍有 t≈4，代表優勢可能來自型態本身而不是開低。
轉折 0.25×ADR20、12:00 前進場、收盤出、成本 3 點；另扣「所有日子同一分鐘」基準；樣本內 2010～2017／樣本外 2018～2026
用法：python -X utf8 backtest/research_513_pattern_any_day.py
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import research_511_higher_low as R
gaps = R.tx_gaps(); days = R.load_days(); adr = R.adr20(days); drift = R.drift_table(days)
out = [__doc__]
for side, name in ((-1, "做空（第2頭較低＋破頸線）"), (1, "做多（第2底較高＋站上頸線）")):
    for rv in (0.2, 0.25, 0.3):
        S = R.setups(days, gaps, adr, side, "相對", rv, "E2")
        for lab, f in (("全部日子", lambda g: True), ("開低日(<-0.3%)", lambda g: g < -0.003), ("平開(±0.3%)", lambda g: abs(g) <= 0.003), ("開高日(>+0.3%)", lambda g: g > 0.003)):
            sel = [s for s in S if s["minute"] <= 180 and f(s["gap"])]
            p = np.array([s["pnl"][("無", None)] for s in sel])
            ex = p - np.array([side * drift[s["minute"]] for s in sel])
            ins = np.array([s["day"] < R.SPLIT for s in sel])
            out.append(f"[{name}] r {rv}×ADR {lab}：{R.fmt(R.stats(p))}")
            out.append(f"     扣同分鐘基準：{R.fmt(R.stats(ex))}｜樣本內 {R.stats(ex[ins])['mean']:+.3f}% t {R.stats(ex[ins])['t']:+.2f}｜樣本外 {R.stats(ex[~ins])['mean']:+.3f}% t {R.stats(ex[~ins])['t']:+.2f}")
txt = "\n".join(out)
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "結果_研究513_型態不看跳空.txt"), "w", encoding="utf-8").write(txt)
print(txt)

# 延後進場：加權指數成分股成交有時間差，指數會比台指期慢幾分鐘；延後 N 分鐘進場仍有優勢，才比較能相信台指期上也做得到
out2 = ["\n===== 延後進場（指數落後期貨的保守檢查）r 0.25×ADR、12:00 前訊號 ====="]
for side, name, f in ((-1, "開低做空", lambda g: g < -0.003), (-1, "開高做空", lambda g: g > 0.003), (1, "開高做多", lambda g: g > 0.003)):
    for dl in (0, 2, 5, 10):
        S = R.setups(days, gaps, adr, side, "相對", 0.25, "E2", delay=dl)
        sel = [s for s in S if s["minute"] <= 180 + dl and f(s["gap"])]
        p = np.array([s["pnl"][("無", None)] for s in sel])
        out2.append(f"[{name}] 延後 {dl:2d} 分：{R.fmt(R.stats(p))}")
print("\n".join(out2))
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "結果_研究513_型態不看跳空.txt"), "a", encoding="utf-8").write("\n".join(out2))
