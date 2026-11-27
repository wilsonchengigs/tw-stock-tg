"""研究 518：盤中型態的開關改用台指 VIX（前一交易日收盤）vs 美國 VIX（前一晚）
- 型態同 515（做空 |跳空|>0.3%、做多開高 >0.3%；0.25×ADR20、E2、12:00 前、收盤出、成本 3 點），超額扣所有日子同分鐘基準
- 台指 VIX 門檻用分位數對齊：取與美國 VIX≥18 同樣比例的日子（另列固定門檻 18～26）
- 兩者都高／只有一個高 拆開
用法：python -X utf8 backtest/research_518_pattern_twvix.py
"""
import os, sys, csv
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_511_higher_low as R
from research_514_pattern_regime import yahoo


def t(x):
    x = np.asarray(x); return x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 else np.nan


def main():
    gaps = R.tx_gaps(); days = R.load_days(); adr = R.adr20(days); drift = R.drift_table(days)
    us = yahoo("VIX.json"); uk = np.array(sorted(us))
    tw = {r["date"]: float(r["vix"]) for r in csv.DictReader(open(os.path.join(HERE, "vixtwn.csv"), encoding="utf-8")) if r["vix"] not in ("", "-")}
    tk = np.array(sorted(tw))

    def prev(ser, keys, d):
        i = np.searchsorted(keys, d) - 1
        return ser[keys[i]] if i >= 0 else None
    out = [__doc__, f"台指 VIX 資料 {tk[0]}～{tk[-1]}"]
    for side, name, gf in ((-1, "做空（|跳空|>0.3%）", lambda g: abs(g) > 0.003), (1, "做多（開高）", lambda g: g > 0.003)):
        S = [s for s in R.setups(days, gaps, adr, side, "相對", 0.25, "E2") if s["minute"] <= 180 and gf(s["gap"])]
        S = [s for s in S if prev(tw, tk, s["day"]) is not None]
        ex = np.array([s["pnl"][("無", None)] - side * drift[s["minute"]] for s in S])
        u = np.array([prev(us, uk, s["day"]) for s in S]); w = np.array([prev(tw, tk, s["day"]) for s in S])
        ins = np.array([s["day"] < R.SPLIT for s in S])
        uh = u >= 18
        q = 1 - uh.mean(); wth = np.quantile(w, q)
        out.append(f"\n===== {name}：{len(S)} 筆；美 VIX≥18 占 {uh.mean()*100:.0f}%，台 VIX 同比例門檻 {wth:.1f}")
        rows = [("美 VIX≥18", uh), (f"台 VIX≥{wth:.1f}", w >= wth)] + [(f"台 VIX≥{x}", w >= x) for x in (18, 20, 22, 24, 26)]
        for lab, m in rows:
            out.append(f"  {lab:12s} 上 {m.sum():3d} 筆 超額 {ex[m].mean():+.3f}%（≈{ex[m].mean()*390:+.0f} 點）t {t(ex[m]):+.2f} 內 {ex[m&ins].mean():+.3f} 外 {ex[m&~ins].mean():+.3f}｜下 {(~m).sum():3d} 筆 {ex[~m].mean():+.3f}% t {t(ex[~m]):+.2f}")
        wh = w >= wth
        for lab, m in (("兩個都高", uh & wh), ("只有美高", uh & ~wh), ("只有台高", ~uh & wh), ("兩個都低", ~uh & ~wh)):
            out.append(f"  {lab}：{m.sum()} 筆 超額 {ex[m].mean():+.3f}% t {t(ex[m]):+.2f}")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究518_型態台指VIX.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
