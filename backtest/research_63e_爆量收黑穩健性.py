"""研究 63e：爆量收黑買進的穩健性（加權指數近似；隔天開盤進、抱 5 天、持有中訊號略過、成本 3 點）

1. 參數熱圖：倍數 k 1.2～2.2 × 均量回看 10／20／60 天 → 每筆平均報酬與隨機進場 p
2. 群聚校正：事件會在股災中扎堆。把「訊號日之間相隔 ≤10 個交易日」視為同一段，
   以「段」為單位做 sign-flip 檢定（每段的超額報酬隨機正負翻轉 5000 次），比逐筆 p 保守
3. 加停損：停損 2／3／5％（以進場價、盤中最低觸及即出，跳空以開盤價）→ 每筆平均、勝率、最差
用法：python -X utf8 backtest/research_63e_爆量收黑穩健性.py
"""
import importlib.util
import os
import random
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("r63b", os.path.join(HERE, "research_63b_爆量收黑買進.py"))
r63b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r63b)
r61 = r63b.r61
O, H_, LO, C, N, DAYS = r61.O, r61.H, r61.LO, r61.C, r61.N, r61.DAYS
AMT = r61.VOL["成交金額"]
START = r63b.START
COST = 3.0


def vratio(look):
    out = [None] * N
    for i in range(look + 1, N):
        xs = [AMT[k] for k in range(i - look, i) if AMT[k]]
        if AMT[i] and len(xs) >= look * 0.8:
            out[i] = AMT[i] / (sum(xs) / len(xs))
    return out


def sigs(vr, k):
    return [i for i in range(max(START, 61), N - 1) if vr[i] is not None and vr[i] >= k and C[i] < C[i - 1]]


def trade_stop(i, H, stop):
    e = i + 1
    px = O[e]
    lim = px * (1 - stop) if stop else None
    x = min(i + H, N - 1)
    for j in range(e, x + 1):
        if lim:
            if j > e and O[j] <= lim:
                return O[j] / px - 1 - COST / px, j
            if LO[j] <= lim:
                return -stop - COST / px, j
    return C[x] / px - 1 - COST / px, x


def run(sg, H=5, stop=None):
    out, busy = [], -1
    for i in sg:
        if i + 1 <= busy or i + 1 >= N:
            continue
        r, x = trade_stop(i, H, stop)
        out.append((i, r))
        busy = x
    return out


def main():
    rng = random.Random(635)
    L = ["研究 63e：爆量收黑買進穩健性（^TWII 近似；隔天開盤進、抱 5 天；成本 3 點）"]
    # 無條件基準：每天隔天開盤進抱 5 天
    base = [trade_stop(i, 5, None)[0] for i in range(max(START, 61), N - 6)]
    bm = statistics.mean(base)
    L.append(f"基準（任何一天隔天開盤進抱 5 天）每筆 {bm:+.2%}")

    L.append("\n== 1. 參數熱圖：每筆平均報酬（筆數）==")
    ks = (1.2, 1.3, 1.4, 1.5, 1.6, 1.8, 2.0, 2.2)
    L.append("回看  " + "".join(f"  k={k:<4}        " for k in ks))
    for look in (10, 20, 60):
        vr = vratio(look)
        cells = []
        for k in ks:
            t = run(sigs(vr, k))
            cells.append(f"{statistics.mean(r for _i, r in t):+.2%}({len(t):3d})    " if len(t) >= 8 else "   —            ")
        L.append(f"{look:3d}日 " + "".join(cells))

    L.append("\n== 2. 群聚校正（回看 20 日）：以「段」為單位 sign-flip 檢定 ==")
    vr20 = vratio(20)
    for k in (1.3, 1.5, 1.8):
        t = run(sigs(vr20, k))
        eps = []
        last = -99
        for i, r in t:
            if i - last > 10:
                eps.append([])
            eps[-1].append(r - bm)
            last = i
        seg = [statistics.mean(e) for e in eps]
        obs = statistics.mean(seg)
        sims = [statistics.mean(s * rng.choice((1, -1)) for s in seg) for _ in range(5000)]
        p = (sum(x >= obs for x in sims) + 1) / 5001
        L.append(f"  k={k}：{len(t)} 筆 → {len(eps)} 段；每段平均超額 {obs:+.2%}；段勝率 {sum(s > 0 for s in seg) / len(seg):.0%}；單尾 p＝{p:.4f}")

    L.append("\n== 3. 加停損（回看 20 日、k=1.5、抱 5 天）==")
    sg = sigs(vr20, 1.5)
    for stop in (None, 0.02, 0.03, 0.05):
        t = [r for _i, r in run(sg, 5, stop)]
        L.append(f"  停損 {'無' if stop is None else f'{stop:.0%}':>3s}：{len(t)} 筆 勝率 {sum(r > 0 for r in t) / len(t):.0%} 每筆 {statistics.mean(t):+.2%} 最差 {min(t):+.1%}")
    L.append("\n== 3b. 加停損（k=1.5、抱 10 天）==")
    for stop in (None, 0.03, 0.05):
        t = [r for _i, r in run(sg, 10, stop)]
        L.append(f"  停損 {'無' if stop is None else f'{stop:.0%}':>3s}：{len(t)} 筆 勝率 {sum(r > 0 for r in t) / len(t):.0%} 每筆 {statistics.mean(t):+.2%} 最差 {min(t):+.1%}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究63e_爆量收黑穩健性.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
