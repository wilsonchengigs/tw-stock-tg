"""研究 32：台指選擇權 P/C 未平倉比偏高 → 提早進場（研究 31 的追蹤驗證）

規則（同研究 30b 的狀態機，只把爆量換成 P/C）：
- 空手時，近 L 日內 P/C 未平倉比 ≥ 過去 250 日 q 分位，且本週五收盤 > 近 L 日最低收盤 ×(1+c) → 提早持有（lev_early），
  停損＝近 L 日最低收盤；站上 MA60×1.01 轉正常持有；跌破停損或超過 T 週 → 出場
- 正常持有：跌破 MA80×0.975 出場
資料：期交所 P/C 2001-12～，所以三段改 2002–2026／2002–2012／2013–2026；現行同期也重算
樣本外：參數只用 2002–2012 挑（前段最佳），看 2013–2026 表現；並列出所有提早進場事件
用法：python -X utf8 backtest/research_32_PC比提早進場.py
"""
import csv
import importlib.util
import itertools
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402

spec = importlib.util.spec_from_file_location("r31", os.path.join(HERE, "research_31_情緒指標事件研究.py"))
R31 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R31)
spec = importlib.util.spec_from_file_location("r30", os.path.join(HERE, "research_30_底部爆量.py"))
R30 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R30)
R = R30.R
DAYS, PX, N, WE = bt.DAYS, bt.PX, len(bt.DAYS), bt.WEEK_END
M60, M80 = bt.get_sma(60), bt.get_sma(80)
PER = [("2002-01-01", "2026-12-31"), ("2002-01-01", "2012-12-31"), ("2013-01-01", "2026-12-31")]
REAL = ("2015-09-01", "2026-12-31")
rows = list(csv.DictReader(open(os.path.join(HERE, "pcratio_daily.csv"), encoding="utf-8")))
PC = R31.align_tw({r["date"]: float(r["oi_ratio"]) for r in rows if r["oi_ratio"]})
PR = [R31.pct_rank(PC, i) if i >= 150 else None for i in range(N)]


def run(start, end, q=None, L=10, c=0.03, T=13, lev_early=2.0, real=False, log=None):
    r1, r2 = (R.R1R, R.R2R) if real else (bt.R1, bt.R2)
    flag = [q is not None and PR[i] is not None and PR[i] >= q for i in range(N)]
    i0 = next(i for i, x in enumerate(DAYS) if x >= start)
    i1 = max(i for i, x in enumerate(DAYS) if x <= end)
    eq = peak = 1.0
    mdd, state, lev, pend, stop, weeks = 0.0, 0, 0.0, None, 0.0, 0
    for i in range(i0, i1 + 1):
        if i > i0:
            w2, w1 = (lev - 1, 2 - lev) if lev > 1 else (0.0, lev)
            eq *= 1 + (w2 * r2[i] + w1 * r1[i] + (1 - w2 - w1) * bt.RC)
        if pend is not None:
            eq *= 1 - bt.COST * abs(pend - lev)
            lev, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if not WE[i] or i < 260:
            continue
        new = state
        if state == 0:
            if PX[i] > M60[i] * 1.01:
                new = 2
            elif any(flag[j] for j in range(i - L, i + 1)):
                lo = min(PX[i - L:i + 1])
                if PX[i] > lo * (1 + c):
                    new, stop, weeks = 1, lo, 0
        elif state == 1:
            weeks += 1
            if PX[i] > M60[i] * 1.01:
                new = 2
            elif PX[i] < stop or weeks > T:
                new = 0
        elif PX[i] < M80[i] * 0.975:
            new = 0
        if log is not None and new != state:
            log.append((DAYS[i], state, new, PX[i]))
        state = new
        t = {0: 0.0, 1: lev_early, 2: 2.0}[state]
        if t != lev:
            pend = t
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd


def ev(**kw):
    return [run(a, b, **kw) for a, b in PER], run(*REAL, real=True, **kw)


def fmt(rs, rr):
    return " | ".join(f"{c * 100:5.1f}%/{m * 100:6.1f}%" for c, m in rs) + f" | 真實 {rr[0] * 100:5.1f}%/{rr[1] * 100:6.1f}%"


def main():
    L_ = ["研究 32：台指選 P/C 未平倉偏高提早進場（全期 2002- | 前段 -2012 | 後段 2013- | 真實；年化/最大回檔）"]
    base = ev()
    L_.append(f"{'現行（同期）':40s} {fmt(*base)}")

    def ok(rs, rr):
        return (all(a[0] >= b[0] - 1e-9 for a, b in zip(rs, base[0])) and rs[0][1] > -0.5
                and rr[0] >= base[1][0] - 1e-9 and rr[1] >= base[1][1] - 0.03)

    for lev in (2.0, 1.0):
        res = []
        for q, Ln, c, T in itertools.product((0.90, 0.95, 0.99), (5, 10, 20), (0.0, 0.03, 0.05), (8, 13, 26)):
            rs, rr = ev(q=q, L=Ln, c=c, T=T, lev_early=lev)
            res.append(((q, Ln, c, T), rs, rr, ok(rs, rr)))
        cs = sorted(x[1][0][0] for x in res)
        L_.append(f"\n== 早進 {lev:.0f}x：{len(res)} 組，三段＋真實都勝現行 {sum(x[3] for x in res)} 組；全期中位 {cs[len(cs) // 2]:.1%}；"
                  f"回檔 > 50% {sum(x[1][0][1] < -0.5 for x in res)} 組 ==")
        for idx, nm in ((0, "分位"), (1, "回看天數"), (2, "反彈確認"), (3, "最長週數")):
            vals = sorted({x[0][idx] for x in res})
            L_.append(f"  {nm}：" + "、".join(f"{v}→{sum(x[3] for x in res if x[0][idx] == v)}/{sum(1 for x in res if x[0][idx] == v)}" for v in vals))
        for p, rs, rr, good in sorted(res, key=lambda x: -x[1][0][0])[:8]:
            L_.append(f"  P/C≥{p[0]:.0%}分位 {p[1]}日 反彈{p[2]:.0%} 最多{p[3]}週 {'★' if good else ' '} {fmt(rs, rr)}")
        # 樣本外：只用前段挑最佳
        best = max(res, key=lambda x: x[1][1][0])
        L_.append(f"  樣本外：前段最佳 {best[0]} → 前段 {best[1][1][0]:.1%}（現行 {base[0][1][0]:.1%}）、後段 {best[1][2][0]:.1%}（現行 {base[0][2][0]:.1%}）、真實 {best[2][0]:.1%}（現行 {base[1][0]:.1%}）")
    log = []
    run("2002-01-01", "2026-12-31", q=0.95, L=10, c=0.03, T=13, log=log)
    L_.append("\n== 代表組（≥95 分位、10 日、反彈 3%、最多 13 週、2x）的提早進場事件 ==")
    for k, (d, s0, s1, px) in enumerate(log):
        if s1 == 1:
            nxt = log[k + 1] if k + 1 < len(log) else None
            res = f"→ {nxt[0]} {'轉正常持有' if nxt[2] == 2 else '停損/逾時出場'}（指數 {px:,.0f} → {nxt[3]:,.0f}，{nxt[3] / px - 1:+.1%}）" if nxt else "→ 持有中"
            L_.append(f"  {d} 提早進 {res}")
    out = "\n".join(L_) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究32_PC比提早進場.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
