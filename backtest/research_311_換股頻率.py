"""研究 311：52 週高點選股換股頻率——每週／每兩週／每月

可交易版（研究 307）：流動性用「當月第一個交易日成交金額 ≥1,000 萬」（`turnover_monthfirst.csv`，同月內各換股日共用）；
含息還原、無前視、股價 ≥10、250 日、近 12 個月無 >±11% 跳動；前 30 檔等權；換手扣 0.585%。
換股日：每週第一個交易日／每兩週（隔週）／每月第一個交易日；持有到下個換股日收盤。
用法：python -X utf8 backtest/research_311_換股頻率.py
"""
import csv
import datetime as dt
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
COST, N = 0.00585, 30


def main():
    px = A.adjusted_load()
    amt = defaultdict(dict)
    for r in csv.DictReader(open(os.path.join(HERE, "turnover_monthfirst.csv"), encoding="utf-8")):
        amt[r["date"][:7]][r["code"]] = float(r["amount"])
    dates = sorted({d for m in px.values() for d in m})
    mfirst = [d for a, d in zip([""] + dates, dates) if d[:7] != a[:7]]
    wk = lambda d: dt.date.fromisoformat(d).isocalendar()[:2]  # noqa: E731
    wfirst = [d for a, d in zip([""] + dates, dates) if not a or wk(d) != wk(a)]
    bad = defaultdict(set)
    for c, m in px.items():
        ds = sorted(m)
        for a, b in zip(ds, ds[1:]):
            if m[a] > 0 and abs(m[b] / m[a] - 1) > 0.11:
                bad[c].add(b[:7])
    dly = {c: sorted(m.items()) for c, m in px.items()}
    pos = {c: {d: q for q, (d, _) in enumerate(v)} for c, v in dly.items()}
    mi = {m: k for k, m in enumerate(sorted({d[:7] for d in dates}))}
    months = sorted({d[:7] for d in dates})
    cache = {}

    def top_at(t):
        if t in cache:
            return cache[t]
        k = mi[t[:7]]
        if k < 12 or t[:7] not in amt:
            cache[t] = None
            return None
        m12 = [d for d in mfirst if d[:7] == months[k - 12]]
        recent = set(months[k - 11:k + 1])
        cand = []
        for c, m in px.items():
            if t not in m or m[t] < 10 or not m12 or m12[0] not in m or amt[t[:7]].get(c, 0.0) < 1e7:
                continue
            if bad[c] & recent:
                continue
            j = pos[c][t]
            if j < 250:
                continue
            ds = dly[c]
            cand.append((c, ds[j][1] / max(ds[q][1] for q in range(j - 249, j + 1))))
        if len(cand) < 100:
            cache[t] = None
            return None
        cand.sort(key=lambda x: -x[1])
        cache[t] = [c for c, _ in cand[:N]]
        return cache[t]

    out = ["研究 311：52 週高點前 30 檔 換股頻率（可交易版、含息、扣 0.585%）\n",
           "頻率     期數   年化     最大回檔   Sharpe   年換手"]
    for lab, sched in (("每週", wfirst), ("每兩週", wfirst[::2]), ("每月", mfirst)):
        r, prev, turns = [], [], []
        start = None
        for t, t1 in zip(sched, sched[1:]):
            top = top_at(t)
            if top is None:
                continue
            start = start or t
            g = statistics.mean((px[c][t1] / px[c][t] - 1) if t1 in px[c] else 0.0 for c in top)
            turn = 1 - len(set(top) & set(prev)) / N if prev else 1.0
            prev = top
            turns.append(turn)
            r.append(g - turn * COST)
        yrs = (dt.date.fromisoformat(sched[-1]) - dt.date.fromisoformat(start)).days / 365.25
        g = math.prod(1 + x for x in r)
        lv = pk = 1.0
        mdd = 0.0
        for x in r:
            lv *= 1 + x
            pk = max(pk, lv)
            mdd = min(mdd, lv / pk - 1)
        per = len(r) / yrs
        sh = statistics.mean(r) / statistics.pstdev(r) * math.sqrt(per)
        out.append(f"{lab:<6}  {len(r):>4}   {(g ** (1 / yrs) - 1) * 100:+6.1f}%  {mdd * 100:6.1f}%    {sh:.2f}   {sum(turns) / yrs * 100:5.0f}%")
    text = "\n".join(out)
    print(text)
    open(os.path.join(HERE, "結果_研究311_換股頻率.txt"), "w", encoding="utf-8").write(text + "\n")


if __name__ == "__main__":
    main()
