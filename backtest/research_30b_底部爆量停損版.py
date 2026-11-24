"""研究 30b：底部爆量提早進場（修正版）——提早進場後改用「爆量後最低點」當停損，站上正式進場線才回到原出場規則

研究 30 的問題：提早進場時指數還在 MA80×0.975 之下，下一個週五就被原出場規則洗出場。
狀態機（每週五判斷、隔天收盤成交）：
- 空手：站上 MA60×1.01 → 正常持有；否則若出現爆量訊號 → 提早持有（記錄停損＝爆量日到今天的最低收盤 ×(1−s)）
- 提早持有：站上 MA60×1.01 → 轉正常持有；收盤跌破停損 → 出場；持有超過 T 週還沒站上進場線 → 出場
- 正常持有：跌破 MA80×0.975 → 出場
- 提早持有的槓桿：2x 或 1x
爆量訊號：近 L 日內有一天成交金額 ≥ k × 前 20 日均量、且當天距 250 日高點跌 ≥ d；本週五收盤 > 爆量後最低收盤 ×1.05（研究 30 的確認 C）
對照：同規則不看量
用法：python -X utf8 backtest/research_30b_底部爆量停損版.py
"""
import importlib.util
import itertools
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r30", os.path.join(HERE, "research_30_底部爆量.py"))
R30 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R30)
bt, R = R30.bt, R30.R
DAYS, PX, N, WE = bt.DAYS, bt.PX, len(bt.DAYS), bt.WEEK_END
M60, M80 = bt.get_sma(60), bt.get_sma(80)
PER = [("1998-01-01", "2026-12-31"), ("1998-01-01", "2012-12-31"), ("2013-01-01", "2026-12-31")]
REAL = ("2015-09-01", "2026-12-31")


def run(start, end, k=None, d=0.15, L=20, s=0.0, T=13, lev_early=2.0, use_vol=True, real=False, log=None):
    r1, r2 = (R.R1R, R.R2R) if real else (bt.R1, bt.R2)
    cd = R30.climax_days(k, d) if (use_vol and k is not None) else ([PX[i] / R30.HI250[i] - 1 <= -d for i in range(N)] if not use_vol else [False] * N)
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
            elif k is not None or not use_vol:
                js = [j for j in range(max(0, i - L), i + 1) if cd[j]]
                if js:
                    lo = min(PX[js[-1]:i + 1])
                    if PX[i] > lo * 1.05:
                        new, stop, weeks = 1, lo * (1 - s), 0
        elif state == 1:
            weeks += 1
            if PX[i] > M60[i] * 1.01:
                new = 2
            elif PX[i] < stop or weeks > T:
                new = 0
        else:
            if PX[i] < M80[i] * (1 - R30.BOUT):
                new = 0
        if log is not None and new != state:
            log.append((DAYS[i], {0: "出場", 1: "提早進", 2: "正常持有"}[new]))
        state = new
        t = {0: 0.0, 1: lev_early, 2: 2.0}[state]
        if t != lev:
            pend = t
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd


def ev(**kw):
    rs = [run(a, b, **kw) for a, b in PER]
    rr = run(*REAL, real=True, **kw)
    return rs, rr


def fmt(rs, rr):
    return " | ".join(f"{c * 100:5.1f}%/{m * 100:6.1f}%" for c, m in rs) + f" | 真實 {rr[0] * 100:5.1f}%/{rr[1] * 100:6.1f}%"


def main():
    L = [f"研究 30b：底部爆量提早進場＋停損（量：{R30.VSRC}；全期 | 前段 | 後段 | 真實；年化/最大回檔）"]
    base = ev()
    L.append(f"{'現行（出場 MA80x0.975）':36s} {fmt(*base)}")

    def ok(rs, rr):
        return (all(a[0] >= b[0] - 1e-9 for a, b in zip(rs, base[0])) and rs[0][1] > -0.5
                and rr[0] >= base[1][0] - 1e-9 and rr[1] >= base[1][1] - 0.03)

    for lev in (2.0, 1.0):
        res = []
        for k, d, Ln, s, T in itertools.product((1.5, 2.0, 2.5), (0.15, 0.20, 0.25), (10, 20), (0.0, 0.03), (8, 13, 26)):
            rs, rr = ev(k=k, d=d, L=Ln, s=s, T=T, lev_early=lev)
            res.append(((k, d, Ln, s, T), rs, rr, ok(rs, rr)))
        cs = sorted(x[1][0][0] for x in res)
        L.append(f"\n== 早進 {lev:.0f}x：{len(res)} 組，三段＋真實都勝現行 {sum(x[3] for x in res)} 組；全期年化中位 {cs[len(cs) // 2]:.1%}；"
                 f"回檔 > 50% {sum(x[1][0][1] < -0.5 for x in res)} 組 ==")
        for p, rs, rr, good in sorted(res, key=lambda x: -x[1][0][0])[:10]:
            L.append(f"  量≥{p[0]}x 跌≥{p[1]:.0%} {p[2]}日 停損-{p[3]:.0%} 最多{p[4]}週 {'★' if good else ' '} {fmt(rs, rr)}")
        # 各參數的勝率（看穩定度）
        for idx, nm in ((0, "量倍數"), (1, "跌幅"), (2, "回看天數"), (3, "停損緩衝"), (4, "最長週數")):
            vals = sorted({x[0][idx] for x in res})
            L.append(f"  {nm}：" + "、".join(f"{v}→{sum(x[3] for x in res if x[0][idx] == v)}/{sum(1 for x in res if x[0][idx] == v)}" for v in vals))
    L.append("\n== 對照：不看量（同停損規則，早進 2x）==")
    for d, Ln, s, T in itertools.product((0.15, 0.20, 0.25), (10, 20), (0.0,), (13,)):
        rs, rr = ev(k=None, d=d, L=Ln, s=s, T=T, use_vol=False)
        L.append(f"  跌≥{d:.0%} {Ln}日 {'★' if ok(rs, rr) else ' '} {fmt(rs, rr)}")
    log = []
    run("1998-01-01", "2026-12-31", k=2.0, d=0.15, L=20, s=0.0, T=13, log=log)
    L.append("\n== 代表組（量≥2x、跌≥15%、20 日、停損爆量後低點、最多 13 週）的提早進場紀錄 ==")
    for i, (dte, ev_) in enumerate(log):
        if ev_ == "提早進":
            nxt = log[i + 1] if i + 1 < len(log) else ("—", "")
            L.append(f"  {dte} 提早進 → {nxt[0]} {nxt[1]}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究30b_底部爆量停損版.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
