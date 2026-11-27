"""研究 303：52 週高點選股（含息）與主策略 v3 結合

月頻（2015-10～，NH 為每月第一個交易日換股、0050／V3 為月底到月底，差 1 個交易日），全部含息、扣成本：
  NH5／NH10＝52 週高點（250 日）前 5％／10％ 等權（研究 302 還原價、換手扣 0.585%）
  0050＝Yahoo 調整價；V3＝strategy_v3.run(real=True) 每日淨值換成月報酬（2x、00631L 真實價）
組合：
  A 0050 持有｜B NH10｜C 50% 0050＋50% NH10（每月再平衡）
  D V3｜E V3＋空手時改持 NH10（以該月空手天數比例 f：V3 月報酬 ＋ f×(NH10 − 現金)）
  F V3＋空手時持 0050（對照：差別只在空手時拿什麼）
用法：python -X utf8 backtest/research_303_52週高點結合主策略.py
"""
import importlib.util
import json
import math
import os
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r302", os.path.join(HERE, "research_302_52週高點含息.py"))
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)
import strategy_v3 as s  # noqa: E402

COST = 0.00585


def nh_series(px, qs=(0.05, 0.10)):
    dates = sorted({d for m in px.values() for d in m})
    me = [d for a, d in zip(dates, dates[1:] + ["9999"]) if d[:7] != a[:7]]
    bad = defaultdict(set)
    for c, m in px.items():
        ds = sorted(m)
        for a, b in zip(ds, ds[1:]):
            if m[a] > 0 and abs(m[b] / m[a] - 1) > 0.11:
                bad[c].add(b[:7])
    dly = {c: sorted(m.items()) for c, m in px.items()}
    pos = {c: {d: q for q, (d, _) in enumerate(v)} for c, v in dly.items()}
    out = {q: {} for q in qs}
    prev = {q: set() for q in qs}
    for k in range(12, len(me) - 1):
        t, t1 = me[k], me[k + 1]
        cand = []
        for c, m in px.items():
            if t not in m or t1 not in m or m[t] < 10 or t1[:7] in bad[c]:
                continue
            if any(me[j][:7] in bad[c] for j in range(k - 11, k + 1)):
                continue
            j = pos[c][t]
            if j < 250:
                continue
            ds = dly[c]
            ratio = ds[j][1] / max(ds[q][1] for q in range(j - 249, j + 1))
            cand.append((c, ratio, m[t1] / m[t] - 1))
        if len(cand) < 200:
            continue
        for q in qs:
            n = int(len(cand) * q)
            top = sorted(cand, key=lambda x: x[1], reverse=True)[:n]
            hold = {x[0] for x in top}
            turn = 1 - len(hold & prev[q]) / len(hold)
            prev[q] = hold
            out[q][t[:7]] = statistics.mean(x[2] for x in top) - turn * COST  # t＝當月第一個交易日（研究 299～302 的 me 是月初）
    return out


def monthly_from_daily(days, vals):
    last = {}
    for d, v in zip(days, vals):
        last[d[:7]] = v
    ms = sorted(last)
    return {m: last[m] / last[p] - 1 for p, m in zip(ms, ms[1:])}


def perf(r):
    g = math.prod(1 + x for x in r)
    cagr = g ** (12 / len(r)) - 1
    lv = pk = 1.0
    mdd = 0.0
    for x in r:
        lv *= 1 + x
        pk = max(pk, lv)
        mdd = min(mdd, lv / pk - 1)
    sh = statistics.mean(r) / statistics.pstdev(r) * math.sqrt(12)
    return f"年化 {cagr * 100:+6.1f}%  最大回檔(月) {mdd * 100:6.1f}%  Sharpe {sh:.2f}"


def main():
    nh = nh_series(A.adjusted_load())
    # 0050
    j = json.load(open(os.path.join(HERE, "0050.TW.json"), encoding="utf-8"))
    tw = timezone(timedelta(hours=8))
    adj = j["indicators"]["adjclose"][0]["adjclose"]
    d50 = [(datetime.fromtimestamp(ts, tw).strftime("%Y-%m-%d"), v) for ts, v in zip(j["timestamp"], adj) if v]
    m50 = monthly_from_daily([d for d, _ in d50], [v for _, v in d50])
    # V3 每日淨值與空手日
    i0 = next(i for i, d in enumerate(s.DAYS) if d >= "2015-09-01")  # 00631L 真實價 2015-08 前有錯價
    _, _, curve = s.run("2015-09-01", s.DAYS[-1], real=True, curve=True)
    days = s.DAYS[i0:i0 + len(curve)]
    mv3 = monthly_from_daily(days, curve)
    rc = s.bt.RC
    cashfrac = defaultdict(list)
    for k in range(1, len(curve)):
        r = curve[k] / curve[k - 1] - 1
        cashfrac[days[k][:7]].append(abs(r - rc) < 1e-12)
    f = {m: sum(v) / len(v) for m, v in cashfrac.items()}
    rcm = (1 + rc) ** 21 - 1
    months = sorted(set(nh[0.10]) & set(m50) & set(mv3))
    out = [f"研究 303：52 週高點選股與主策略結合（{months[0]}～{months[-1]}，{len(months)} 個月，含息、扣成本）\n",
           f"V3 空手月份比例（以天計）：平均 {statistics.mean(f[m] for m in months) * 100:.0f}%\n"]
    combos = {
        "A 0050 持有": [m50[m] for m in months],
        "B NH10": [nh[0.10][m] for m in months],
        "B' NH5": [nh[0.05][m] for m in months],
        "C 50% 0050＋50% NH10": [(m50[m] + nh[0.10][m]) / 2 for m in months],
        "D V3（2x）": [mv3[m] for m in months],
        "E V3＋空手持 NH10": [mv3[m] + f[m] * (nh[0.10][m] - rcm) for m in months],
        "F V3＋空手持 0050": [mv3[m] + f[m] * (m50[m] - rcm) for m in months],
    }
    for k, r in combos.items():
        out.append(f"{k:<22} {perf(r)}")
    # 分段
    half = len(months) // 2
    out.append(f"\n前半（{months[0]}～{months[half - 1]}）／後半：")
    for k in ("A 0050 持有", "B NH10", "D V3（2x）", "E V3＋空手持 NH10"):
        out.append(f"  {k:<20} 前 {perf(combos[k][:half])}")
        out.append(f"  {'':<20} 後 {perf(combos[k][half:])}")
    c = statistics.correlation(combos["A 0050 持有"], combos["B NH10"])
    out.append(f"\n0050 與 NH10 月報酬相關 {c:.2f}")
    text = "\n".join(out)
    print(text)
    open(os.path.join(HERE, "結果_研究303_52週高點結合主策略.txt"), "w", encoding="utf-8").write(text + "\n")


if __name__ == "__main__":
    main()
