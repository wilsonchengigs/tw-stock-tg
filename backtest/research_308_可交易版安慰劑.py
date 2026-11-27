"""研究 308：可交易版（選股日成交金額 ≥1,000 萬，研究 307）52 週高點前 30 檔 vs 隨機 30 檔；0050＋選股各半（由研究 306 改寫）

同研究 304／305（含息、無前視、每月第一個交易日換、扣 0.585% 換手）。
安慰劑：每月從同一批候選（通過同樣篩選的股票）隨機抽 30 檔，換手照算（隨機持股每月幾乎全換，成本較高，
所以另算「不扣成本」的比較），重複 200 次，看 NH30 的年化與 Sharpe 排名。
組合：0050（Yahoo 含息，月初對月初）50%＋NH30 50%，每月再平衡。
用法：python -X utf8 backtest/research_306_隨機選股安慰劑.py
"""
import csv
import importlib.util
import json
import math
import os
import random
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r302", os.path.join(HERE, "research_302_52週高點含息.py"))
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)
COST, N, RUNS = 0.00585, 30, 200


def perf(r):
    g = math.prod(1 + x for x in r)
    cagr = g ** (12 / len(r)) - 1
    lv = pk = 1.0
    mdd = 0.0
    for x in r:
        lv *= 1 + x
        pk = max(pk, lv)
        mdd = min(mdd, lv / pk - 1)
    return cagr * 100, mdd * 100, statistics.mean(r) / statistics.pstdev(r) * math.sqrt(12)


def main():
    px = A.adjusted_load()
    amt = defaultdict(dict)
    for r in csv.DictReader(open(os.path.join(HERE, "turnover_monthfirst.csv"), encoding="utf-8")):
        amt[r["date"]][r["code"]] = float(r["amount"])
    dates = sorted({d for m in px.values() for d in m})
    me = [d for a, d in zip([""] + dates, dates) if d[:7] != a[:7]]
    bad = defaultdict(set)
    for c, m in px.items():
        ds = sorted(m)
        for a, b in zip(ds, ds[1:]):
            if m[a] > 0 and abs(m[b] / m[a] - 1) > 0.11:
                bad[c].add(b[:7])
    dly = {c: sorted(m.items()) for c, m in px.items()}
    pos = {c: {d: q for q, (d, _) in enumerate(v)} for c, v in dly.items()}
    months = []  # (t, t1, cand sorted, fwd dict)
    for k in range(12, len(me) - 1):
        t, t1 = me[k], me[k + 1]
        cand = []
        for c, m in px.items():
            if t not in m or m[t] < 10 or me[k - 12] not in m or amt[t].get(c, 0.0) < 1e7:
                continue
            if any(me[j][:7] in bad[c] for j in range(k - 11, k + 1)):
                continue
            j = pos[c][t]
            if j < 250:
                continue
            ds = dly[c]
            cand.append((c, ds[j][1] / max(ds[q][1] for q in range(j - 249, j + 1))))
        if len(cand) < 200:
            continue
        cand.sort(key=lambda x: -x[1])
        fwd = {c: (px[c][t1] / px[c][t] - 1) if t1 in px[c] else 0.0 for c, _ in cand}
        months.append((t, t1, [c for c, _ in cand], fwd))

    def run(picker):
        r, g, prev = [], [], []
        for mi, (t, t1, cs, fwd) in enumerate(months):
            top = picker(mi, cs)
            gross = statistics.mean(fwd[c] for c in top)
            turn = 1 - len(set(top) & set(prev)) / len(top) if prev else 1.0
            prev = top
            g.append(gross)
            r.append(gross - turn * COST)
        return r, g

    nh, nh_g = run(lambda mi, cs: cs[:N])
    rnd = random.Random(308)
    sims = [run(lambda mi, cs: rnd.sample(cs, N)) for _ in range(RUNS)]
    c0, d0, s0 = perf(nh)
    cg0, _, sg0 = perf(nh_g)
    sc = [perf(x[0]) for x in sims]
    sg = [perf(x[1]) for x in sims]
    out = [f"研究 308：可交易版 NH30 vs 隨機 30 檔（{months[0][0][:7]}～{months[-1][0][:7]}，{len(months)} 月，{RUNS} 次）\n",
           f"NH30 扣成本：年化 {c0:+.1f}%、回檔 {d0:.1f}%、Sharpe {s0:.2f}｜不扣：{cg0:+.1f}%、Sharpe {sg0:.2f}",
           f"隨機 30 檔扣成本：年化 中位 {statistics.median(x[0] for x in sc):+.1f}%（5%～95% {sorted(x[0] for x in sc)[RUNS // 20]:+.1f}～{sorted(x[0] for x in sc)[RUNS * 19 // 20]:+.1f}%）、回檔中位 {statistics.median(x[1] for x in sc):.1f}%、Sharpe 中位 {statistics.median(x[2] for x in sc):.2f}",
           f"隨機 30 檔不扣：年化 中位 {statistics.median(x[0] for x in sg):+.1f}%、最高 {max(x[0] for x in sg):+.1f}%、Sharpe 最高 {max(x[2] for x in sg):.2f}",
           f"NH30（不扣）勝過隨機（不扣）的比例：年化 {sum(cg0 > x[0] for x in sg) / RUNS * 100:.1f}%、Sharpe {sum(sg0 > x[2] for x in sg) / RUNS * 100:.1f}%（p≈{(1 + sum(cg0 <= x[0] for x in sg)) / (RUNS + 1):.3f}）"]
    # 0050 各半
    j = json.load(open(os.path.join(HERE, "0050.TW.json"), encoding="utf-8"))
    tw = timezone(timedelta(hours=8))
    e50 = {datetime.fromtimestamp(ts, tw).strftime("%Y-%m-%d"): v for ts, v in zip(j["timestamp"], j["indicators"]["adjclose"][0]["adjclose"]) if v}
    r50 = [(e50[t1] / e50[t] - 1) if t in e50 and t1 in e50 else 0.0 for t, t1, _, _ in months]
    mix = [(a + b) / 2 for a, b in zip(r50, nh)]
    for lab, r in (("0050", r50), ("NH30", nh), ("各半", mix)):
        c, d, sh = perf(r)
        out.append(f"{lab:<5} 年化 {c:+.1f}%、回檔 {d:.1f}%、Sharpe {sh:.2f}")
    out.append(f"0050 與 NH30 月報酬相關 {statistics.correlation(r50, nh):.2f}")
    text = "\n".join(out)
    print(text)
    open(os.path.join(HERE, "結果_研究308_可交易版安慰劑.txt"), "w", encoding="utf-8").write(text + "\n")


if __name__ == "__main__":
    main()
