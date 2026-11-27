"""研究 301b：52 週高點接近度選股的穩健性

格點：高點回看 L＝120／200／250 日 × 持股比例 q＝5／10／20%（等權、每月換、換手扣 0.585%）；
對照等權全市場（同樣未還原股利）；每格報年化、最大回檔、月超額 t。
另：與 12-1 動能前 10% 的持股重疊比例（平均）；兩者等權混合的結果。
資料同研究 299（`stock_closes` 未還原股利、股價 ≥10 元、月內 >±11% 跳動剔除）。
用法：python -X utf8 backtest/research_301b_52週高點穩健性.py
"""
import importlib.util
import math
import os
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("r299", os.path.join(HERE, "research_299_全市場動能.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
COST = R.COST


def perf(r):
    g = math.prod(1 + x for x in r)
    cagr = g ** (12 / len(r)) - 1
    lv = pk = 1.0
    mdd = 0.0
    for x in r:
        lv *= 1 + x
        pk = max(pk, lv)
        mdd = min(mdd, lv / pk - 1)
    return cagr * 100, mdd * 100


def main():
    px = R.load()
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
    LS, QS = (120, 200, 250), (0.05, 0.10, 0.20)
    rets = defaultdict(list)
    prev = defaultdict(set)
    overlap = []
    for k in range(12, len(me) - 1):
        t, t1 = me[k], me[k + 1]
        cand = []
        for c, m in px.items():
            if t not in m or t1 not in m or me[k - 12] not in m or m[t] < 10:
                continue
            if t1[:7] in bad[c] or any(me[j][:7] in bad[c] for j in range(k - 11, k + 1)):
                continue
            j = pos[c][t]
            if j < 250:
                continue
            ds = dly[c]
            closes = [ds[q][1] for q in range(j - 249, j + 1)]
            ratio = {L: closes[-1] / max(closes[-L:]) for L in LS}
            mom = m[me[k - 1]] / m[me[k - 12]] - 1 if me[k - 1] in m else None
            if mom is None:
                continue
            cand.append((c, ratio, mom, m[t1] / m[t] - 1))
        if len(cand) < 200:
            continue
        rets["EW"].append(statistics.mean(x[3] for x in cand))
        for L in LS:
            for q in QS:
                n = max(1, int(len(cand) * q))
                top = sorted(cand, key=lambda x: x[1][L], reverse=True)[:n]
                hold = {x[0] for x in top}
                key = (L, q)
                turn = 1 - len(hold & prev[key]) / len(hold)
                prev[key] = hold
                rets[key].append(statistics.mean(x[3] for x in top) - turn * COST)
        n10 = len(cand) // 10
        hi = {x[0] for x in sorted(cand, key=lambda x: x[1][250], reverse=True)[:n10]}
        mo = {x[0] for x in sorted(cand, key=lambda x: x[2], reverse=True)[:n10]}
        overlap.append(len(hi & mo) / n10)
    ew = rets["EW"]
    out = [f"研究 301b：52 週高點穩健性（{len(ew)} 個月，未還原股利）\n",
           f"等權全市場：年化 {perf(ew)[0]:+.1f}%、回檔 {perf(ew)[1]:.1f}%\n",
           "L\\q        5%                       10%                      20%"]
    for L in LS:
        cells = []
        for q in QS:
            r = rets[(L, q)]
            c, d = perf(r)
            diff = [a - b for a, b in zip(r, ew)]
            t = statistics.mean(diff) / (statistics.pstdev(diff) / math.sqrt(len(diff)))
            cells.append(f"{c:+5.1f}%／{d:5.1f}%／t{t:+.2f}")
        out.append(f"{L:>3} 日   " + "   ".join(cells))
    out.append("（格式：扣成本年化／最大回檔／月超額 t）")
    out.append(f"\n近高點 10%（250 日）與 12-1 動能前 10% 的持股重疊：平均 {statistics.mean(overlap) * 100:.0f}%")
    text = "\n".join(out)
    print(text)
    open(os.path.join(HERE, "結果_研究301b_52週高點穩健性.txt"), "w", encoding="utf-8").write(text + "\n")


if __name__ == "__main__":
    main()
