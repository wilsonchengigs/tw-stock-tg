"""研究 132：台指選 P/C 未平倉偏高提早進場（日報觀察，研究 32、35）在 v3 現行策略上的家族多重檢定——比照研究 129～131

研究 32／35 用的是舊版基準（沒有融資過熱濾網）；這裡改在 v3 引擎（strategy_v3.run 的規則）上加提早進場：
- 空手且不過熱時，近 L 日內 P/C 未平倉比曾 ≥ 過去 250 日 q 分位，且本週五收盤 > 近 L 日最低收盤 ×(1+c) → 提早持有 lev_early，
  停損＝近 L 日最低收盤；站上 MA60×1.01（且不過熱）轉正常持有；跌破停損、超過 T＝13 週或過熱 → 出場
- 其餘（出場線、融資過熱每天檢查、過熱後回補）同 v3
- 家族：q 0.90／0.95／0.99 × L 5／10／20 × c 0／3／5% × 早進 1x／2x 共 54 組（日報用 q 0.95、L 10、c 3%）
- 虛無假設：P/C 百分位序列與之後行情無關；P/C 百分位序列在有值區間環狀平移（避開 ±250 日）
- 家族 p：最小 p 值法；全期 2002–2026、後段 2013–2026、真實價 2015-09～ 分段
用法：python -X utf8 backtest/research_132_PC提早進場多重檢定.py（R132_SHIFTS 控制平移次數，預設 200）
"""
import csv
import importlib.util
import itertools
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


V = load("v3", "strategy_v3.py")
R31 = load("r31", "research_31_情緒指標事件研究.py")
bt, DAYS, PX, N, WE, M60, M80 = V.bt, V.DAYS, V.PX, V.N, V.WE, V.M60, V.M80
rows = list(csv.DictReader(open(os.path.join(HERE, "pcratio_daily.csv"), encoding="utf-8")))
PC = R31.align_tw({r["date"]: float(r["oi_ratio"]) for r in rows if r["oi_ratio"]})
PR0 = [R31.pct_rank(PC, i) if i >= 150 else None for i in range(N)]
GRID = list(itertools.product((0.90, 0.95, 0.99), (5, 10, 20), (0.0, 0.03, 0.05), (1.0, 2.0)))
SEGS = (("全期", "2002-01-01", "2026-12-31", False), ("後段", "2013-01-01", "2026-12-31", False), ("真實", "2015-09-01", "2026-12-31", True))
T = 13


def run(start, end, pr, q=None, L=10, c=0.03, lev_early=1.0, real=False, lev=2.0, th=0.175, zth=2.0, reentry=0.125):
    """v3 規則＋P/C 提早進場；q=None 時等於 v3（回傳年化）"""
    r1 = V.R1R if real else bt.R1
    r2 = V.R2R if real else bt.R2
    flag = [q is not None and pr[i] is not None and pr[i] >= q for i in range(N)]
    i0 = next(i for i, x in enumerate(DAYS) if x >= start)
    i1 = max(i for i, x in enumerate(DAYS) if x <= end)
    eq = 1.0
    state, heat_out, cur, pend, stop, weeks = 0, False, 0.0, None, 0.0, 0   # state：0 空手、1 正常持有、2 提早持有

    def ret(i, Lv):
        if Lv <= 0:
            return bt.RC
        if Lv <= 1:
            return Lv * r1[i] + (1 - Lv) * bt.RC
        return (Lv - 1) * r2[i] + (2 - Lv) * r1[i]

    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + ret(i, cur)
        if pend is not None:
            eq *= 1 - bt.COST * abs(pend - cur)
            cur, pend = pend, None
        if i >= 260 and not WE[i] and state in (1, 2) and V.hot_at(i, th, zth):
            state, heat_out = 0, True
            if cur != 0.0:
                pend = 0.0
            continue
        if not (WE[i] and i >= 260):
            continue
        hot = V.hot_at(i, th, zth)
        p = PX[i]
        above = p >= M80[i] * 0.975
        if state == 0:
            if heat_out and not above:
                heat_out = False
            cooled = V.DEV[i] is None or (V.DEV[i] < reentry and (zth is None or V.Z[i] <= zth))
            if (p > M60[i] * 1.01 and not hot) or (heat_out and cooled and above):
                state, heat_out = 1, False
            elif not hot and q is not None and any(flag[j] for j in range(i - L, i + 1)):
                lo = min(PX[i - L:i + 1])
                if p > lo * (1 + c):
                    state, stop, weeks = 2, lo, 0
        elif state == 2:
            weeks += 1
            if hot:
                state, heat_out = 0, True
            elif p > M60[i] * 1.01:
                state = 1
            elif p < stop or weeks > T:
                state = 0
        elif hot:
            state, heat_out = 0, True
        elif not above:
            state, heat_out = 0, False
        t = {0: 0.0, 1: lev, 2: lev_early}[state]
        if t != cur:
            pend = t
    return eq ** (1 / ((i1 - i0) / bt.TD)) - 1


def family(pr):
    return [[run(a, b, pr, q=q, L=L, c=c, lev_early=le, real=real) for _, a, b, real in SEGS] for q, L, c, le in GRID]


def main():
    base = [run(a, b, PR0, real=real) for _, a, b, real in SEGS]
    chk = [V.run(a, b, real=real)[0] for _, a, b, real in SEGS]
    valid = [i for i in range(N) if PR0[i] is not None]
    n = len(valid)
    real_res = family(PR0)
    K = int(os.environ.get("R132_SHIFTS", "200"))
    gap = 250
    shifts = [gap + round(k * (n - 2 * gap) / (K - 1)) for k in range(K)]
    allfam = []
    for k, s in enumerate(shifts):
        pr = [None] * N
        for p in range(n):
            pr[valid[p]] = PR0[valid[(p - s) % n]]
        allfam.append(family(pr))
        if (k + 1) % 10 == 0:
            print(f"  平移 {k + 1}/{K}", flush=True)

    def pval(v, col, skip=None):
        others = [x for i, x in enumerate(col) if i != skip]
        return (sum(x >= v for x in others) + 1) / (len(others) + 1)

    L_ = [f"研究 132：P/C 提早進場 × v3 家族多重檢定（{len(GRID)} 組；P/C 百分位環狀平移 {K} 次，{shifts[0]}～{shifts[-1]} 日，有值 {n} 天）",
          "v3 不提早進場：" + "、".join(f"{nm} {x:.1%}" for (nm, *_), x in zip(SEGS, base)) + "（strategy_v3 對照：" + "、".join(f"{x:.1%}" for x in chk) + "）", "",
          "實際結果（各段年化（平移中位，單組 p）；★＝日報用的 q0.95 L10 c3%）："]
    singles = []
    for g, (q, L, c, le) in enumerate(GRID):
        ps, meds = [], []
        for si in range(len(SEGS)):
            col = [f[g][si] for f in allfam]
            ps.append(pval(real_res[g][si], col))
            meds.append(sorted(col)[K // 2])
        singles.append(ps)
        mark = "★" if (q, L, c) == (0.95, 10, 0.03) else " "
        beat = sum(real_res[g][si] > base[si] for si in range(len(SEGS)))
        L_.append(f" {mark} q{q} L{L:2d} c{c:.0%} 早進{le:.0f}x：" + "｜".join(
            f"{nm} {real_res[g][si]:.1%}（{meds[si]:.1%}，p {ps[si]:.3f}）" for si, (nm, *_) in enumerate(SEGS)) + f"｜勝 v3 {beat}/3 段")
    L_ += ["", "家族檢定（最小 p 值法）："]
    for si, (nm, *_) in enumerate(SEGS):
        cols = [[f[g][si] for f in allfam] for g in range(len(GRID))]
        real_minp = min(singles[g][si] for g in range(len(GRID)))
        null_minp = [min(pval(allfam[k][g][si], cols[g], skip=k) for g in range(len(GRID))) for k in range(K)]
        pm = (sum(v <= real_minp for v in null_minp) + 1) / (K + 1)
        L_.append(f"  {nm}：家族最小單組 p {real_minp:.3f}；平移樣本家族最小 p 中位 {sorted(null_minp)[K // 2]:.3f}｜家族 p {pm:.3f}")
    allbeat = sum(all(real_res[g][si] > base[si] for si in range(len(SEGS))) for g in range(len(GRID)))
    L_.append(f"  三段都勝 v3：{allbeat}/{len(GRID)} 組")
    txt = "\n".join(L_) + "\n"
    print(txt)
    open(os.path.join(HERE, "結果_研究132_PC提早進場多重檢定.txt"), "w", encoding="utf-8").write(txt)


if __name__ == "__main__":
    main()
