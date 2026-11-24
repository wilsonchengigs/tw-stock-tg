"""研究 58：大盤融資維持率（證交所官方，每週最後交易日，2004-02～；算法同日報 report.py）

市場常見說法：維持率跌破 140%（或 130%）＝融資斷頭、恐慌見底，是買點；維持率很高（> 170%）＝散戶樂觀過熱。
1. 事件研究：維持率首次跌破門檻（去叢集 8 週）後 4／12／24 週加權報酬、上漲機率、之後再跌 10% 機率；與「所有週」比較
2. 策略：空手時，近 2 週維持率曾 < X、且指數從近 10 日低點反彈 3% → 提早進場（停損近期低點，站上 MA60×1.01 轉正常）；
   持有時維持率 > Y → 出場（過熱）。新版基準（出場 2.5%＋融資過熱）；週資料循環平移 100 次安慰劑
資料：backtest/margin_ratio_weekly.csv（build_margin_ratio.py）
用法：python -X utf8 backtest/research_58_融資維持率.py
"""
import bisect
import csv
import importlib.util
import os
import random
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r48", os.path.join(HERE, "research_48_基本面景氣.py"))
R48 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R48)
R, bt, PX, N, DAYS, WE = R48.R, R48.bt, R48.PX, R48.N, R48.DAYS, R48.WE
rows = [(r["date"], float(r["ratio"])) for r in csv.DictReader(open(os.path.join(HERE, "margin_ratio_weekly.csv"), encoding="utf-8"))]
WD = [d for d, _ in rows]
WV = [v for _, v in rows]
IDX = {d: i for i, d in enumerate(DAYS)}


def daily_from(weekly_vals):
    """週值 → 每日（用當天以前最近一週的值）"""
    out = []
    for d in DAYS:
        k = bisect.bisect_right(WD, d) - 1
        out.append(weekly_vals[k] if k >= 0 else None)
    return out


MR = daily_from(WV)


def fwd_w(d, weeks):
    i = IDX.get(d)
    if i is None or i + weeks * 5 >= N:
        return None
    return PX[i + weeks * 5] / PX[i] - 1


def event_study(L):
    L.append(f"資料 {WD[0]}～{WD[-1]}，{len(WD)} 週；維持率中位 {statistics.median(WV):.1f}%、最低 {min(WV):.1f}%（{WD[WV.index(min(WV))]}）、最高 {max(WV):.1f}%")
    base = {h: [x for d in WD if (x := fwd_w(d, h)) is not None] for h in (4, 12, 24)}
    L.append("所有週：" + "；".join(f"{h} 週平均 {statistics.mean(v):+.1%}、上漲 {sum(x > 0 for x in v) / len(v):.0%}" for h, v in base.items()))
    for th, below in ((150, True), (140, True), (135, True), (130, True), (170, False), (175, False), (180, False)):
        ev, last = [], -99
        for k, v in enumerate(WV):
            hit = v < th if below else v > th
            if hit and k - last > 8:
                ev.append(k)
            if hit:
                last = k
        L.append(f"\n維持率 {'<' if below else '>'} {th}%：{len(ev)} 次（{', '.join(WD[k] for k in ev[:12])}{'…' if len(ev) > 12 else ''}）")
        for h in (4, 12, 24):
            v = [x for k in ev if (x := fwd_w(WD[k], h)) is not None]
            if v:
                L.append(f"  {h:2d} 週：平均 {statistics.mean(v):+.1%}（所有週 {statistics.mean(base[h]):+.1%}）、上漲 {sum(x > 0 for x in v) / len(v):.0%}、n={len(v)}")
        lo = []
        for k in ev:
            i = IDX.get(WD[k])
            if i is not None and i + 120 < N:
                lo.append(min(PX[i:i + 121]) / PX[i] - 1)
        if lo:
            L.append(f"  之後 120 日內再跌超過 10%：{sum(x < -0.10 for x in lo) / len(lo):.0%}")


def run(start, end, mr, low=None, high=None, real=False):
    r2 = R.R40.R32.R.R2R if real else bt.R2
    i0 = next(i for i, x in enumerate(DAYS) if x >= start)
    i1 = max(i for i, x in enumerate(DAYS) if x <= end)
    eq = peak = 1.0
    mdd, st, pos, pend, stop = 0.0, 0, False, None, 0.0
    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + (r2[i] if pos else bt.RC)
        if pend is not None:
            eq *= 1 - bt.COST * 2
            pos, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if not WE[i] or i < 260:
            continue
        hot = R48.HOT[i] or (high is not None and mr[i] is not None and mr[i] > high)
        if st == 0:
            if PX[i] > R48.M60[i] * 1.01 and not hot:
                st = 2
            elif low is not None and any(mr[j] is not None and mr[j] < low for j in range(i - 10, i + 1)) and not hot:
                lo = min(PX[i - 10:i + 1])
                if PX[i] > lo * 1.03:
                    st, stop = 1, lo
        elif st == 1:
            if PX[i] > R48.M60[i] * 1.01:
                st = 2
            elif PX[i] < stop:
                st = 0
        elif PX[i] < R48.M80[i] * 0.975 or hot:
            st = 0
        if (st != 0) != pos:
            pend = st != 0
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd


def shifted_weekly(rng):
    k = rng.randrange(52, len(WV) - 52)
    return daily_from(WV[k:] + WV[:k])


def main():
    L = ["研究 58：大盤融資維持率（證交所官方週資料）"]
    event_study(L)
    PER = [("2005-01-01", "2026-12-31"), ("2005-01-01", "2012-12-31"), ("2013-01-01", "2026-12-31")]
    REAL = ("2015-09-01", "2026-12-31")
    L.append("\n== 策略（新版基準；2005- | 2005-2012 | 2013- | 真實；p＝100 次平移）==")
    base = [run(a, b, MR) for a, b in PER]
    L.append("新版基準 " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in base) + f" | 真實 {run(*REAL, MR, real=True)[0]:.1%}")
    rng = random.Random(58)
    for nm, kw in ([(f"維持率 < {x} 提早進場", dict(low=x)) for x in (150, 145, 140, 135, 130)]
                   + [(f"維持率 > {y} 出場不進", dict(high=y)) for y in (170, 175, 180, 185)]
                   + [("維持率 < 140 提早進＋> 180 出場", dict(low=140, high=180))]):
        rs = [run(a, b, MR, **kw) for a, b in PER]
        rr = run(*REAL, MR, real=True, **kw)
        sims = [run(*PER[0], shifted_weekly(rng), **kw)[0] for _ in range(100)]
        p = (sum(x >= rs[0][0] for x in sims) + 1) / 101
        L.append(f"{nm:28s} " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in rs) + f" | 真實 {rr[0]:.1%}/{rr[1]:.1%} | p {p:.2f}")
        print(L[-1], flush=True)
    L.append(f"\n最新：{WD[-1]} 維持率 {WV[-1]:.1f}%")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究58_融資維持率.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
