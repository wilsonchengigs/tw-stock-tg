"""研究 44：SMA vs WMA（線性加權）vs EMA（使用者提議）

同一套規則（週五判斷、隔天收盤成交；進場 > 均線(n_in)×1.01，出場 < 均線(n_out)×0.975；新版融資過熱濾網），
只換均線種類。格點：進場 n＝40／50／60／70／80、出場 n＝60／80／100／120（出場 ≥ 進場）。
因為 WMA／EMA 反應較快，同樣天數不公平，另外看「各自最佳的鄰近區域」。
歷史（2002–2026 三段＋真實）＋拔靴（研究 24 同路徑，300 條，不含融資濾網）
用法：python -X utf8 backtest/research_44_加權均線.py
"""
import importlib.util
import itertools
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r41", os.path.join(HERE, "research_41_總經濾網.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
spec = importlib.util.spec_from_file_location("r24", os.path.join(HERE, "research_24_候選參數拔靴檢驗.py"))
R24 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R24)
bt, DAYS, PX, N, WE = R.bt, R.DAYS, R.PX, R.N, R.WE
RR = R.R40.R32.R


def sma(x, n):
    out, s = [None] * len(x), 0.0
    for i, v in enumerate(x):
        s += v
        if i >= n:
            s -= x[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def wma(x, n):
    """線性加權：最近一天權重 n，最早一天權重 1"""
    out = [None] * len(x)
    den = n * (n + 1) / 2
    s = ws = 0.0  # s＝窗內總和、ws＝加權和
    for i, v in enumerate(x):
        if i < n:
            s += v
            ws += v * (i + 1)
            if i == n - 1:
                out[i] = ws / den
            continue
        ws = ws + n * v - s
        s = s + v - x[i - n]
        out[i] = ws / den
    return out


def ema(x, n):
    out, e, a = [None] * len(x), None, 2 / (n + 1)
    for i, v in enumerate(x):
        e = v if e is None else e + a * (v - e)
        if i >= n - 1:
            out[i] = e
    return out


KIND = {"SMA": sma, "WMA": wma, "EMA": ema}
_CACHE = {}


def ma(kind, n):
    k = (kind, n)
    if k not in _CACHE:
        _CACHE[k] = KIND[kind](PX, n)
    return _CACHE[k]


def run(kind, nin, nout, start, end, heat=True, real=False):
    r2 = RR.R2R if real else bt.R2
    mi, mo = ma(kind, nin), ma(kind, nout)
    i0 = next(i for i, x in enumerate(DAYS) if x >= start)
    i1 = max(i for i, x in enumerate(DAYS) if x <= end)
    eq = peak = 1.0
    mdd, on, pos, pend, tr = 0.0, False, False, None, 0
    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + (r2[i] if pos else bt.RC)
        if pend is not None:
            eq *= 1 - bt.COST * 2
            pos, pend = pend, None
            tr += 1
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if WE[i] and i >= 260:
            hot = heat and R.HOT[i]
            on = (not (PX[i] < mo[i] * 0.975 or hot)) if on else (PX[i] > mi[i] * 1.01 and not hot)
            if on != pos:
                pend = on
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd, tr / yrs


def boot(kind, nin, nout, paths):
    res = []
    for rets in paths:
        px = [100.0]
        for r in rets:
            px.append(px[-1] * (1 + r))
        mi, mo = KIND[kind](px, nin), KIND[kind](px, nout)
        eq = peak = 1.0
        mdd, on, pos, pend = 0.0, False, False, None
        for i in range(261, len(px)):
            r1 = px[i] / px[i - 1] - 1 + bt.DIV / bt.TD
            eq *= 1 + ((2 * r1 - bt.DRAG / bt.TD) if pos else bt.RC)
            if pend is not None:
                eq *= 1 - bt.COST * 2
                pos, pend = pend, None
            peak = max(peak, eq)
            mdd = min(mdd, eq / peak - 1)
            if i % 5 == 0:
                on = (not px[i] < mo[i] * 0.975) if on else (px[i] > mi[i] * 1.01)
                if on != pos:
                    pend = on
        res.append((eq ** (1 / R24.YEARS) - 1, mdd))
    return res


def main():
    L = ["研究 44：SMA vs WMA vs EMA（新版規則含融資濾網；全期 2002- | 前段 | 後段 | 真實；年交易）"]
    grid = [(a, b) for a, b in itertools.product((40, 50, 60, 70, 80), (60, 80, 100, 120)) if b >= a]
    base = [run("SMA", 60, 80, a, b) for a, b in R.PER]
    base_r = run("SMA", 60, 80, *R.REAL, real=True)
    L.append(f"現行 SMA60/80：" + " | ".join(f"{c:.1%}/{m:.1%}" for c, m, _ in base) + f" | 真實 {base_r[0]:.1%}/{base_r[1]:.1%}")
    summary = {}
    for kind in ("SMA", "WMA", "EMA"):
        L.append(f"\n== {kind} ==")
        rows = []
        for nin, nout in grid:
            rs = [run(kind, nin, nout, a, b) for a, b in R.PER]
            rr = run(kind, nin, nout, *R.REAL, real=True)
            good = all(x[0] >= y[0] - 1e-9 for x, y in zip(rs, base)) and rs[0][1] > -0.5 and rr[0] >= base_r[0] - 1e-9 and rr[1] >= base_r[1] - 0.03
            rows.append(((nin, nout), rs, rr, good))
            L.append(f"  {kind}{nin}/{nout} {'★' if good else ' '} " + " | ".join(f"{c:5.1%}/{m:6.1%}" for c, m, _ in rs)
                     + f" | 真實 {rr[0]:5.1%}/{rr[1]:6.1%} | 年交易 {rs[0][2]:.1f}")
        cs = sorted(x[1][0][0] for x in rows)
        ms = sorted(x[1][0][1] for x in rows)
        summary[kind] = (cs[len(cs) // 2], ms[len(ms) // 2], sum(x[3] for x in rows), len(rows), sum(x[1][0][1] < -0.5 for x in rows))
    L.append("\n== 摘要（全部格點）：全期年化中位、回檔中位、勝現行組數、回檔 > 50% 組數 ==")
    for k, (c, m, g, n, bad) in summary.items():
        L.append(f"  {k}: {c:.1%}、{m:.1%}、{g}/{n}、{bad}")
    rng = random.Random(7)
    paths = [R24.R.path(rng, 250) for _ in range(300)]
    L.append("\n== 拔靴（300 條 20 年，不含融資濾網）：年化中位、P(回檔<-50%)、勝 SMA60/80 比例 ==")
    b0 = boot("SMA", 60, 80, paths)
    for kind, nin, nout in (("SMA", 60, 80), ("WMA", 60, 80), ("EMA", 60, 80), ("WMA", 80, 100), ("WMA", 80, 120), ("EMA", 80, 100), ("EMA", 70, 100), ("WMA", 70, 100)):
        b = b0 if (kind, nin, nout) == ("SMA", 60, 80) else boot(kind, nin, nout, paths)
        cs = sorted(x[0] for x in b)
        win = sum(1 for x, y in zip(b, b0) if x[0] > y[0] + 1e-12) / len(b)
        L.append(f"  {kind}{nin}/{nout}: {cs[150]:.1%}、P {sum(x[1] < -0.5 for x in b) / len(b):.0%}、勝 {win:.0%}")
        print(L[-1], flush=True)
    out = "\n".join(L) + "\n"
    print("\n".join(x for x in L if not x.startswith("  SMA") and not x.startswith("  WMA") and not x.startswith("  EMA") or "★" in x))
    open(os.path.join(HERE, "結果_研究44_加權均線.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
