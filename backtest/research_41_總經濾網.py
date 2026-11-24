"""研究 41：總經濾網（新版基準：出場 MA80×0.975＋融資過熱濾網 250 日 17.5%）

指標（美國資料用台股當天之前最後一筆，不偷看）：
- 美國 10 年期公債殖利率（^TNX）：近 n 日上升超過 x 個百分點 → 不進場／出場
- 美元指數（DX-Y.NYB）：站上 n 日均線（美元強勢）→ 不進場／出場
- 銅金比（HG=F ÷ GC=F）：跌破 n 日均線（景氣轉弱）→ 不進場／出場
- 油價（CL=F）：近 n 日漲超過 x → 不進場
每組做 100 次循環平移安慰劑（把指標序列整段平移，保留自相關、打斷與台股的時間對應）
用法：python -X utf8 backtest/research_41_總經濾網.py
"""
import bisect
import json
import os
import random
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location("r40", os.path.join(HERE, "research_40_候選組合.py"))
R40 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R40)
bt = R40.bt
DAYS, PX, N, WE = R40.DAYS, R40.PX, R40.N, R40.WE
M60, M80 = R40.M60, R40.M80
NY = timezone(timedelta(hours=-5))
HOT = [i >= 250 and (v := R40.R38.R.ratio_dev(i, 250)) is not None and v > 0.175 for i in range(N)]
PER = [("2002-01-01", "2026-12-31"), ("2002-01-01", "2012-12-31"), ("2013-01-01", "2026-12-31")]
REAL = ("2015-09-01", "2026-12-31")


def us(name):
    r = json.load(open(os.path.join(HERE, name + ".json")))
    m = {datetime.fromtimestamp(t, NY).strftime("%Y-%m-%d"): c for t, c in zip(r["timestamp"], r["indicators"]["quote"][0]["close"]) if c and c > 0}
    ks = sorted(m)
    return [m[ks[k]] if (k := bisect.bisect_left(ks, d) - 1) >= 0 else None for d in DAYS]


def sma_arr(x, n):
    out, s, q = [None] * len(x), 0.0, []
    for i, v in enumerate(x):
        if v is None:
            continue
        q.append(v)
        s += v
        if len(q) > n:
            s -= q.pop(0)
        if len(q) == n:
            out[i] = s / n
    return out


def run(start, end, block=None, force=None, real=False):
    r2 = R40.R32.R.R2R if real else bt.R2
    i0 = next(i for i, x in enumerate(DAYS) if x >= start)
    i1 = max(i for i, x in enumerate(DAYS) if x <= end)
    eq = peak = 1.0
    mdd, on, pos, pend = 0.0, False, False, None
    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + (r2[i] if pos else bt.RC)
        if pend is not None:
            eq *= 1 - bt.COST * 2
            pos, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if WE[i] and i >= 260:
            if on:
                on = not (PX[i] < M80[i] * 0.975 or HOT[i] or (force is not None and force[i]))
            else:
                on = PX[i] > M60[i] * 1.01 and not HOT[i] and not (block is not None and block[i])
            if on != pos:
                pend = on
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd


def shifted(flags, rng):
    i0 = next((i for i in range(N) if flags[i] is not None), 0)
    seg = flags[i0:]
    k = rng.randrange(250, len(seg) - 250)
    return [None] * i0 + seg[k:] + seg[:k]


def main():
    tnx, dxy, cu, au, oil = us("TNX"), us("DXY"), us("COPPER"), us("GOLD"), us("OIL")
    cg = [c / g if c and g else None for c, g in zip(cu, au)]
    rng = random.Random(41)
    L = ["研究 41：總經濾網（新版基準；全期 2002- | 前段 -2012 | 後段 2013- | 真實；p＝100 次平移，看全期年化）"]
    base = [run(a, b) for a, b in PER]
    bre = run(*REAL, real=True)
    L.append("新版基準 " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in base) + f" | 真實 {bre[0]:.1%}/{bre[1]:.1%}")
    tests = []
    for n, x in ((20, 0.3), (60, 0.5), (120, 0.75)):
        f = [None if (tnx[i] is None or i < n or tnx[i - n] is None) else (tnx[i] - tnx[i - n] > x) for i in range(N)]
        tests.append((f"10Y 殖利率 {n} 日升 > {x} 個百分點", f))
    for n in (50, 100, 200):
        m = sma_arr(dxy, n)
        tests.append((f"美元指數 > MA{n}", [None if m[i] is None else dxy[i] > m[i] for i in range(N)]))
        m = sma_arr(cg, n)
        tests.append((f"銅金比 < MA{n}", [None if m[i] is None else cg[i] < m[i] for i in range(N)]))
    for n, x in ((20, 0.2), (60, 0.3)):
        tests.append((f"油價 {n} 日漲 > {x:.0%}", [None if (oil[i] is None or i < n or oil[i - n] is None) else oil[i] / oil[i - n] - 1 > x for i in range(N)]))
    for nm, f in tests:
        fb = [bool(v) for v in f]
        for mode in ("block", "both"):
            kw = dict(block=fb) if mode == "block" else dict(block=fb, force=fb)
            rs = [run(a, b, **kw) for a, b in PER]
            rr = run(*REAL, real=True, **kw)
            sims = []
            for _ in range(100):
                sf = [bool(v) for v in shifted(f, rng)]
                sims.append(run(*PER[0], **(dict(block=sf) if mode == "block" else dict(block=sf, force=sf)))[0])
            p = (sum(x >= rs[0][0] for x in sims) + 1) / 101
            L.append(f"{nm:22s} {'擋進場' if mode == 'block' else '擋進＋出場'}  " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in rs)
                     + f" | 真實 {rr[0]:.1%}/{rr[1]:.1%} | 平移中位 {sorted(sims)[50]:.1%} p {p:.2f}")
            print(L[-1], flush=True)
    open(os.path.join(HERE, "結果_研究41_總經濾網.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
