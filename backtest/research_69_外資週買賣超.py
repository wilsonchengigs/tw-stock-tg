"""研究 69：外資（現貨）週買賣超當現行策略的濾網／訊號（資料：backtest/inst_weekly.csv，證交所 BFI82U 週報，2004-04～）

金額隨市場規模成長，所以用「近 n 週累計買賣超」相對過去 52 週的 z-score（只用當時以前的資料）
1. 事件研究：單週外資買賣超 z < -2（大賣）／> +2（大買）之後 4／12／24 週加權報酬，去叢集 8 週
2. 策略（新版基準＝出場 2.5%＋融資過熱，同研究 58 的 run 架構）：
   A 濾網：4 週累計 z < -x → 不進場；持有中也出場
   B 只擋進場：4 週累計 z < -x → 不進場（持有中不管）
   C 反向提早進場：空手時 4 週累計 z < -x 後、指數自 10 日低點反彈 3% → 提早進（停損近期低點）
   週資料循環平移 100 次安慰劑
用法：python -X utf8 backtest/research_69_外資週買賣超.py
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
spec = importlib.util.spec_from_file_location("r58", os.path.join(HERE, "research_58_融資維持率.py"))
R58 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R58)
R48, bt, PX, N, DAYS, WE, IDX = R58.R48, R58.bt, R58.PX, R58.N, R58.DAYS, R58.WE, R58.IDX

rows = [(r["week_end"], float(r["foreign"])) for r in csv.DictReader(open(os.path.join(HERE, "inst_weekly.csv"), encoding="utf-8"))]
rows.sort()
WD = [d for d, _ in rows]
FV = [v for _, v in rows]


def zscore(vals, n):
    acc = [sum(vals[max(0, k - n + 1):k + 1]) for k in range(len(vals))]
    out = [None] * len(vals)
    for k in range(len(vals)):
        hist = acc[max(0, k - 52):k]
        if len(hist) >= 40:
            sd = statistics.pstdev(hist)
            out[k] = (acc[k] - statistics.mean(hist)) / sd if sd > 0 else None
    return out


def daily_from(wd, wv):
    out = []
    for d in DAYS:
        k = bisect.bisect_right(wd, d) - 1
        out.append(wv[k] if k >= 0 else None)
    return out


def fwd_w(d, weeks):
    i = IDX.get(d)
    if i is None or i + weeks * 5 >= N:
        return None
    return PX[i + weeks * 5] / PX[i] - 1


def run(start, end, z, x=None, mode=None, real=False):
    r2 = R48.R.R40.R32.R.R2R if real else bt.R2
    i0 = next(i for i, dd in enumerate(DAYS) if dd >= start)
    i1 = max(i for i, dd in enumerate(DAYS) if dd <= end)
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
        sell = x is not None and z[i] is not None and z[i] < -x
        hot = R48.HOT[i]
        block = hot or (sell and mode in ("A", "B"))
        if st == 0:
            if PX[i] > R48.M60[i] * 1.01 and not block:
                st = 2
            elif mode == "C" and any(z[j] is not None and z[j] < -x for j in range(i - 10, i + 1)) and not hot:
                lo = min(PX[i - 10:i + 1])
                if PX[i] > lo * 1.03:
                    st, stop = 1, lo
        elif st == 1:
            if PX[i] > R48.M60[i] * 1.01:
                st = 2
            elif PX[i] < stop:
                st = 0
        elif PX[i] < R48.M80[i] * 0.975 or hot or (sell and mode == "A"):
            st = 0
        if (st != 0) != pos:
            pend = st != 0
    return eq ** (1 / ((i1 - i0) / bt.TD)) - 1, mdd


def main():
    L = ["研究 69：外資現貨週買賣超（證交所 BFI82U）"]
    L.append(f"資料 {WD[0]}～{WD[-1]}，{len(WD)} 週；最近 8 週外資買賣超（億）：" + "、".join(f"{d[5:]} {v / 1e8:+,.0f}" for d, v in rows[-8:]))
    z1 = zscore(FV, 1)
    base = {h: [x for d in WD if (x := fwd_w(d, h)) is not None] for h in (4, 12, 24)}
    L.append("所有週：" + "；".join(f"{h} 週 {statistics.mean(v):+.1%}" for h, v in base.items()))
    for th, below in ((2.0, True), (1.5, True), (2.0, False), (1.5, False)):
        ev, last = [], -99
        for k, v in enumerate(z1):
            hit = v is not None and (v < -th if below else v > th)
            if hit and k - last > 8:
                ev.append(k)
            if hit:
                last = k
        cells = []
        for h in (4, 12, 24):
            v = [x for k in ev if (x := fwd_w(WD[k], h)) is not None]
            if v:
                cells.append(f"{h} 週 {statistics.mean(v):+.1%}（上漲 {sum(x > 0 for x in v) / len(v):.0%}）")
        L.append(f"單週外資 z {'<' if below else '>'} {'-' if below else '+'}{th}：{len(ev)} 次；" + "；".join(cells))
    L.append(f"最新一週單週 z＝{z1[-1]:+.2f}")

    PER = [("2005-01-01", "2026-12-31"), ("2005-01-01", "2012-12-31"), ("2013-01-01", "2026-12-31")]
    REAL = ("2015-09-01", "2026-12-31")
    nil = [None] * N
    b = [run(a, c, nil) for a, c in PER]
    L.append("\n== 策略（2005- | 2005-2012 | 2013- | 真實；p＝100 次平移）==")
    L.append("新版基準 " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in b) + f" | 真實 {run(*REAL, nil, real=True)[0]:.1%}")
    rng = random.Random(69)
    for n in (4, 8):
        z = daily_from(WD, zscore(FV, n))
        for mode in ("A", "B", "C"):
            for x in (1.0, 1.5, 2.0):
                res = [run(a, c, z, x, mode) for a, c in PER]
                rl = run(*REAL, z, x, mode, real=True)
                sims = []
                for _ in range(100):
                    k = rng.randrange(52, len(FV) - 52)
                    zz = daily_from(WD, zscore(FV[k:] + FV[:k], n))
                    sims.append(run(*PER[0], zz, x, mode)[0])
                p = (sum(s >= res[0][0] for s in sims) + 1) / 101
                nm = {"A": "濾網（擋進＋出場）", "B": "只擋進場", "C": "外資大賣後提早進"}[mode]
                L.append(f"{n}週 z<-{x} {nm:12s} " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in res) + f" | 真實 {rl[0]:.1%}/{rl[1]:.1%} | p {p:.2f}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究69_外資週買賣超.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
