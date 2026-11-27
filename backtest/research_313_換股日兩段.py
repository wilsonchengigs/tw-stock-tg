"""研究 313：換股日位置分兩段（2014–2019／2020～，由研究 312 改寫）。原：研究 312：52 週高點選股換股日在月內的位置（由研究 311 改寫）——每月第 1／6／11／16 個交易日換股；原說明：

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

    out = ["研究 312：52 週高點前 30 檔 每月換股日位置（可交易版、含息、扣 0.585%；成交金額用當月第一個交易日）\n",
           "換股日   期數   年化     最大回檔   Sharpe   年換手"]
    bym = defaultdict(list)
    for d in dates:
        bym[d[:7]].append(d)
    scheds = []
    for nth in range(1, 19):
        scheds.append((f"第{nth}日", [v[nth - 1] for m, v in sorted(bym.items()) if len(v) >= nth]))
    def cagr(rs):
        g = math.prod(1 + x for x in rs)
        return (g ** (12 / len(rs)) - 1) * 100

    rows = {}
    for lab, sched in scheds:
        seg = {"a": [], "b": []}
        prev = []
        for t, t1 in zip(sched, sched[1:]):
            top = top_at(t)
            if top is None:
                continue
            g = statistics.mean((px[c][t1] / px[c][t] - 1) if t1 in px[c] else 0.0 for c in top)
            turn = 1 - len(set(top) & set(prev)) / N if prev else 1.0
            prev = top
            seg["a" if t < "2020-01-01" else "b"].append(g - turn * COST)
        rows[lab] = (cagr(seg["a"]), cagr(seg["b"]), len(seg["a"]), len(seg["b"]))
    out = ["研究 313：換股日位置兩段（可交易版前 30 檔、含息、扣成本；年化）", "", "換股日   2014–2019   2020～"]
    for lab, (a, b, na, nb) in rows.items():
        out.append(f"{lab:<6}  {a:+7.1f}%   {b:+7.1f}%   （{na}／{nb} 期）")
    mid = [k for k in rows if k in ("第6日", "第7日", "第8日", "第9日", "第10日", "第11日", "第12日")]
    oth = [k for k in rows if k not in mid]
    for i2, name in ((0, "2014–2019"), (1, "2020～")):
        a = statistics.mean(rows[k][i2] for k in mid)
        b = statistics.mean(rows[k][i2] for k in oth)
        rk = sorted(rows, key=lambda k: -rows[k][i2])
        out.append(f"{name}：第 6～12 日平均 {a:+.1f}% vs 其他日 {b:+.1f}%；前 7 名 " + "、".join(rk[:7]))
    a_ = [rows[k][0] for k in rows]
    b_ = [rows[k][1] for k in rows]
    out.append(f"兩段各日年化的相關係數 {statistics.correlation(a_, b_):+.2f}（高＝同樣的日子兩段都好）")
    text = "\n".join(out)
    print(text)
    open(os.path.join(HERE, "結果_研究313_換股日兩段.txt"), "w", encoding="utf-8").write(text + "\n")


if __name__ == "__main__":
    main()
