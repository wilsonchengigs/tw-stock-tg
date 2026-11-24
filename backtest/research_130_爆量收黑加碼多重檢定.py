"""研究 130：在場時爆量收黑加碼台指期（已納入日報，候選 1）的家族多重檢定——比照研究 129

研究 77 在 v3 上試了 k 1.4／1.5／1.6／1.8 × 加 0.5／1x × 抱 3／5／7／10 天共 32 組，採用的是 k1.5 加 1x 抱 10 天（43.8%）。
這裡檢定「從 32 組挑出來」之後還顯不顯著：
- 虛無假設：「爆量收黑」這個日子標記與之後幾天的報酬無關
- 做法：把每天的（成交金額倍數, 是否收黑）一起在 2015-10～ 的交易日上環狀平移 s 天（保留爆量的群聚與訊號數），
  只有「平移後的訊號日剛好在場」才加碼，與實際規則相同；每個平移重跑 32 組
- 家族 p：各組先和自己的平移分布比成單組 p，取家族最小 p，再和平移樣本的家族最小 p 比（研究 129 的最小 p 值法）
- 引擎沿用研究 77（00631L 真實還原價＋台指期真實價、夜盤開盤進、成本 3 點）
用法：python -X utf8 backtest/research_130_爆量收黑加碼多重檢定.py（R130_SHIFTS 控制平移次數，預設 200）
"""
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("r77", os.path.join(HERE, "research_77_v3爆量收黑加碼格點.py"))
r77 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r77)
DAYS, PX, VR, N = r77.DAYS, r77.PX, r77.VR, r77.N
COST_ETF, COST_FUT = r77.COST_ETF, r77.COST_FUT


def make_sim():
    E = r77.etf()
    fdates, fday, fnight, near = r77.r63d.load()
    fidx = {d: i for i, d in enumerate(fdates)}
    days = [i for i in range(N) if DAYS[i] in E and DAYS[i] in fidx and DAYS[i] >= "2015-10-01"]
    st = r77.load_v3()

    def sim(k, add, H, vr, dn):
        """vr[i]、dn[i]：第 i 天的成交金額倍數與是否收黑（可被平移）；回傳（年化, 最大回檔）"""
        eq = peak = 1.0
        mdd = 0.0
        pos = False
        fut = None
        prev_i = None
        for i in days:
            d = DAYS[i]
            if prev_i is not None:
                r = 0.0
                if pos:
                    r += E[d] / E[DAYS[prev_i]] - 1
                if fut is not None:
                    m = fut[1]
                    b = fday[d].get(m)
                    if b is None:
                        m = near[d]
                        b = fday[d].get(m)
                    pb = fday[DAYS[prev_i]].get(m) if fut[3] != "entry" else None
                    if b:
                        base_px = fut[0] if fut[3] == "entry" else (pb[3] if pb else b[3])
                        r += add * (b[3] / base_px - 1)
                        fut = (fut[0], m, fut[2], "hold")
                eq *= 1 + r
            want = st[i - 1] if i > 0 else False
            if want != pos:
                eq *= 1 - COST_ETF * 2
                pos = want
            if fut is not None and (i >= fut[2] or not pos):
                eq *= 1 - add * COST_FUT / fday[d].get(fut[1], (0, 0, 0, 40000))[3]
                fut = None
            if k is not None and fut is None and pos and st[i] and vr.get(i) is not None and vr[i] >= k and dn[i]:
                j = fidx.get(d)
                if j is not None and j + 1 < len(fdates):
                    d1 = fdates[j + 1]
                    m = near[d1]
                    nb = fnight[d1].get(m)
                    entry = nb[0] if nb else fday[d1][m][0]
                    fut = (entry, m, i + H, "entry")
            peak = max(peak, eq)
            mdd = min(mdd, eq / peak - 1)
            prev_i = i
        yrs = (len(days) - 1) / 245
        return eq ** (1 / yrs) - 1, mdd

    return sim, days


def main():
    sim, days = make_sim()
    n = len(days)
    vr0 = {i: VR[i] for i in days}
    dn0 = {i: PX[i] < PX[i - 1] for i in days}
    grid = [(k, a, h) for k in (1.4, 1.5, 1.6, 1.8) for a in (0.5, 1.0) for h in (3, 5, 7, 10)]

    def family(s):
        vr = {days[p]: vr0[days[(p - s) % n]] for p in range(n)}
        dn = {days[p]: dn0[days[(p - s) % n]] for p in range(n)}
        return [sim(k, a, h, vr, dn) for k, a, h in grid]

    base = sim(None, 0, 0, vr0, dn0)
    real = family(0)
    K = int(os.environ.get("R130_SHIFTS", "200"))
    gap = 60
    shifts = [gap + round(k * (n - 2 * gap) / (K - 1)) for k in range(K)]
    allfam = []
    for k, s in enumerate(shifts):
        allfam.append([x[0] for x in family(s)])
        if (k + 1) % 20 == 0:
            print(f"  平移 {k + 1}/{K}", flush=True)
    cols = list(zip(*allfam))

    def pval(v, col, skip=None):
        others = [c for i, c in enumerate(col) if i != skip]
        return (sum(c >= v for c in others) + 1) / (len(others) + 1)

    single = [pval(x[0], cols[g]) for g, x in enumerate(real)]
    L = [f"研究 130：在場爆量收黑加碼家族多重檢定（v3、00631L＋台指期真實價、2015-10～；不加碼 {base[0]:.1%}／{base[1]:.1%}）",
         f"家族 {len(grid)} 組（研究 77 格點）；環狀平移 {K} 次（{shifts[0]}～{shifts[-1]} 交易日，共 {n} 天）", "",
         "實際結果（單組 p＝平移後該組年化 ≥ 實際的比例）："]
    for g in sorted(range(len(grid)), key=lambda g: -real[g][0]):
        k, a, h = grid[g]
        mark = "  ← 日報採用" if (k, a, h) == (1.5, 1.0, 10) else ""
        L.append(f"  k{k} 加{a}x 抱{h:2d}天：{real[g][0]:.1%}／{real[g][1]:.1%}｜平移中位 {sorted(cols[g])[K // 2]:.1%}｜單組 p {single[g]:.3f}{mark}")
    real_minp = min(single)
    null_minp = [min(pval(allfam[k][g], cols[g], skip=k) for g in range(len(grid))) for k in range(K)]
    pm = (sum(v <= real_minp for v in null_minp) + 1) / (K + 1)
    best = max(real, key=lambda x: x[0])[0]
    mx = sorted(max(f) for f in allfam)
    pc = (sum(v >= best for v in mx) + 1) / (K + 1)
    g0 = grid.index((1.5, 1.0, 10))
    L += ["", "家族檢定：",
          f"  最小 p 值：實際家族最小單組 p {real_minp:.3f}；平移樣本家族最小 p 中位 {sorted(null_minp)[K // 2]:.3f}｜家族 p {pm:.3f}",
          f"  家族最好年化：實際 {best:.1%}；平移後 中位 {mx[K // 2]:.1%}、90 分位 {mx[int(K * 0.9)]:.1%}｜家族 p {pc:.3f}（偏嚴，參考）",
          f"  日報採用組（k1.5 加1x 抱10天）單組 p {single[g0]:.3f}"]
    txt = "\n".join(L) + "\n"
    print(txt)
    open(os.path.join(HERE, "結果_研究130_爆量收黑加碼多重檢定.txt"), "w", encoding="utf-8").write(txt)


if __name__ == "__main__":
    main()
