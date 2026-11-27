"""研究 304：52 週高點選股實務化——持股數與換股頻率

同研究 302／303（還原除權息、每月第一個交易日排名、股價 ≥10、250 日、12 個月無 >±11% 跳動），
持股：固定前 N 檔（20／30／50）或前 10%；換股頻率：每月、每季（只在 1／4／7／10 月月初換，其餘月份續抱）；
換手扣 0.585%。輸出年化、最大回檔（月）、Sharpe、年均換手。
用法：python -X utf8 backtest/research_304_選股持股數與頻率.py
"""
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


def main():
    px = A.adjusted_load()
    dates = sorted({d for m in px.values() for d in m})
    me = [d for a, d in zip([""] + dates, dates) if d[:7] != a[:7]]  # 每月第一個交易日
    bad = defaultdict(set)
    for c, m in px.items():
        ds = sorted(m)
        for a, b in zip(ds, ds[1:]):
            if m[a] > 0 and abs(m[b] / m[a] - 1) > 0.11:
                bad[c].add(b[:7])
    dly = {c: sorted(m.items()) for c, m in px.items()}
    pos = {c: {d: q for q, (d, _) in enumerate(v)} for c, v in dly.items()}
    sizes = (20, 30, 50, "10%")
    freqs = ("月", "季")
    rets = defaultdict(list)
    turns = defaultdict(list)
    hold = {(n, f): [] for n in sizes for f in freqs}
    months = []
    for k in range(12, len(me) - 1):
        t, t1 = me[k], me[k + 1]
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
            cand.append((c, ds[j][1] / max(ds[q][1] for q in range(j - 249, j + 1))))
        if len(cand) < 200:
            continue
        cand.sort(key=lambda x: -x[1])
        months.append(t[:7])
        for n in sizes:
            nn = int(len(cand) * 0.10) if n == "10%" else n
            top = [c for c, _ in cand[:nn]]
            for f in freqs:
                key = (n, f)
                old = hold[key]
                if f == "月" or t[5:7] in ("01", "04", "07", "10") or not old:
                    new = top
                else:
                    new = old
                turn = 1 - len(set(new) & set(old)) / len(new) if old else 1.0
                hold[key] = new
                # 下個月報酬：持股中 t1 沒報價（下市）的以 -100%？保守：當月有 >±11% 跳動或下市者以 0 報酬計並記錄
                rs = []
                for c in new:
                    m = px[c]
                    if t1 in m and t in m and t1[:7] not in bad[c]:
                        rs.append(m[t1] / m[t] - 1)
                    elif t1 in m and t in m:
                        rs.append(m[t1] / m[t] - 1)
                    else:
                        rs.append(0.0)
                rets[key].append(statistics.mean(rs) - turn * COST)
                turns[key].append(turn)
    out = [f"研究 304：52 週高點選股 持股數 × 換股頻率（{months[0]}～{months[-1]}，{len(months)} 個月，含息、扣 0.585% 換手成本）\n",
           "持股     頻率   年化     最大回檔   Sharpe   年換手"]
    for n in sizes:
        for f in freqs:
            r = rets[(n, f)]
            g = math.prod(1 + x for x in r)
            cagr = g ** (12 / len(r)) - 1
            lv = pk = 1.0
            mdd = 0.0
            for x in r:
                lv *= 1 + x
                pk = max(pk, lv)
                mdd = min(mdd, lv / pk - 1)
            sh = statistics.mean(r) / statistics.pstdev(r) * math.sqrt(12)
            out.append(f"{str(n):<6}   {f}     {cagr * 100:+6.1f}%   {mdd * 100:6.1f}%    {sh:.2f}     {statistics.mean(turns[(n, f)]) * 12 * 100:4.0f}%")
    text = "\n".join(out)
    print(text)
    open(os.path.join(HERE, "結果_研究304_選股持股數與頻率.txt"), "w", encoding="utf-8").write(text + "\n")


if __name__ == "__main__":
    main()
