"""研究 63d：爆量收黑買進，用台指期「真實價格」驗證（研究 63b 用加權指數近似）

資料：backtest/tx_daily_ohlc.csv（build_tx_ohlc.py；期交所 TX 每日行情，一般與盤後時段，1998-07～）
- 近月：每天一般時段成交量最大的月份；結算日（該月份最後交易日）改用次月
- 連續報酬：同一個契約的收盤對收盤；換月那天用新契約「前一日收盤」接續（不吃價差），並扣 2 點換月成本
- 期交所「盤後」列記在下一個交易日：訊號日 D 收盤後當晚 15:00 的夜盤 = D+1 的 night 列（2017-05 起）
訊號：證交所成交金額 ≥ k × 前 20 日均（或台指期口數），且台指期日盤收盤 < 前一日日盤收盤
進場三種：(n) 當晚夜盤開盤（2017-05～）、(o) 隔天日盤開盤、(c) 隔天日盤收盤；出場：進場後第 H 個日盤收盤
成本：每筆 3 點；持有中訊號略過；對照：同筆數同持有天數的隨機進場（同一種進場方式）
用法：python -X utf8 backtest/research_63d_爆量收黑_台指期真實價.py
"""
import csv
import importlib.util
import os
import random
import statistics
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
COST, ROLL = 3.0, 2.0
spec = importlib.util.spec_from_file_location("r61", os.path.join(HERE, "research_61_爆量順勢短線.py"))
r61 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r61)
AMT = dict(zip(r61.DAYS, r61.VOL["成交金額"]))


def num(x):
    try:
        return float(x)
    except ValueError:
        return None


def load():
    day = defaultdict(dict)    # date -> month -> (o,h,l,c,vol)
    night = defaultdict(dict)
    for r in csv.DictReader(open(os.path.join(HERE, "tx_daily_ohlc.csv"), encoding="utf-8")):
        o, h, lo, c, v = (num(r[k]) for k in ("open", "high", "low", "close", "volume"))
        if c is None or o is None:
            continue
        (day if r["session"] == "day" else night)[r["date"]][r["month"]] = (o, h, lo, c, v or 0)
    dates = sorted(day)
    # 每個月份的最後交易日（＝結算日）
    last_day = {}
    for d in dates:
        for m in day[d]:
            last_day[m] = d
    near = {}
    for d in dates:
        ms = sorted(day[d], key=lambda m: -day[d][m][4])
        m = ms[0]
        if last_day.get(m) == d and len(ms) > 1:
            m = sorted([x for x in day[d] if x > m])[0] if any(x > m for x in day[d]) else m
        near[d] = m
    return dates, day, night, near


def main():
    dates, day, night, near = load()
    n = len(dates)
    idx = {d: i for i, d in enumerate(dates)}
    C = [day[d][near[d]][3] for d in dates]
    VOLF = [sum(v[4] for v in day[d].values()) for d in dates]
    # 日盤收盤對收盤報酬（同契約）
    R = [0.0] * n
    for i in range(1, n):
        m, pm = near[dates[i]], near[dates[i - 1]]
        prev = day[dates[i - 1]].get(m)
        if prev is None or prev[3] is None:
            R[i] = C[i] / C[i - 1] - 1
        else:
            R[i] = C[i] / prev[3] - 1 - (ROLL / C[i] if m != pm else 0)

    def vr(series, i):
        xs = [series[k] for k in range(i - 20, i) if series[k]]
        return series[i] / (sum(xs) / len(xs)) if series[i] and len(xs) >= 16 else None

    amt = [AMT.get(d) for d in dates]

    def entry_ret(i, how, H):
        """訊號日 i；回傳 (報酬, 出場 index) 或 None。
        夜盤開／隔天開盤進：出場在第 i+H 個日盤收盤；隔天收盤進：再抱滿 H 天，出場在 i+1+H"""
        last = i + 1 + H if how == "c" else i + H
        if last >= n:
            return None
        d1 = dates[i + 1]
        m1 = near[d1]
        if how == "n":
            nb = night[d1].get(m1) or night[d1].get(near[dates[i]])
            if nb is None:
                return None
            # 夜盤開 → 隔天日盤收（同契約），再接後續日報酬
            m_n = m1 if night[d1].get(m1) else near[dates[i]]
            c1 = day[d1].get(m_n, day[d1][m1])[3]
            px = nb[0]
            g = c1 / px
        elif how == "o":
            px = day[d1][m1][0]
            g = day[d1][m1][3] / px
        else:
            px = day[d1][m1][3]
            g = 1.0
        for j in range(i + 2, last + 1):
            g *= 1 + R[j]
        return g - 1 - COST / px, last

    L = ["研究 63d：爆量收黑買進——台指期真實價格（近月；換月接續、扣 2 點；成本每筆 3 點）",
         f"資料：{dates[0]}～{dates[-1]}，{n} 個交易日；夜盤（盤後）{sum(1 for d in dates if night[d])} 天"]
    rng = random.Random(634)
    first_night = next((d for d in dates if night[d]), "2017-05-16")
    for vsrc, k in (("成交金額", 1.5), ("成交金額", 1.3), ("台指期口數", 1.5), ("台指期口數", 2.0)):
        ser = amt if vsrc == "成交金額" else VOLF
        sig = [i for i in range(21, n - 1) if dates[i] >= "1998-09-01" and (v := vr(ser, i)) is not None and v >= k and C[i] < day[dates[i - 1]].get(near[dates[i]], (0, 0, 0, C[i - 1]))[3]]
        L.append(f"\n== {vsrc} ≥{k}x 且台指期收黑：{len(sig)} 天 ==")
        for H in (1, 3, 5, 10):
            for how, nm in (("n", "當晚夜盤開"), ("o", "隔天開盤"), ("c", "隔天收盤")):
                for lab, lo, hi in (("全期", "1998", "2027"), ("2017-05後", first_night, "2027")) if how != "n" else (("2017-05後", first_night, "2027"),):
                    trs, busy = [], -1
                    for i in sig:
                        if not (lo <= dates[i] < hi) or i + 1 <= busy:
                            continue
                        r = entry_ret(i, how, H)
                        if r is None:
                            continue
                        trs.append(r[0])
                        busy = r[1]
                    if len(trs) < 5:
                        continue
                    pool = [i for i in range(21, n - H - 1) if lo <= dates[i] < hi]
                    rnd = []
                    for _ in range(1000):
                        xs = []
                        for _t in trs:
                            r = entry_ret(rng.choice(pool), how, H)
                            if r:
                                xs.append(r[0])
                        rnd.append(statistics.mean(xs))
                    rnd.sort()
                    ev = statistics.mean(trs)
                    p = (sum(x >= ev for x in rnd) + 1) / 1001
                    L.append(f"  抱{H:2d}天 {nm:5s} {lab:8s} {len(trs):3d} 筆 勝率 {sum(t > 0 for t in trs) / len(trs):4.0%} 每筆 {ev:+.2%}"
                             f"（≈{ev * 40000:+5.0f} 點）  隨機 {rnd[500]:+.2%}  p＝{p:.3f}  最差 {min(trs):+.1%}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究63d_台指期真實價.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
