"""研究 309：可交易版因子比較（含息、無前視、選股日成交金額 ≥1,000 萬、股價 ≥10、月初換、扣 0.585%）

各取前 30 檔等權：
  NH＝52 週高點接近度（還原收盤 ÷ 250 日最高）
  MOM＝12-1 動能（12 個月前月初 → 1 個月前月初）
  LV＝60 日日報酬標準差最低
  NH+MOM＝兩者百分位排名平均
對照：可交易候選等權（EW）
用法：python -X utf8 backtest/research_309_可交易版因子比較.py
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
COST, N = 0.00585, 30


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


def rank_pct(vals):
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    r = [0.0] * len(vals)
    for k, i in enumerate(order):
        r[i] = k / (len(vals) - 1)
    return r


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
    for k in range(12, len(me) - 1):
        t, t1 = me[k], me[k + 1]
        cand = []
        for c, m in px.items():
            if t not in m or m[t] < 10 or me[k - 12] not in m or me[k - 1] not in m or amt[t].get(c, 0.0) < 1e7:
                continue
            if any(me[j][:7] in bad[c] for j in range(k - 11, k + 1)):
                continue
            j = pos[c][t]
            if j < 250:
                continue
            ds = dly[c]
            nh = ds[j][1] / max(ds[q][1] for q in range(j - 249, j + 1))
            mom = m[me[k - 1]] / m[me[k - 12]] - 1
            vol = statistics.pstdev([ds[q][1] / ds[q - 1][1] - 1 for q in range(j - 59, j + 1)])
            fwd = (m[t1] / m[t] - 1) if t1 in m else 0.0
            cand.append((c, nh, mom, -vol, fwd))
        if len(cand) < 100:
            continue
        rn, rm = rank_pct([x[1] for x in cand]), rank_pct([x[2] for x in cand])
        combo = [(a + b) / 2 for a, b in zip(rn, rm)]
        rets["EW"].append(statistics.mean(x[4] for x in cand))
        for name, key in (("NH", lambda i: cand[i][1]), ("MOM", lambda i: cand[i][2]), ("LV", lambda i: cand[i][3]), ("NH+MOM", lambda i: combo[i])):
            idx = sorted(range(len(cand)), key=key, reverse=True)[:N]
            top = [cand[i][0] for i in idx]
            turn = 1 - len(set(top) & set(prev[name])) / N if prev[name] else 1.0
            prev[name] = top
            rets[name].append(statistics.mean(cand[i][4] for i in idx) - turn * COST)
            rets[name + "_turn"].append(turn)
    out = [f"研究 309：可交易版因子比較（{len(rets['EW'])} 個月；≥1,000 萬、含息、無前視、前 30 檔、扣成本）\n",
           "因子      年化     最大回檔   Sharpe   年換手   月超額 vs EW（t）"]
    for name in ("NH", "MOM", "LV", "NH+MOM", "EW"):
        c, d, sh = perf(rets[name])
        if name == "EW":
            out.append(f"{name:<8} {c:+6.1f}%  {d:6.1f}%    {sh:.2f}")
            continue
        diff = [a - b for a, b in zip(rets[name], rets["EW"])]
        t = statistics.mean(diff) / (statistics.pstdev(diff) / math.sqrt(len(diff)))
        out.append(f"{name:<8} {c:+6.1f}%  {d:6.1f}%    {sh:.2f}    {statistics.mean(rets[name + '_turn']) * 1200:4.0f}%   {statistics.mean(diff) * 100:+.2f}%（{t:+.2f}）")
    text = "\n".join(out)
    print(text)
    open(os.path.join(HERE, "結果_研究309_可交易版因子比較.txt"), "w", encoding="utf-8").write(text + "\n")


if __name__ == "__main__":
    main()
