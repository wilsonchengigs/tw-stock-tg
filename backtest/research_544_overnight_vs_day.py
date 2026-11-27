"""研究 544：台指期「隔夜（日盤收 13:45 → 隔天日盤開 08:45）」vs「日盤（開 → 收）」報酬拆解
- 台指期近月（成交量最大）日盤 OHLC，1998～；換月日（前後兩天月份不同）剔除
- 狀態與 VIX 都用 p（前一交易日）收盤前可知的值；初版用了 d 之前的 VIX＝隔夜當晚的美國收盤，有後見之明（研究 545 更正）
- 年化（簡單加總×252）、t、逐段（1998–2007／2008–2016／2017～ 有夜盤）；依主策略 v3 狀態、前一晚 VIX
- 只抱隔夜的台指期策略：每天收盤買、隔天開盤賣，成本每次 3 點（另算 2 點、5 點）
用法：python -X utf8 backtest/research_544_overnight_vs_day.py
"""
import os, sys, csv
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from research_514_pattern_regime import yahoo
import research_138_金字塔加碼與分段停損 as S138


def load():
    best = {}
    for r in csv.DictReader(open(os.path.join(HERE, "tx_daily_ohlc.csv"), encoding="utf-8")):
        if r["session"] != "day" or r["open"] in ("-", "") or r["close"] in ("-", ""):
            continue
        v = int(r["volume"] or 0)
        if r["date"] not in best or v > best[r["date"]][0]:
            best[r["date"]] = (v, r["month"], float(r["open"]), float(r["close"]))
    return best


def main():
    b = load(); ds = sorted(b)
    vix = yahoo("VIX.json"); vk = np.array(sorted(vix))
    dd = [str(x)[:10] for x in S138.DAYS]; st = dict(zip(dd, S138.ST)); keys = np.array(sorted(st))
    rows = []
    for p, d in zip(ds, ds[1:]):
        if b[p][1] != b[d][1]:
            continue
        on = b[d][2] / b[p][3] - 1; dy = b[d][3] / b[d][2] - 1
        # 對齊（研究 545 更正）：隔夜那段只能用 p 收盤前已知的資料（p 之前的美國 VIX、p 前一天的主策略狀態）
        i = np.searchsorted(keys, p) - 1; j = np.searchsorted(vk, p) - 1
        rows.append((d, on, dy, st[keys[i]] if i >= 0 else None, vix[vk[j]] if j >= 0 else None, b[p][3]))
    out = [__doc__, f"{rows[0][0]}～{rows[-1][0]}，{len(rows)} 天（剔除換月）"]
    def line(lab, sel):
        on = np.array([r[1] for r in sel]) * 100; dy = np.array([r[2] for r in sel]) * 100
        t = lambda x: x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))
        return f"  {lab:20s} {len(sel):5d} 天｜隔夜 每天 {on.mean():+.3f}%（年化約 {on.mean()*252:+.0f}%）t {t(on):+.1f}｜日盤 {dy.mean():+.3f}%（{dy.mean()*252:+.0f}%）t {t(dy):+.1f}"
    out.append(line("全部", rows))
    for a, z, lab in (("1998", "2008", "1998–2007"), ("2008", "2017", "2008–2016"), ("2017", "2099", "2017～（有夜盤）")):
        out.append(line(lab, [r for r in rows if a <= r[0] < z]))
    for s0, sl in ((1, "主策略在場"), (0, "主策略空手")):
        out.append(line(sl, [r for r in rows if r[3] == s0]))
        for vl, vh, vlab in ((0, 18, "VIX<18"), (18, 25, "VIX18～25"), (25, 999, "VIX≥25")):
            out.append(line(f" {sl} {vlab}", [r for r in rows if r[3] == s0 and r[4] is not None and vl <= r[4] < vh]))
    out.append("\n只抱隔夜（每天收盤買、隔天開盤賣）扣成本：")
    for cost in (2, 3, 5):
        for a, z, lab in (("1998", "2099", "全部"), ("2017", "2099", "2017～")):
            x = np.array([r[1] - cost / r[5] for r in rows if a <= r[0] < z])
            eq = np.cumprod(1 + x); yrs = len(x) / 252
            mdd = (eq / np.maximum.accumulate(eq) - 1).min()
            out.append(f"  成本 {cost} 點 {lab:6s}：年化 {eq[-1]**(1/yrs)-1:+.1%} 回檔 {mdd:.1%} 每天 {x.mean()*100:+.3f}%")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究544_隔夜與日盤.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
