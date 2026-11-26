"""研究 186：主策略（v3）全面健檢——使用者 2026-11-26「再仔細跑一下主策略，看有沒有可以優化的地方」

已研究過 100 多項（換參數、換指標、加濾網、分段、停損、波動目標、季節、海外分散…），大多比現行差或是雜訊；
研究 183 的 CSCV 也顯示「在均線格點裡挑最好」過擬合機率 64%。所以這裡不再盲掃，只做三件事：
A. 現況：資料到 2026-11-25 的 v3 績效、2024 起逐筆交易、這一波（2026）主策略的回檔
B. v3 完整規格（均線 ＋ 融資過熱濾網）的 CSCV 過擬合機率：進場 MA50/60/70 × 1.00/1.01/1.02、
   出場 MA70/80/90 × 0.97/0.975/0.98、過熱門檻 15/17.5/20%、z 1.5/2/無 ＝ 729 組；14 段、C(14,7)
C. 兩個沒測過的新點子（每個一小族參數，看全期／前段／後段／真實價／逐年勝負）：
   C1 安全墊槓桿：在場時指數離出場線不到 c%（容易被洗出場的區域）只持 lev_low 倍，安全墊夠了才 2 倍
      （研究 16 是「依時間」分段，研究 64i 是加碼端；主部位依距離調槓桿沒測過）
   C2 長多頭放寬出場：指數在 MA240 之上（長期多頭）時出場緩衝放寬到 b_up，否則用 b_dn
      （研究 82 是依波動調緩衝＝更差；研究 42 是年線乖離過熱；依長期趨勢分段的出場緩衝沒測過）
用法：python -X utf8 backtest/research_186_主策略全面健檢.py
"""
import importlib.util
import itertools
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("v3", os.path.join(HERE, "strategy_v3.py"))
V3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V3)
bt, DAYS, PX, N, WE = V3.bt, V3.DAYS, V3.PX, V3.N, V3.WE
DEV, Z = V3.DEV, V3.Z
M240 = bt.get_sma(240)


def run(start, end, real=False, ein=60, bin_=1.01, eout=80, bout=0.975, th=0.175, zth=2.0, reentry=0.125,
        lev_fn=None, bout_fn=None, curve=False, trades=None):
    """v3 引擎（同 strategy_v3.run，daily_heat 開啟）加上可調均線、槓桿函數、出場緩衝函數"""
    r1 = V3.R1R if real else bt.R1
    r2 = V3.R2R if real else bt.R2
    mi, mo = bt.get_sma(ein), bt.get_sma(eout)
    i0 = next(i for i, x in enumerate(DAYS) if x >= start)
    i1 = max(i for i, x in enumerate(DAYS) if x <= end)
    eq = peak = 1.0
    mdd, state, heat_out, cur, pend = 0.0, 0, False, 0.0, None
    out = []

    def hot(i):
        return DEV[i] is not None and (DEV[i] > th or (zth is not None and Z[i] > zth))

    def ret(i, L):
        if L <= 0:
            return bt.RC
        if L <= 1:
            return L * r1[i] + (1 - L) * bt.RC
        return (L - 1) * r2[i] + (2 - L) * r1[i]

    def bo(i):
        return bout_fn(i) if bout_fn else bout

    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + ret(i, cur)
        if pend is not None:
            eq *= 1 - bt.COST * abs(pend - cur)
            if trades is not None:
                trades.append((DAYS[i], cur, pend, PX[i]))
            cur, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        out.append(eq)
        if i >= 260 and not WE[i] and state == 1 and hot(i):
            state, heat_out = 0, True
            if cur != 0:
                pend = 0.0
            continue
        if WE[i] and i >= 260:
            h = hot(i)
            p = PX[i]
            above = p >= mo[i] * bo(i)
            if state == 0:
                if heat_out and not above:
                    heat_out = False
                cooled = DEV[i] is None or (DEV[i] < reentry and (zth is None or Z[i] <= zth))
                if (p > mi[i] * bin_ and not h) or (heat_out and cooled and above):
                    state, heat_out = 1, False
            elif h:
                state, heat_out = 0, True
            elif not above:
                state, heat_out = 0, False
            t = (lev_fn(i, mo[i] * bo(i)) if lev_fn else 2.0) if state == 1 else 0.0
            if t != cur:
                pend = t
    yrs = (i1 - i0) / bt.TD
    res = (eq ** (1 / yrs) - 1, mdd)
    return res + (out,) if curve else res


PER = [("2002-01-01", "2026-12-31"), ("2002-01-01", "2012-12-31"), ("2013-01-01", "2026-12-31")]
REAL = ("2015-09-01", "2026-12-31")


def fmt(**kw):
    rs = [run(a, b, **kw) for a, b in PER]
    rr = run(*REAL, real=True, **kw)
    return rs, rr, " | ".join(f"{c:5.1%}/{m:6.1%}" for c, m in rs) + f" | 真實 {rr[0]:5.1%}/{rr[1]:6.1%}"


def yearly(**kw):
    _, _, e = run("2002-01-01", "2026-12-31", curve=True, **kw)
    i0 = next(i for i, x in enumerate(DAYS) if x >= "2002-01-01")
    out, last = {}, 1.0
    for k, eqv in enumerate(e):
        y = DAYS[i0 + k][:4]
        out[y] = eqv
    ys = sorted(out)
    res, prev = {}, 1.0
    for y in ys:
        res[y] = out[y] / prev - 1
        prev = out[y]
    return res


def part_a(L):
    L.append("【A】現況（資料到 %s）" % DAYS[-1])
    _, _, s = fmt()
    L.append("v3 全期 2002– ｜ 前段 –2012 ｜ 後段 2013– ｜ 真實 2015-09–（年化/最大回檔）")
    L.append("  " + s)
    tr = []
    run("2002-01-01", "2026-12-31", curve=False, trades=tr)
    L.append("2024 起換倉（成交日、前→後槓桿、加權）：")
    for d, a, b, p in tr:
        if d >= "2024-01-01":
            L.append(f"  {d}  {a:.1f}x → {b:.1f}x  加權 {p:,.0f}")
    _, _, e = run("2002-01-01", "2026-12-31", curve=True)
    i0 = next(i for i, x in enumerate(DAYS) if x >= "2002-01-01")
    k26 = next(k for k in range(len(e)) if DAYS[i0 + k] >= "2026-01-01")
    pk = max(range(k26, len(e)), key=lambda k: e[k])
    ipk = max(range(i0 + k26, N), key=lambda i: PX[i])
    L.append(f"2026：策略淨值高點 {DAYS[i0 + pk]}，到 {DAYS[-1]} 回檔 {e[-1] / e[pk] - 1:+.1%}；"
             f"加權高點 {DAYS[ipk]} {PX[ipk]:,.0f}，到現在 {PX[-1] / PX[ipk] - 1:+.1%}；今年策略 {e[-1] / e[k26 - 1] - 1:+.1%}、加權 {PX[-1] / PX[i0 + k26 - 1] - 1:+.1%}")
    ys = yearly()
    L.append("逐年（v3）：" + "、".join(f"{y} {r:+.0%}" for y, r in ys.items()))


def part_b(L, S=14):
    L.append("\n【B】v3 完整規格 CSCV（729 組，2002–2026，夏普）")
    grid = list(itertools.product((50, 60, 70), (1.0, 1.01, 1.02), (70, 80, 90), (0.97, 0.975, 0.98), (0.15, 0.175, 0.20), (1.5, 2.0, None)))
    cur = (60, 1.01, 80, 0.975, 0.175, 2.0)
    lr = {}
    for g in grid:
        _, _, e = run("2002-01-01", "2026-12-31", ein=g[0], bin_=g[1], eout=g[2], bout=g[3], th=g[4], zth=g[5], curve=True)
        lr[g] = [math.log(e[k] / e[k - 1]) for k in range(1, len(e))]
    T = len(lr[cur])
    edges = [T * k // S for k in range(S + 1)]
    st = {g: [(edges[k + 1] - edges[k], sum(v[edges[k]:edges[k + 1]]), sum(x * x for x in v[edges[k]:edges[k + 1]])) for k in range(S)] for g, v in lr.items()}

    def sh(g, idx):
        n = sum(st[g][k][0] for k in idx)
        s = sum(st[g][k][1] for k in idx)
        q = sum(st[g][k][2] for k in idx)
        m = s / n
        return m / math.sqrt(max(q / n - m * m, 1e-12)) * math.sqrt(bt.TD)

    below, ranks, deg, curr = 0, [], [], []
    for ins in itertools.combinations(range(S), S // 2):
        oos = [k for k in range(S) if k not in ins]
        best = max(grid, key=lambda g: sh(g, ins))
        order = sorted(grid, key=lambda g: sh(g, oos))
        w = order.index(best) / (len(grid) - 1)
        ranks.append(w)
        below += w < 0.5
        deg.append((sh(best, ins), sh(best, oos)))
        curr.append(order.index(cur) / (len(grid) - 1))
    n = len(ranks)
    L.append(f"PBO {below / n:.1%}；樣本內第一名夏普 {sum(a for a, _ in deg) / n:.2f} → 樣本外 {sum(b for _, b in deg) / n:.2f}；"
             f"現行在樣本外的排名中位 {sorted(curr)[n // 2]:.0%}")
    allo = sorted(grid, key=lambda g: sh(g, range(S)))
    L.append(f"全期：現行第 {allo.index(cur) / (len(grid) - 1):.0%} 分位、夏普 {sh(cur, range(S)):.2f}；最好 {allo[-1]} {sh(allo[-1], range(S)):.2f}；"
             f"中位 {sh(allo[len(allo) // 2], range(S)):.2f}；10 分位 {sh(allo[len(allo) // 10], range(S)):.2f}")
    # 各維度的邊際效果（固定其他維度取平均）
    for d, name in enumerate(("進場 MA", "進場緩衝", "出場 MA", "出場緩衝", "過熱門檻", "z")):
        vals = sorted({g[d] for g in grid}, key=lambda v: (v is None, v))
        L.append(f"  {name}：" + "、".join(f"{v}→{sum(sh(g, range(S)) for g in grid if g[d] == v) / sum(1 for g in grid if g[d] == v):.3f}" for v in vals))


def part_c(L):
    L.append("\n【C】新點子（全期｜前段｜後段｜真實；逐年勝現行的年數）")
    base_rs, base_rr, s = fmt()
    yb = yearly()
    L.append(f"  現行                         {s}")

    def show(name, **kw):
        rs, rr, s = fmt(**kw)
        yv = yearly(**kw)
        win = sum(yv[y] > yb[y] + 1e-9 for y in yb)
        lose = sum(yv[y] < yb[y] - 1e-9 for y in yb)
        ok = all(a[0] >= b[0] for a, b in zip(rs, base_rs)) and rr[0] >= base_rr[0]
        L.append(f"  {name:<28} {s}  勝 {win}／輸 {lose} 年{'  ★四段都不輸' if ok else ''}")
        return yv

    L.append(" C1 安全墊槓桿（離出場線 < c 時只持 lev_low 倍）")
    for c in (0.03, 0.05, 0.08, 0.12):
        for lo in (1.0, 1.5):
            show(f"c {c:.0%}、lev_low {lo}x", lev_fn=lambda i, line, c=c, lo=lo: 2.0 if PX[i] >= line * (1 + c) else lo)
    L.append(" C2 長多頭（指數 > MA240）放寬出場緩衝")
    for bu, bd in ((0.96, 0.975), (0.95, 0.975), (0.965, 0.98), (0.96, 0.98), (0.975, 0.985), (0.95, 0.98)):
        show(f"MA240 上 ×{bu}、下 ×{bd}", bout_fn=lambda i, bu=bu, bd=bd: bu if (M240[i] and PX[i] > M240[i]) else bd)
    L.append(" C2 對照：不分多空頭，全部用同一個緩衝")
    for b in (0.95, 0.96, 0.965, 0.98, 0.985):
        show(f"全部 ×{b}", bout=b)


def main():
    L = ["研究 186：主策略（v3）全面健檢"]
    part_a(L)
    part_c(L)
    part_b(L)
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究186_主策略全面健檢.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
