"""研究 63b：「爆量收黑 → 隔天開盤買進、抱 H 天」做成可交易規則（研究 63 事件研究的延伸；與研究 61 的順勢相反）

- 訊號：量 ≥ k × 前 20 日平均，且收盤 < 前收（跌幅門檻 0／-1％／-2％）
  量的來源：證交所成交金額（1998～）或台指期一般時段全月份口數（1998～，早期流動性低）
- 進場：隔天開盤（加權指數開盤，近似台指期）；出場：H 個交易日後收盤；不設停損停利
- 不重疊：持有固定 H 天，持有中出現的訊號略過
- 成本：每筆來回 3 點
- 對照：
  (a) 同樣持有天數、隨機進場日（2000 次）→ 平均每筆報酬的分布，看實際排第幾（扣掉台股長期向上）
  (b) 「收黑但沒爆量（<1.2x）」同規則
  (c) 全期買進持有的「每天平均報酬 × 持有天數」
- 參數格點：k ∈ {1.3,1.5,1.8,2.0} × 跌幅 ∈ {0,-1%,-2%} × H ∈ {3,5,10,20} × 量來源 2 種，全部列出中位數，避免只挑最好的
- 分期：1998-2012／2013-2026
用法：python -X utf8 backtest/research_63b_爆量收黑買進.py
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
O, C, N, DAYS = r61.O, r61.C, r61.N, r61.DAYS
COST = 3.0
START = next(i for i, d in enumerate(DAYS) if d >= "1998-09-01")


def signals(vsrc, k, drop, lo="1998", hi="2027", calm=False):
    vr = r61.VR[vsrc]
    out = []
    for i in range(max(START, 21), N - 1):
        if not (lo <= DAYS[i] < hi) or vr[i] is None:
            continue
        ch = C[i] / C[i - 1] - 1
        ok_vol = vr[i] < 1.2 if calm else vr[i] >= k
        if ok_vol and ch < drop:
            out.append(i)
    return out


def trades(sig, H):
    """持有固定 H 天；持有中出現的訊號略過。回傳 [(進場 index, 出場 index, 報酬)]"""
    out = []
    busy = -1
    for i in sig:
        e = i + 1
        if e <= busy or e >= N:
            continue
        x = min(i + H, N - 1)
        out.append((e, x, C[x] / O[e] - 1 - COST / O[e]))
        busy = x
    return out


def random_ev(trs, rng, lo="1998", hi="2027", reps=2000):
    """同樣筆數、同樣持有天數分布的隨機進場日，平均每筆報酬分布"""
    lens = [x - e for e, x, _r in trs]
    pool = [i for i in range(max(START, 21), N - 25) if lo <= DAYS[i] < hi]
    res = []
    for _ in range(reps):
        rr = []
        for ln in lens:
            e = rng.choice(pool)
            x = min(e + ln, N - 1)
            rr.append(C[x] / O[e] - 1 - COST / O[e])
        res.append(statistics.mean(rr))
    return sorted(res)


def main():
    rng = random.Random(633)
    L = ["研究 63b：爆量收黑 → 隔天開盤買進、抱 H 天（加權指數近似台指期；成本每筆 3 點；持有中訊號略過）"]
    years = (len([d for d in DAYS if d >= "1998-09-01"])) / 245
    grid = []
    for vsrc, k, drop, H in itertools.product(("成交金額", "台指期口數"), (1.3, 1.5, 1.8, 2.0), (0.0, -0.01, -0.02), (3, 5, 10, 20)):
        sig = signals(vsrc, k, drop)
        trs = trades(sig, H)
        if len(trs) < 15:
            continue
        rets = [t[2] for t in trs]
        grid.append(((vsrc, k, drop, H), trs, statistics.mean(rets), sum(r > 0 for r in rets) / len(rets)))
    L.append(f"\n== 1. 全格點（至少 15 筆）：{len(grid)} 組 ==")
    L.append("量來源      k    跌幅   H   筆數  年筆數  勝率   每筆平均  隨機進場中位  超額    p(單尾)  持有天數占比")
    pvals = []
    for p, trs, ev, win in grid:
        rnd = random_ev(trs, rng, reps=500)
        pv = (sum(x >= ev for x in rnd) + 1) / (len(rnd) + 1)
        pvals.append(pv)
        days_in = sum(x - e + 1 for e, x, _r in trs)
        L.append(f"{p[0]:8s} {p[1]:.1f}  {p[2]:+.0%}  {p[3]:2d}  {len(trs):4d}  {len(trs) / years:5.1f}  {win:4.0%}  {ev:+7.2%}   {rnd[len(rnd) // 2]:+7.2%}   "
                 f"{ev - rnd[len(rnd) // 2]:+6.2%}  {pv:.3f}   {days_in / (years * 245):5.1%}")
    evx = sorted(g[2] for g in grid)
    L.append(f"\n格點每筆平均報酬中位 {evx[len(evx) // 2]:+.2%}；p<0.05 的組數 {sum(p < 0.05 for p in pvals)}/{len(pvals)}；p<0.01 的 {sum(p < 0.01 for p in pvals)}")

    # 2. 代表組（事件研究最直接的對應）：成交金額 1.5x、收黑、H=5／10／20
    L.append("\n== 2. 代表組：成交金額 ≥1.5x、收黑（任何跌幅）==")
    for H in (5, 10, 20):
        L.append(f"-- 抱 {H} 天 --")
        for lab, lo, hi in (("全期", "1998", "2027"), ("1998-2012", "1998", "2013"), ("2013-2026", "2013", "2027")):
            trs = trades(signals("成交金額", 1.5, 0.0, lo, hi), H)
            if len(trs) < 5:
                L.append(f"  {lab}：{len(trs)} 筆，樣本不足")
                continue
            rets = [t[2] for t in trs]
            rnd = random_ev(trs, rng, lo, hi, reps=2000)
            ev = statistics.mean(rets)
            L.append(f"  {lab:9s}：{len(trs):3d} 筆 勝率 {sum(r > 0 for r in rets) / len(rets):4.0%} 每筆 {ev:+.2%}（≈{ev * 40000:+.0f} 點、大台 {ev * 40000 * 200:+,.0f} 元）"
                     f"  隨機進場中位 {rnd[1000]:+.2%}  p＝{(sum(x >= ev for x in rnd) + 1) / 2001:.3f}  最差一筆 {min(rets):+.1%}")
        calm = trades(signals("成交金額", 1.5, 0.0, calm=True), H)
        cr = [t[2] for t in calm]
        L.append(f"  對照 收黑但量平(<1.2x)：{len(cr)} 筆 勝率 {sum(r > 0 for r in cr) / len(cr):.0%} 每筆 {statistics.mean(cr):+.2%}")

    # 3. 逐筆明細（代表組 H=10）
    L.append("\n== 3. 代表組 H=10 逐筆 ==")
    for e, x, r in trades(signals("成交金額", 1.5, 0.0), 10):
        L.append(f"  {DAYS[e]} → {DAYS[x]}  {r:+.2%}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究63b_爆量收黑買進.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
