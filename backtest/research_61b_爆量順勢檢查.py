"""研究 61b：檢查研究 61（爆量順勢短線）的結論是否被回測細節扭曲

檢查項目：
1. 跳空成交：原版在持有第 2 天以後，若開盤就跳過停損，仍以停損價成交（低估虧損）；
   若開盤就跳過停利，以停利價成交（低估獲利）。改成以開盤價成交，看期望值變多少。
2. 重疊持倉：原版在持有期間又出現訊號會再開一筆，同一段行情被重複計算。改成「有部位就不接新訊號」。
3. 樣本外：在 1998-2012 選出期望值最好的設定，拿到 2013-2026 看；反過來也做一次。
4. 多重比較：432 組裡挑最好的一組，本來就會比較好看。把每個訊號日的方向隨機翻轉（所有設定同一套翻轉），
   重算整個格點的「最佳期望值」，看實際最佳值在這個分布裡排第幾。
用法：python -X utf8 backtest/research_61b_爆量順勢檢查.py
"""
import importlib.util
import itertools
import os
import random
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("r61", os.path.join(HERE, "research_61_爆量順勢短線.py"))
r61 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r61)
O, H, LO, C, N, DAYS, COST = r61.O, r61.H, r61.LO, r61.C, r61.N, r61.DAYS, r61.COST_PTS


def trade_gap(i, d, s, t, hold):
    """同 r61.trade，但第 2 天起若開盤已越過停損／停利，以開盤價成交。回傳 (報酬, 出場 index)"""
    e = i + 1
    px = O[e]
    stop = px * (1 - d * s)
    tgt = px * (1 + d * t)
    for j in range(e, min(e + hold, N)):
        if j > e:
            if (d > 0 and O[j] <= stop) or (d < 0 and O[j] >= stop):
                return d * (O[j] / px - 1) - COST / px, j
            if (d > 0 and O[j] >= tgt) or (d < 0 and O[j] <= tgt):
                return d * (O[j] / px - 1) - COST / px, j
        hit_stop = (LO[j] <= stop) if d > 0 else (H[j] >= stop)
        hit_tgt = (H[j] >= tgt) if d > 0 else (LO[j] <= tgt)
        if hit_stop:
            return -s - COST / px, j
        if hit_tgt:
            return t - COST / px, j
    j = min(e + hold, N) - 1
    return d * (C[j] / px - 1) - COST / px, j


def run(sig, s, t, hold, gap=True, overlap=True, flip=None):
    rets = []
    busy = -1
    for i, d in sig:
        if flip is not None:
            d = d * flip[i]
        if not overlap and i + 1 <= busy:
            continue
        if gap:
            r, j = trade_gap(i, d, s, t, hold)
        else:
            r, j = r61.trade(i, d, s, t, hold), i + hold
        busy = j
        rets.append(r)
    return rets


def ev(rets):
    return statistics.mean(rets) if rets else float("nan")


def main():
    years = (r61.datetime.fromisoformat(DAYS[-1]) - r61.datetime.fromisoformat("1998-09-01")).days / 365.25
    L = ["研究 61b：爆量順勢短線的回測檢查（成本每筆 3 點；點數以指數 40,000 換算）"]
    params = list(itertools.product(("成交金額", "台指期口數"), (1.5, 2.0, 2.5), ("candle", "close"), (0.0, 0.01),
                                    (0.01, 0.02, 0.03), (0.02, 0.04, 0.06), (1, 3, 5, 10)))
    SIG = {}
    for p in params:
        SIG[p] = [x for x in r61.signals(*p[:4]) if DAYS[x[0]] >= "1998-09-01"]
    grid = [p for p in params if len(SIG[p]) >= 30]

    # 1+2：四種回測方式的整體分布
    L.append(f"\n== 1～2. 跳空成交與重疊持倉（{len(grid)} 組設定）==")
    L.append("方式                         期望值中位   最好      >0 組數   勝率中位")
    res = {}
    for nm, g, ov in (("原版（停損價成交、可重疊）", False, True), ("跳空以開盤成交、可重疊", True, True),
                      ("原版、不重疊", False, False), ("跳空以開盤成交、不重疊", True, False)):
        evs, wins = [], []
        for p in grid:
            rr = run(SIG[p], *p[4:], gap=g, overlap=ov)
            evs.append(ev(rr))
            wins.append(sum(x > 0 for x in rr) / len(rr))
            res[(nm, p)] = rr
        se = sorted(evs)
        L.append(f"{nm:24s}  {se[len(se) // 2]:+.3%}   {se[-1]:+.3%}   {sum(e > 0 for e in se):3d}/{len(se)}   {sorted(wins)[len(wins) // 2]:.0%}")
    base = "跳空以開盤成交、不重疊"
    best = max(grid, key=lambda p: ev(res[("原版（停損價成交、可重疊）", p)]))
    L.append(f"\n研究 61 的最佳組 {best}：")
    for nm in ("原版（停損價成交、可重疊）", "跳空以開盤成交、可重疊", "原版、不重疊", base):
        rr = res[(nm, best)]
        L.append(f"  {nm:24s} {len(rr):4d} 筆  勝率 {sum(x > 0 for x in rr) / len(rr):.0%}  每筆期望 {ev(rr):+.3%}（≈{ev(rr) * 40000:+.0f} 點）")

    # 3：樣本外（用修正後的回測方式）
    L.append("\n== 3. 樣本外（跳空以開盤成交、不重疊；至少 15 筆）==")
    for a, b, na, nb in ((("1998", "2013"), ("2013", "2027"), "1998-2012", "2013-2026"),
                         (("2013", "2027"), ("1998", "2013"), "2013-2026", "1998-2012")):
        sc = []
        for p in grid:
            ins = [x for x in SIG[p] if a[0] <= DAYS[x[0]] < a[1]]
            out = [x for x in SIG[p] if b[0] <= DAYS[x[0]] < b[1]]
            if len(ins) < 15 or len(out) < 15:
                continue
            sc.append((ev(run(ins, *p[4:], overlap=False)), ev(run(out, *p[4:], overlap=False)), p))
        sc.sort(key=lambda x: -x[0])
        top = sc[:10]
        outs = sorted(x[1] for x in sc)
        L.append(f"在 {na} 挑前 10 名 → {nb} 的期望值：平均 {statistics.mean(x[1] for x in top):+.3%}"
                 f"（同期全部設定中位 {outs[len(outs) // 2]:+.3%}；前 10 名裡 >0 的有 {sum(x[1] > 0 for x in top)} 組）")
        L.append(f"  第 1 名 {top[0][2]}：樣本內 {top[0][0]:+.3%} → 樣本外 {top[0][1]:+.3%}")
        # 排名相關
        ra = {id(x): k for k, x in enumerate(sorted(sc, key=lambda x: x[0]))}
        rb = {id(x): k for k, x in enumerate(sorted(sc, key=lambda x: x[1]))}
        n = len(sc)
        rho = 1 - 6 * sum((ra[id(x)] - rb[id(x)]) ** 2 for x in sc) / (n * (n * n - 1))
        L.append(f"  樣本內外期望值的排名相關 ρ＝{rho:+.2f}（{n} 組）")

    # 4：多重比較（隨機翻轉方向，看格點最佳值）
    L.append("\n== 4. 多重比較：隨機翻轉每個訊號日的方向，重算格點最佳期望值（300 次；跳空成交、不重疊）==")
    actual = {p: ev(res[(base, p)]) for p in grid}
    act_best = max(actual.values())
    act_med = statistics.median(actual.values())
    rng = random.Random(611)
    bests, meds = [], []
    sub = grid  # 全格點
    for _ in range(300):
        flip = [rng.choice((1, -1)) for _ in range(N)]
        e = [ev(run(SIG[p], *p[4:], overlap=False, flip=flip)) for p in sub]
        bests.append(max(e))
        meds.append(statistics.median(e))
    bests.sort()
    meds.sort()
    L.append(f"實際：格點最佳 {act_best:+.3%}、格點中位 {act_med:+.3%}")
    L.append(f"隨機方向：最佳的中位 {bests[150]:+.3%}、95 分位 {bests[285]:+.3%}；中位的中位 {meds[150]:+.3%}、5 分位 {meds[15]:+.3%}")
    L.append(f"實際最佳值的 p＝{(sum(b >= act_best for b in bests) + 1) / 301:.3f}；"
             f"實際中位值低於隨機的比例＝{sum(m > act_med for m in meds) / 300:.0%}")
    L.append(f"\n（資料期間 {DAYS[0]}～{DAYS[-1]}，約 {years:.1f} 年）")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究61b_爆量順勢檢查.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
