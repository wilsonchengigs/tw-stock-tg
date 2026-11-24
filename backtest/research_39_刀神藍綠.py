"""研究 39：刀神「藍綠戰法」套到加權指數＋正2（使用者提議）

來源：《海期刀神的60分K獲利術》（刀神）https://play.google.com/store/books/details?id=ti9AEAAAQBAJ ；
YouTube「刀神談海期」系列 https://www.youtube.com/watch?v=GWHXbhiByJk
規則（書介與影片簡介整理，原書細節未取得）：60 分 K 的 MA20（小藍）與 MA60（小綠）；小藍上穿小綠（黃金交叉）且 KD 轉強進場；
看均線斜率，斜率越大支撐越強。本研究做多不做空（使用者不做空）：
- 進場：MA20 > MA60，且 MA20、MA60 斜率（與 5 根前比較）都向上；變形加 KD(9) K > D
- 出場：MA20 < MA60（死亡交叉）；變形「收盤跌破 MA60」
A. 真實 60 分 K（Yahoo ^TWII 60m，2023-11～2026-11，每天 5 根），訊號在 K 棒收盤、下一根 K 棒收盤成交（2x＝2×指數報酬−內扣）
   另做「只在週五最後一根判斷」版本（符合每週判斷的偏好）
B. 日 K 近似長期回測（1998～）：小時 MA20／60 ≈ 日 MA4／MA12（每天約 5 根）
比較：同期現行策略、正2 長抱
用法：python -X utf8 backtest/research_39_刀神藍綠.py
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402

TW = timezone(timedelta(hours=8))
COST = bt.COST
DRAG = bt.DRAG


def sma(x, n):
    out, s = [None] * len(x), 0.0
    for i, v in enumerate(x):
        s += v
        if i >= n:
            s -= x[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def kd(c, h, lo, n=9):
    K, D, k, d = [], [], 50.0, 50.0
    for i in range(len(c)):
        hh, ll = max(h[max(0, i - n + 1):i + 1]), min(lo[max(0, i - n + 1):i + 1])
        rsv = 50.0 if hh == ll else (c[i] - ll) / (hh - ll) * 100
        k = k * 2 / 3 + rsv / 3
        d = d * 2 / 3 + k / 3
        K.append(k)
        D.append(d)
    return K, D


def signals(c, h, lo, fast, slow, use_kd, exit_mode, slope_n=5):
    mf, ms = sma(c, fast), sma(c, slow)
    K, D = kd(c, h, lo)
    st, out = False, []
    for i in range(len(c)):
        if ms[i] is None or i < slow + slope_n:
            out.append(False)
            continue
        if not st:
            go = mf[i] > ms[i] and mf[i] > mf[i - slope_n] and ms[i] > ms[i - slope_n]
            if go and use_kd:
                go = K[i] > D[i]
            st = go
        else:
            st = not (mf[i] < ms[i] if exit_mode == "cross" else c[i] < ms[i])
        out.append(st)
    return out


def backtest(c, sig, bars_per_year, decide=None):
    eq = peak = 1.0
    mdd, pos, pend, trades = 0.0, False, None, 0
    for i in range(1, len(c)):
        r = c[i] / c[i - 1] - 1
        eq *= 1 + ((2 * r - DRAG / bars_per_year) if pos else 0.01 / bars_per_year)
        if pend is not None:
            eq *= 1 - COST * 2
            pos, pend = pend, None
            trades += 1
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if (decide is None or decide[i]) and sig[i] != pos:
            pend = sig[i]
    yrs = len(c) / bars_per_year
    return eq ** (1 / yrs) - 1, mdd, trades / yrs


def main():
    L = ["研究 39：刀神藍綠戰法（做多＋正2）"]
    r = json.load(open(os.path.join(HERE, "TWII_60m.json")))
    q = r["indicators"]["quote"][0]
    rows = [(datetime.fromtimestamp(t, TW), c, h, lo) for t, c, h, lo in zip(r["timestamp"], q["close"], q["high"], q["low"]) if c and h and lo]
    rows = [x for x in rows if x[0].strftime("%Y-%m-%d") < datetime.now(TW).strftime("%Y-%m-%d")]  # 去掉今天未收完
    c = [x[1] for x in rows]
    h = [x[2] for x in rows]
    lo = [x[3] for x in rows]
    days = [x[0].strftime("%Y-%m-%d") for x in rows]
    bpy = 5 * 245
    last_of_week = [i == len(rows) - 1 or rows[i][0].isocalendar()[:2] != rows[i + 1][0].isocalendar()[:2] for i in range(len(rows))]
    L.append(f"\n== A. 真實 60 分 K（{days[0]}～{days[-1]}，{len(c)} 根）年化/最大回檔/年交易次數 ==")
    for use_kd in (False, True):
        for ex in ("cross", "ma60"):
            s = signals(c, h, lo, 20, 60, use_kd, ex)
            a = backtest(c, s, bpy)
            w = backtest(c, s, bpy, last_of_week)
            L.append(f"  MA20/60 {'＋KD' if use_kd else '    '} 出場{'死叉' if ex == 'cross' else '破MA60'}：每根判斷 {a[0]:6.1%}/{a[1]:6.1%}/{a[2]:5.1f} 次｜週五判斷 {w[0]:6.1%}/{w[1]:6.1%}/{w[2]:4.1f} 次")
    hold = backtest(c, [True] * len(c), bpy)
    L.append(f"  正2 長抱 {hold[0]:6.1%}/{hold[1]:6.1%}")
    # 同期現行策略（日線）
    i0 = next(i for i, d in enumerate(bt.DAYS) if d >= days[0])
    i1 = max(i for i, d in enumerate(bt.DAYS) if d <= days[-1])
    m60, m80 = bt.get_sma(60), bt.get_sma(80)
    st, pos, pend, eq, peak, mdd = False, False, None, 1.0, 1.0, 0.0
    for i in range(i0 - 200, i1 + 1):
        if bt.WEEK_END[i]:
            st = (not bt.PX[i] < m80[i] * 0.975) if st else (bt.PX[i] > m60[i] * 1.01)
        if i <= i0:
            pos = st
            continue
        eq *= 1 + (bt.R2[i] if pos else bt.RC)
        if pend is not None:
            eq *= 1 - COST * 2
            pos, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if bt.WEEK_END[i] and st != pos:
            pend = st
    yrs = (i1 - i0) / bt.TD
    L.append(f"  同期現行策略（日線）{eq ** (1 / yrs) - 1:6.1%}/{mdd:6.1%}")
    L.append("\n== B. 日 K 近似（小時 MA20/60 ≈ 日 MA4/12；另試 MA5/20、MA10/30）1998～2026 ==")
    PX = bt.PX
    for f, sl in ((4, 12), (5, 20), (10, 30)):
        for ex in ("cross", "ma60"):
            s = signals(PX, PX, PX, f, sl, False, ex)
            a = backtest(PX, s, bt.TD)
            w = backtest(PX, s, bt.TD, bt.WEEK_END)
            L.append(f"  MA{f}/{sl} 出場{'死叉' if ex == 'cross' else '破慢線'}：每天 {a[0]:6.1%}/{a[1]:6.1%}/{a[2]:5.1f} 次｜週五 {w[0]:6.1%}/{w[1]:6.1%}/{w[2]:4.1f} 次")
    L.append(f"  對照：現行 1998～2026 19.2%/-43.6%/2.8 次")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究39_刀神藍綠.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
