"""研究 307：52 週高點選股的流動性門檻

選股日（每月第一個交易日）成交金額門檻：0／500 萬／1,000 萬／3,000 萬／1 億（`turnover_monthfirst.csv`，單日值）；
門檻內再取 52 週高點前 30 檔、前 10%；其餘同研究 304～306（含息、無前視、月換、扣 0.585%）。
另列各門檻下候選數與 NH30 平均成交金額。
用法：python -X utf8 backtest/research_307_選股流動性.py
"""
import csv
import importlib.util
import math
import os
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r302", os.path.join(HERE, "research_302_52週高點含息.py"))
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)
COST = 0.00585
THS = (0, 5e6, 1e7, 3e7, 1e8)


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
    rets = defaultdict(list)
    prev = defaultdict(list)
    ncand = defaultdict(list)
    avg_amt = defaultdict(list)
    for k in range(12, len(me) - 1):
        t, t1 = me[k], me[k + 1]
        if t not in amt:
            continue
        cand = []
        for c, m in px.items():
            if t not in m or m[t] < 10 or me[k - 12] not in m:
                continue
            if any(me[j][:7] in bad[c] for j in range(k - 11, k + 1)):
                continue
            j = pos[c][t]
            if j < 250:
                continue
            ds = dly[c]
            cand.append((c, ds[j][1] / max(ds[q][1] for q in range(j - 249, j + 1)), amt[t].get(c, 0.0)))
        if len(cand) < 200:
            continue
        cand.sort(key=lambda x: -x[1])
        for th in THS:
            cs = [x for x in cand if x[2] >= th]
            ncand[th].append(len(cs))
            for lab, n in (("30", 30), ("10%", int(len(cs) * 0.10))):
                top = [x[0] for x in cs[:n]]
                if lab == "30":
                    avg_amt[th].append(statistics.median(x[2] for x in cs[:n]))
                key = (th, lab)
                g = statistics.mean((px[c][t1] / px[c][t] - 1) if t1 in px[c] else 0.0 for c in top)
                turn = 1 - len(set(top) & set(prev[key])) / len(top) if prev[key] else 1.0
                prev[key] = top
                rets[key].append(g - turn * COST)
    out = [f"研究 307：52 週高點選股 流動性門檻（{len(rets[(0, '30')])} 個月，含息、無前視、扣成本）\n",
           "門檻（選股日成交金額）  候選數   NH30 成交金額中位   前 30 檔 年化／回檔／Sharpe     前 10% 年化／回檔／Sharpe"]
    for th in THS:
        a = perf(rets[(th, "30")])
        b = perf(rets[(th, "10%")])
        out.append(f"≥{th / 1e4:>6.0f} 萬            {statistics.mean(ncand[th]):5.0f}    {statistics.median(avg_amt[th]) / 1e4:8.0f} 萬"
                   f"       {a[0]:+6.1f}%／{a[1]:6.1f}%／{a[2]:.2f}       {b[0]:+6.1f}%／{b[1]:6.1f}%／{b[2]:.2f}")
    text = "\n".join(out)
    print(text)
    open(os.path.join(HERE, "結果_研究307_選股流動性.txt"), "w", encoding="utf-8").write(text + "\n")


if __name__ == "__main__":
    main()
