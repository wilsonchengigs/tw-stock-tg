"""研究 189：融資過熱出場的來回成本（2026 年過熱出場 3 次：5/21→5/25、6/09→6/15、6/25→8/03）

問題：融資過熱濾網（研究 38／85／90／131）整體有效（研究 186 B：z 濾網是唯一有明顯貢獻的維度），
但過熱出場後幾天就回補的「來回」看起來像白白賣低買高。逐筆看：
- 每次過熱出場：出場成交價、回補（或改由價格規則進場）成交價、間隔天數、這段期間加權漲跌（正＝錯過、負＝躲過）
- 依間隔分組（≤10 天／11～40 天／>40 天）各自的合計效果
- 變形（家族，不挑單一最好）：過熱要連續 1（現行）／2／3 天才出場；出場後 5／10 天內不因「回補條件」回補（只有價格進場規則能進）
看 全期｜前段｜後段｜真實 與逐年勝負
用法：python -X utf8 backtest/research_189_融資過熱出場來回成本.py
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("v3", os.path.join(HERE, "strategy_v3.py"))
V3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V3)
bt, DAYS, PX, N, WE = V3.bt, V3.DAYS, V3.PX, V3.N, V3.WE
DEV, Z, M60, M80 = V3.DEV, V3.Z, V3.M60, V3.M80


def run(start, end, real=False, persist=1, lock=0, log=None, curve=False):
    """v3（每日過熱檢查）＋ persist：過熱要連續幾天才出場；lock：過熱出場後幾個交易日內不走『回補』（價格進場仍可）"""
    r1 = V3.R1R if real else bt.R1
    r2 = V3.R2R if real else bt.R2
    i0 = next(i for i, x in enumerate(DAYS) if x >= start)
    i1 = max(i for i, x in enumerate(DAYS) if x <= end)
    eq = peak = 1.0
    mdd, state, heat_out, cur, pend, hot_run, out_i = 0.0, 0, False, 0.0, None, 0, -999
    ev = None
    out = []

    def hot(i):
        return V3.hot_at(i)

    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + (cur - 1) * r2[i] + (2 - cur) * r1[i] if cur > 1 else 1 + (bt.RC if cur == 0 else r1[i])
        if pend is not None:
            eq *= 1 - bt.COST * abs(pend - cur)
            if log is not None:
                if pend == 0 and ev is not None and ev.get("type") == "heat" and "exit_px" not in ev:
                    ev["exit_px"], ev["exit_d"], ev["exit_i"] = PX[i], DAYS[i], i
                elif pend > 0 and ev is not None and "exit_px" in ev:
                    ev["in_px"], ev["in_d"], ev["in_i"] = PX[i], DAYS[i], i
                    log.append(ev)
                    ev = None
            cur, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        out.append(eq)
        if i < 260:
            continue
        hot_run = hot_run + 1 if hot(i) else 0
        if not WE[i] and state == 1 and hot_run >= persist:
            state, heat_out, out_i = 0, True, i
            ev = {"type": "heat", "sig_d": DAYS[i]}
            if cur != 0:
                pend = 0.0
            continue
        if WE[i]:
            h = hot_run >= persist
            p = PX[i]
            above = p >= M80[i] * 0.975
            if state == 0:
                if heat_out and not above:
                    heat_out = False
                cooled = DEV[i] is None or (DEV[i] < 0.125 and Z[i] <= 2.0)
                reent = heat_out and cooled and above and (i - out_i > lock)
                if (p > M60[i] * 1.01 and not hot(i)) or reent:
                    state, heat_out = 1, False
            elif h:
                state, heat_out, out_i = 0, True, i
                ev = {"type": "heat", "sig_d": DAYS[i]}
            elif not above:
                state, heat_out = 0, False
                ev = {"type": "price", "sig_d": DAYS[i]}
            t = 2.0 if state == 1 else 0.0
            if t != cur:
                pend = t
    yrs = (i1 - i0) / bt.TD
    res = (eq ** (1 / yrs) - 1, mdd)
    return res + (out,) if curve else res


PER = [("2002-01-01", "2026-12-31"), ("2002-01-01", "2012-12-31"), ("2013-01-01", "2026-12-31")]


def fmt(**kw):
    rs = [run(a, b, **kw) for a, b in PER]
    rr = run("2015-09-01", "2026-12-31", real=True, **kw)
    return rs, rr, " | ".join(f"{c:5.1%}/{m:6.1%}" for c, m in rs) + f" | 真實 {rr[0]:5.1%}/{rr[1]:6.1%}"


def yearly(**kw):
    _, _, e = run("2002-01-01", "2026-12-31", curve=True, **kw)
    i0 = next(i for i, x in enumerate(DAYS) if x >= "2002-01-01")
    last, prev, res = {}, 1.0, {}
    for k, v in enumerate(e):
        last[DAYS[i0 + k][:4]] = v
    for y in sorted(last):
        res[y] = last[y] / prev - 1
        prev = last[y]
    return res


def main():
    L = ["研究 189：融資過熱出場的來回成本"]
    base = fmt()
    L.append("v3（核對；本檔引擎）：" + base[2])
    L.append("strategy_v3 原引擎     ：" + V3.fmt())
    log = []
    run("2002-01-01", "2026-12-31", log=log)
    L.append(f"\n【逐筆】過熱出場後到再進場（加權變動：正＝錯過上漲、負＝躲過下跌）共 {len(log)} 次")
    groups = {"≤10 天": [], "11～40 天": [], ">40 天": []}
    for e in log:
        gap = e["in_i"] - e["exit_i"]
        chg = e["in_px"] / e["exit_px"] - 1
        lo = min(PX[e["exit_i"]:e["in_i"] + 1]) / e["exit_px"] - 1
        g = "≤10 天" if gap <= 10 else ("11～40 天" if gap <= 40 else ">40 天")
        groups[g].append(chg)
        L.append(f"  {e['exit_d']} 出 {e['exit_px']:>8,.0f} → {e['in_d']} 進 {e['in_px']:>8,.0f}  間隔 {gap:>3} 天  加權 {chg:+6.1%}（期間最低 {lo:+6.1%}）")
    for g, v in groups.items():
        if v:
            L.append(f"  {g}：{len(v)} 次，錯過（正）{sum(x > 0 for x in v)} 次、躲過 {sum(x < 0 for x in v)} 次，平均 {sum(v) / len(v):+.1%}、合計 {sum(v):+.1%}（2 倍部位約 ×2）")
    L.append("\n【變形】（全期｜前段｜後段｜真實；逐年勝／輸 v3）")
    yb = yearly()
    for persist in (1, 2, 3):
        for lock in (0, 5, 10):
            if persist == 1 and lock == 0:
                continue
            rs, rr, s = fmt(persist=persist, lock=lock)
            yv = yearly(persist=persist, lock=lock)
            w = sum(yv[y] > yb[y] + 1e-9 for y in yb)
            l_ = sum(yv[y] < yb[y] - 1e-9 for y in yb)
            ok = all(a[0] >= b[0] for a, b in zip(rs, base[0])) and rr[0] >= base[1][0]
            L.append(f"  連續 {persist} 天、回補鎖 {lock:>2} 天：{s}  勝 {w}／輸 {l_}{'  ★四段都不輸' if ok else ''}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究189_融資過熱出場來回成本.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()


def extra():
    L = ["\n【補充 1】過熱時保留部分部位（研究 86 是週五版，這裡在每日檢查的現行版重驗；hot_lev＝過熱期間仍在出場線上時保留的槓桿）"]
    L.append(f"  全出（現行）  {V3.fmt()}")
    for hl in (0.5, 1.0, 1.5):
        L.append(f"  保留 {hl}x     {V3.fmt(hot_lev=hl)}")
    L.append("\n【補充 2】出場當下能不能分辨「短來回」？（≤10 天回來 vs >40 天）")
    log = []
    run("2002-01-01", "2026-12-31", log=log)
    rows = []
    for e in log:
        i = next(k for k, d in enumerate(DAYS) if d == e["sig_d"])
        gap = e["in_i"] - e["exit_i"]
        rows.append((gap, DEV[i], Z[i], PX[i] / M80[i] - 1, PX[i] / max(PX[i - 59:i + 1]) - 1, PX[i] / PX[i - 20] - 1))
    for name, f in (("≤10 天", lambda g: g <= 10), ("11～40", lambda g: 10 < g <= 40), (">40 天", lambda g: g > 40)):
        g = [r for r in rows if f(r[0])]
        if g:
            avg = lambda k: sum(r[k] for r in g) / len(g)  # noqa: E731
            L.append(f"  {name}（{len(g)}）：偏離 {avg(1):+.1%}、z {avg(2):.2f}、離 MA80 {avg(3):+.1%}、離 60 日高 {avg(4):+.1%}、20 日漲跌 {avg(5):+.1%}")
    L.append("  逐筆（間隔、偏離、z、離 MA80、離 60 日高、20 日漲跌）：")
    for r in rows:
        L.append(f"    {r[0]:>3} 天  {r[1]:+.1%}  z {r[2]:.2f}  {r[3]:+.1%}  {r[4]:+.1%}  {r[5]:+.1%}")
    return L


if __name__ == "__main__":
    add = extra()
    print("\n".join(add))
    open(os.path.join(HERE, "結果_研究189_融資過熱出場來回成本.txt"), "a", encoding="utf-8").write("\n".join(add) + "\n")
