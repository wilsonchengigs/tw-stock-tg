"""研究 571：日內順勢（主策略空手＋VIX≥18）部位大小：固定 1x vs 依 ADR20 反比（平均調成 1x）vs 依 VIX 反比
比較：每筆平均、年化（每筆報酬×倍數加總）、每筆夏普、最差單筆、累加最大回檔
用法：python -X utf8 backtest/research_571_intraday_vol_sizing.py
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_522_intraday_trend_robust as M
import research_511_higher_low as R
from research_514_pattern_regime import yahoo
import research_138_金字塔加碼與分段停損 as S138
from research_531_intraday_by_main_state import trade


def main():
    days = M.load_idx(); ds = sorted(days)
    adr = R.adr20(R.load_days())
    vix = yahoo("VIX.json"); vk = np.array(sorted(vix))
    dd = [str(x)[:10] for x in S138.DAYS]; st = dict(zip(dd, S138.ST)); keys = np.array(sorted(st))
    rows = []
    for d in ds:
        v = vix[vk[np.searchsorted(vk, d) - 1]]
        if st[keys[np.searchsorted(keys, d) - 1]] != 0 or v < 18 or d not in adr:
            continue
        t = trade(days[d])
        if t:
            rows.append((d, t[1], adr[d], v))
    x = np.array([r[1] for r in rows]); a = np.array([r[2] for r in rows]); v = np.array([r[3] for r in rows])
    out = [__doc__]
    for lab, w in (("固定 1x", np.ones(len(x))), ("ADR 反比", (1 / a) / np.mean(1 / a)), ("VIX 反比", (1 / v) / np.mean(1 / v)), ("ADR 反比（上限 1.5x）", np.minimum(1.5, (1 / a) / np.mean(1 / a)))):
        y = x * w; eq = np.cumsum(y); mdd = (eq - np.maximum.accumulate(np.concatenate([[0], eq]))[1:]).min()
        out.append(f"  {lab:16s} 每筆 {y.mean():+.3f}% 夏普 {y.mean()/y.std():+.3f} 最差 {y.min():+.2f}% 累加回檔 {mdd:.1f}% 合計 {y.sum():+.0f}%｜倍數範圍 {w.min():.2f}～{w.max():.2f}")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究571_日內波動調倍數.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
