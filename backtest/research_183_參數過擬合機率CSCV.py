"""研究 183：研究 17 延伸——均線參數過擬合機率（CSCV／PBO）與現行參數的分段排名

研究 17 用滾動最佳化（每年重挑）發現多數設定輸給固定現行，但沒有直接回答「現行參數是不是挑出來的運氣」。
這裡用 Bailey 等人的 CSCV（Combinatorially Symmetric Cross-Validation）：
- 1998–2026 切成 14 段（每段約 2 年），任取 7 段當樣本內、另外 7 段當樣本外，共 C(14,7)=3,432 種切法
- 每種切法：樣本內夏普最高的那組參數，在樣本外的排名（0＝最差、1＝最好）
- PBO（過擬合機率）＝ 樣本內第一名在樣本外掉到中位數以下的比例；< 0.2 算穩、> 0.5 代表挑參數跟丟銅板差不多
- 另算：樣本內最好 vs 樣本外的夏普衰退；現行參數（MA60×1.01 進／MA80×0.975 出）在 14 段各自的排名百分位
格點：研究 17 的 315 組 ＋ 出場 ×0.975（現行）＝ 420 組；只看均線主策略（不含融資過熱濾網與加碼），2x 全押、週五訊號隔天收盤成交
用法：python -X utf8 backtest/research_183_參數過擬合機率CSCV.py
"""
import itertools
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402

PX, DAYS, WE = bt.PX, bt.DAYS, bt.WEEK_END
N = len(PX)
GRID = [(a, b, c, d) for a, b, c, d in itertools.product((40, 50, 60, 70, 80, 100), (1.0, 1.01, 1.02),
                                                         (60, 70, 80, 90, 100, 120, 150), (0.97, 0.975, 0.98, 0.99)) if c >= a]
CUR = (60, 1.01, 80, 0.975)


def daily_rets(p):
    ein, bi, eo, bo = p
    mi, mo = bt.get_sma(ein), bt.get_sma(eo)
    st, sig = False, []
    for i in range(N):
        if WE[i] and i >= 260:
            st = (not PX[i] < mo[i] * bo) if st else (PX[i] > mi[i] * bi)
        sig.append(st)
    out, pos, pend = [0.0], False, None
    for i in range(1, N):
        r = bt.R2[i] if pos else bt.RC
        if pend is not None:
            r = (1 + r) * (1 - bt.COST * 2) - 1
            pos, pend = pend, None
        if WE[i] and sig[i] != pos:
            pend = sig[i]
        out.append(math.log1p(r))
    return out


def main():
    start = 260
    S = 14
    edges = [start + (N - start) * k // S for k in range(S + 1)]
    blocks = [(edges[k], edges[k + 1]) for k in range(S)]
    R = {p: daily_rets(p) for p in GRID}
    # 每段的 n、sum、sumsq（日對數報酬），組合時直接相加
    st = {p: [(b - a, sum(R[p][a:b]), sum(x * x for x in R[p][a:b])) for a, b in blocks] for p in GRID}

    def sharpe(p, idx):
        n = sum(st[p][k][0] for k in idx)
        s = sum(st[p][k][1] for k in idx)
        q = sum(st[p][k][2] for k in idx)
        m = s / n
        v = max(q / n - m * m, 1e-12)
        return m / math.sqrt(v) * math.sqrt(bt.TD)

    L = [f"研究 183：CSCV 過擬合機率（{len(GRID)} 組均線參數、{S} 段、C({S},{S // 2})={math.comb(S, S // 2)} 種切法；夏普為目標）"]
    L.append("各段：" + "；".join(f"{DAYS[a][:7]}～{DAYS[b - 1][:7]}" for a, b in blocks))
    below, ranks, deg, cur_ranks_oos = 0, [], [], []
    for ins in itertools.combinations(range(S), S // 2):
        oos = [k for k in range(S) if k not in ins]
        si = {p: sharpe(p, ins) for p in GRID}
        best = max(GRID, key=si.get)
        so = {p: sharpe(p, oos) for p in GRID}
        order = sorted(GRID, key=so.get)
        w = order.index(best) / (len(GRID) - 1)
        ranks.append(w)
        if w < 0.5:
            below += 1
        deg.append((si[best], so[best]))
        cur_ranks_oos.append(order.index(CUR) / (len(GRID) - 1))
    T = len(ranks)
    L.append(f"\nPBO（樣本內第一名在樣本外掉到中位數以下）＝ {below / T:.1%}")
    qs = sorted(ranks)
    L.append(f"樣本內第一名的樣本外排名百分位：10 分位 {qs[T // 10]:.0%}、中位 {qs[T // 2]:.0%}、90 分位 {qs[T * 9 // 10]:.0%}")
    mi = sum(a for a, _ in deg) / T
    mo = sum(b for _, b in deg) / T
    L.append(f"夏普：樣本內第一名平均 {mi:.2f} → 樣本外 {mo:.2f}（衰退 {1 - mo / mi:.0%}）")
    cq = sorted(cur_ranks_oos)
    L.append(f"現行參數在各種樣本外切法的排名百分位：中位 {cq[T // 2]:.0%}、10 分位 {cq[T // 10]:.0%}")

    L.append("\n現行參數在每一段的排名（百分位，100%＝該段最好）與該段夏普：")
    allp = sorted(GRID, key=lambda p: sharpe(p, range(S)))
    for k, (a, b) in enumerate(blocks):
        order = sorted(GRID, key=lambda p: sharpe(p, [k]))
        L.append(f"  {DAYS[a][:7]}～{DAYS[b - 1][:7]}：第 {order.index(CUR) / (len(GRID) - 1):4.0%} 分位、夏普 {sharpe(CUR, [k]):+.2f}"
                 f"（該段最好 {sharpe(order[-1], [k]):+.2f}、中位 {sharpe(order[len(order) // 2], [k]):+.2f}）")
    L.append(f"全期：現行第 {allp.index(CUR) / (len(GRID) - 1):.0%} 分位、夏普 {sharpe(CUR, range(S)):.2f}；全期最好 {allp[-1]} 夏普 {sharpe(allp[-1], range(S)):.2f}")

    # 鄰近參數高原：現行周圍（各維度相鄰一格）的夏普分布
    def neigh(p):
        A, B, C, D = (40, 50, 60, 70, 80, 100), (1.0, 1.01, 1.02), (60, 70, 80, 90, 100, 120, 150), (0.97, 0.975, 0.98, 0.99)
        dims = [A, B, C, D]
        out = []
        for d in range(4):
            i = dims[d].index(p[d])
            for j in (i - 1, i + 1):
                if 0 <= j < len(dims[d]):
                    q = list(p)
                    q[d] = dims[d][j]
                    if tuple(q) in R:
                        out.append(tuple(q))
        return out
    nb = neigh(CUR)
    vals = sorted(sharpe(q, range(S)) for q in nb)
    L.append(f"鄰近 {len(nb)} 組全期夏普：{min(vals):.2f}～{max(vals):.2f}（中位 {vals[len(vals) // 2]:.2f}），現行 {sharpe(CUR, range(S)):.2f}")

    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究183_參數過擬合機率CSCV.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
