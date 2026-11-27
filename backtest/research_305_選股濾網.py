"""研究 305：52 週高點選股——持股數鄰近參數＋大盤濾網

同研究 304（含息、無前視、每月第一個交易日換、扣 0.585%）。
(1) 持股 15／20／25／30／35／40／50／60 檔，月換
(2) 大盤濾網（換股日判斷，整月持有或整月現金；現金報酬 1%／年）：
    F0 無濾網｜F1 加權收盤 > MA200｜F2 加權收盤 > MA60×1.01（主策略進場線，簡化：不含出場線遲滯與融資過熱）
    切換時全部換手計成本
用法：python -X utf8 backtest/research_305_選股濾網.py
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
import strategy_v3 as s  # noqa: E402

COST = 0.00585
CASH_M = 0.01 / 12


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
    return cagr * 100, mdd * 100, sh


def main():
    px = A.adjusted_load()
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
    idx = {d: i for i, d in enumerate(s.DAYS)}
    P = s.PX
    ma = lambda i, n: sum(P[i - n + 1:i + 1]) / n  # noqa: E731
    sizes = (15, 20, 25, 30, 35, 40, 50, 60)
    filt = {"F0 無": lambda i: True, "F1 >MA200": lambda i: P[i] > ma(i, 200), "F2 >MA60×1.01": lambda i: P[i] > ma(i, 60) * 1.01}
    rets = defaultdict(list)
    prev = defaultdict(list)
    inmkt = defaultdict(list)
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
        if len(cand) < 200 or t not in idx:
            continue
        cand.sort(key=lambda x: -x[1])
        i = idx[t]
        for n in sizes:
            top = [c for c, _ in cand[:n]]
            rs = [(px[c][t1] / px[c][t] - 1) if t1 in px[c] else 0.0 for c in top]
            gross = statistics.mean(rs)
            for fn, f in filt.items():
                if n not in (20, 30, 40) and fn != "F0 無":
                    continue
                key = (n, fn)
                on = f(i)
                old = prev[key]
                if on:
                    turn = 1 - len(set(top) & set(old)) / len(top) if old else 1.0
                    rets[key].append(gross - turn * COST)
                    prev[key] = top
                else:
                    rets[key].append(CASH_M - (COST if old else 0.0))
                    prev[key] = []
                inmkt[key].append(on)
    out = [f"研究 305：52 週高點選股 鄰近參數＋大盤濾網（{len(rets[(30, 'F0 無')])} 個月，含息、無前視、扣成本）\n",
           "(1) 持股數（月換、無濾網）：年化／最大回檔／Sharpe"]
    for n in sizes:
        c, d, sh = perf(rets[(n, "F0 無")])
        out.append(f"  {n:>2} 檔  {c:+6.1f}%  {d:6.1f}%  {sh:.2f}")
    out.append("\n(2) 大盤濾網：年化／最大回檔／Sharpe／在場月份比例")
    for n in (20, 30, 40):
        for fn in filt:
            c, d, sh = perf(rets[(n, fn)])
            out.append(f"  {n} 檔 {fn:<14} {c:+6.1f}%  {d:6.1f}%  {sh:.2f}  {statistics.mean(inmkt[(n, fn)]) * 100:.0f}%")
    text = "\n".join(out)
    print(text)
    open(os.path.join(HERE, "結果_研究305_選股濾網.txt"), "w", encoding="utf-8").write(text + "\n")


if __name__ == "__main__":
    main()
