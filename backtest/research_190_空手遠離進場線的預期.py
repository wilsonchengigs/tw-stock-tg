"""研究 190：空手、而且指數離進場線很遠時（2026-11-25：38,195 vs 進場線 45,821，-16.6%）該有什麼預期

問題（預期管理，不是新規則）：
- 歷史上同樣情況，多久才重新進場？等待期間大盤還會再跌多少？
- 重新進場那一筆（進場→下次出場）賺多少、勝率？
- 事件後 1／3／6／12 個月加權報酬
事件：主策略空手、收盤 ≤ 進場線（MA60×1.01）×(1−d)，d＝10／15／20%；每段空手期只取第一次（獨立事件）
兩套：v3（含融資濾網，2002～）與核心均線（無融資濾網，1991～，含 1990 年代）
用法：python -X utf8 backtest/research_190_空手遠離進場線的預期.py
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


R186 = load("r186", "research_186_主策略全面健檢.py")
R187 = load("r187", "research_187_高波動來回刷.py")
TD = 245


def episodes(days, px, m60, exec_pos, eq, d):
    """exec_pos[i]＝第 i 天收盤後持有的槓桿；eq＝每日淨值（同索引）；回傳事件清單"""
    out, n = [], len(px)
    i = 61
    while i < n:
        if exec_pos[i] == 0 and m60[i] and px[i] <= m60[i] * 1.01 * (1 - d):
            ent = next((k for k in range(i + 1, n) if exec_pos[k] > 0 and exec_pos[k - 1] == 0), None)
            ex = next((k for k in range(ent + 1, n) if exec_pos[k] == 0), None) if ent else None
            fwd = {m: (px[i + int(m * 21)] / px[i] - 1 if i + int(m * 21) < n else None) for m in (1, 3, 6, 12)}
            out.append({"d": days[i], "gap": px[i] / (m60[i] * 1.01) - 1, "ent": ent, "ex": ex,
                        "wait": (ent - i) if ent else None,
                        "to_ent": (px[ent] / px[i] - 1) if ent else None,
                        "low": min(px[i:(ent or n - 1) + 1]) / px[i] - 1,
                        "trade": (eq[ex] / eq[ent] - 1) if (ent and ex) else ((eq[-1] / eq[ent] - 1) if ent else None),
                        "open": ent is not None and ex is None, "fwd": fwd})
            i = ent if ent else n
        else:
            i += 1
    return out


def show(L, title, ev, days):
    L.append(f"\n== {title}：{len(ev)} 次 ==")
    for e in ev:
        f = e["fwd"]
        L.append(f"  {e['d']} 離進場線 {e['gap']:+.0%} → " + (f"{e['wait']:>3} 天後進場（{days[e['ent']]}），期間加權再跌最多 {e['low']:+.0%}、到進場 {e['to_ent']:+.0%}；"
                 f"那一筆 {e['trade']:+.0%}{'（持有中）' if e['open'] else ''}" if e["ent"] else f"還沒進場（期間最低 {e['low']:+.0%}）")
                 + "｜之後加權 " + " ".join(f"{m}月 {v:+.0%}" if v is not None else f"{m}月 —" for m, v in f.items()))
    done = [e for e in ev if e["ent"]]
    if done:
        w = sorted(e["wait"] for e in done)
        tr = [e["trade"] for e in done if not e["open"]]
        L.append(f"  等待：中位 {w[len(w) // 2]} 天（約 {w[len(w) // 2] / 21:.1f} 個月）、最短 {w[0]}、最長 {w[-1]}；"
                 f"等待期間再跌：中位 {sorted(e['low'] for e in done)[len(done) // 2]:+.0%}、最多 {min(e['low'] for e in done):+.0%}；"
                 f"進場時加權比事件日：中位 {sorted(e['to_ent'] for e in done)[len(done) // 2]:+.0%}")
        if tr:
            L.append(f"  進場那一筆（2x）：{len(tr)} 筆、勝率 {sum(t > 0 for t in tr) / len(tr):.0%}、平均 {sum(tr) / len(tr):+.0%}、中位 {sorted(tr)[len(tr) // 2]:+.0%}、最差 {min(tr):+.0%}、最好 {max(tr):+.0%}")
    for m in (1, 3, 6, 12):
        v = [e["fwd"][m] for e in ev if e["fwd"][m] is not None]
        if v:
            L.append(f"  事件後 {m:>2} 個月加權：{len(v)} 次、上漲 {sum(x > 0 for x in v) / len(v):.0%}、平均 {sum(v) / len(v):+.1%}、中位 {sorted(v)[len(v) // 2]:+.1%}、最差 {min(v):+.0%}")


def main():
    L = ["研究 190：空手且離進場線很遠時的預期（獨立事件：每段空手期取第一次）"]
    # v3
    DAYS, PX = R186.DAYS, R186.PX
    tr = []
    _, _, e = R186.run("2002-01-01", "2026-12-31", curve=True, trades=tr)
    i0 = next(i for i, d in enumerate(DAYS) if d >= "2002-01-01")
    pos, cur, tmap = [], 0.0, {d: b for d, a, b, _ in tr}
    for d in DAYS:
        cur = tmap.get(d, cur)
        pos.append(cur)
    eq = [1.0] * i0 + e
    m60 = R186.bt.get_sma(60)
    i = len(DAYS) - 1
    L.append(f"現況 {DAYS[i]}：收 {PX[i]:,.0f}、進場線 {m60[i] * 1.01:,.0f}（{PX[i] / (m60[i] * 1.01) - 1:+.1%}）、主策略 {'空手' if pos[i] == 0 else '在場'}")
    for d in (0.10, 0.15, 0.20):
        ev = [x for x in episodes(DAYS, PX, m60, pos, eq, d) if x["d"] >= "2002-03-01"]
        show(L, f"v3、離進場線 ≤ -{d:.0%}", ev, DAYS)
    # 核心（1991～，含 1990 年代）
    D, P = R187.D, R187.P0
    we = R187.WE0
    m60c, m80c = R187.sma(P, 60), R187.sma(P, 80)
    st, pend, cur, posc = False, None, 0.0, []
    r1 = [0.0] + [P[k] / P[k - 1] - 1 + 0.03 / TD for k in range(1, len(P))]
    eqc, E = [], 1.0
    for k in range(len(P)):
        if k > 0:
            E *= 1 + ((2 * r1[k] - 0.01 / TD) if cur > 0 else 0.01 / TD)
        if pend is not None:
            E *= 1 - 0.0025 * 2
            cur, pend = pend, None
        posc.append(cur)
        eqc.append(E)
        if we[k] and k >= 260:
            st = (not P[k] < m80c[k] * 0.975) if st else (P[k] > m60c[k] * 1.01)
            t = 2.0 if st else 0.0
            if t != cur:
                pend = t
    ev = [x for x in episodes(D, P, m60c, posc, eqc, 0.15) if x["d"] >= "1991-03-01"]
    show(L, "核心均線（無融資濾網，1991～）、離進場線 ≤ -15%", ev, D)
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究190_空手遠離進場線的預期.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
