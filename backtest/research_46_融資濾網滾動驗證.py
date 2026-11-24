"""研究 46：融資過熱濾網的滾動（walk-forward）驗證
每年初只用過去 L 年（或全部過去）資料，從 n∈{120,250,500} × y∈{10,12.5,15,17.5,20,25%} ＋「不用濾網」中挑年化最高者，套用當年。
串起來的樣本外績效 vs 固定新版（250、17.5%）vs 不用濾網
用法：python -X utf8 backtest/research_46_融資濾網滾動驗證.py
"""
import importlib.util
import itertools
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r38", os.path.join(HERE, "research_38_融資過熱安慰劑.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
R3, N = R.R, R.N
bt = R3.bt
DAYS, PX, WE = bt.DAYS, bt.PX, bt.WEEK_END
M60, M80 = bt.get_sma(60), bt.get_sma(80)
CANDS = [None] + list(itertools.product((120, 250, 500), (0.10, 0.125, 0.15, 0.175, 0.20, 0.25)))


def hot_arr(c):
    if c is None:
        return [False] * N
    n, y = c
    return [i >= n and (v := R3.ratio_dev(i, n)) is not None and v > y for i in range(N)]


HOT = {c: hot_arr(c) for c in CANDS}


def daily_eq(hot):
    eq, on, pos, pend, out = 1.0, False, False, None, [1.0]
    for i in range(1, N):
        eq *= 1 + (bt.R2[i] if pos else bt.RC)
        if pend is not None:
            eq *= 1 - bt.COST * 2
            pos, pend = pend, None
        if WE[i] and i >= 260:
            on = (not (PX[i] < M80[i] * 0.975 or hot[i])) if on else (PX[i] > M60[i] * 1.01 and not hot[i])
            if on != pos:
                pend = on
        out.append(eq)
    return out


EQ = {c: daily_eq(HOT[c]) for c in CANDS}
YI = {}
for i, d in enumerate(DAYS):
    YI.setdefault(d[:4], [i, i])[1] = i


def cagr(eq, a, b):
    return (eq[b] / eq[a]) ** (bt.TD / max(b - a, 1)) - 1


def walk(lb):
    chosen, eq, peak, mdd, series = {}, 1.0, 1.0, 0.0, {}
    for y in range(2006, 2027):
        ys = str(y)
        if ys not in YI:
            continue
        a0 = YI[str(max(2002, y - lb))][0] if lb else YI["2002"][0]
        b0 = YI[ys][0] - 1
        best = max(CANDS, key=lambda c: cagr(EQ[c], a0, b0))
        chosen[ys] = best
        a, b = YI[ys]
        e = EQ[best]
        for i in range(a, b + 1):
            eq *= e[i] / e[i - 1]
            peak = max(peak, eq)
            mdd = min(mdd, eq / peak - 1)
        series[ys] = eq
    n_years = len(series)
    return chosen, eq ** (1 / n_years) - 1, mdd


def fixed(c):
    a, b = YI["2006"][0], YI["2026"][1]
    e = EQ[c]
    peak, mdd = e[a - 1], 0.0
    for i in range(a, b + 1):
        peak = max(peak, e[i])
        mdd = min(mdd, e[i] / peak - 1)
    return (e[b] / e[a - 1]) ** (1 / 21) - 1, mdd


def main():
    L = ["研究 46：融資過熱濾網滾動驗證（樣本外 2006～2026）"]
    for nm, c in (("不用濾網", None), ("固定新版 n=250 y=17.5%", (250, 0.175)), ("固定 n=250 y=15%", (250, 0.15)), ("固定 n=500 y=17.5%", (500, 0.175))):
        c_, m_ = fixed(c)
        L.append(f"{nm:24s} {c_:.1%}／{m_:.1%}")
    for lb in (4, 6, 8, 0):
        ch, c_, m_ = walk(lb)
        used = sum(1 for v in ch.values() if v is not None)
        L.append(f"滾動（回看 {'全部過去' if lb == 0 else f'{lb} 年'}）：{c_:.1%}／{m_:.1%}；21 年中有 {used} 年選了某個濾網")
        L.append("   " + "、".join(f"{y}:{'無' if v is None else f'{v[0]}/{v[1]:.1%}'}" for y, v in ch.items()))
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究46_融資濾網滾動驗證.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
