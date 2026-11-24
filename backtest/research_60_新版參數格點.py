"""研究 60：加入融資濾網後，進出場參數的最佳區域是否改變（進場 MA50～70×1.00～1.02、出場 MA70～90×0.97～0.98）
用法：python -X utf8 backtest/research_60_新版參數格點.py
"""
import importlib.util
import itertools
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r41", os.path.join(HERE, "research_41_總經濾網.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
bt, DAYS, PX, N, WE, HOT = R.bt, R.DAYS, R.PX, R.N, R.WE, R.HOT
RR = R.R40.R32.R


def run(ein, bi, eo, bo, start, end, real=False):
    r2 = RR.R2R if real else bt.R2
    mi, mo = bt.get_sma(ein), bt.get_sma(eo)
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
            on = (not (PX[i] < mo[i] * bo or HOT[i])) if on else (PX[i] > mi[i] * bi and not HOT[i])
            if on != pos:
                pend = on
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd


def main():
    L = ["研究 60：新版（含融資濾網）參數格點（全期 2002- | 前段 | 後段 | 真實）"]
    res = []
    for ein, bi, eo, bo in itertools.product((50, 60, 70), (1.0, 1.01, 1.02), (70, 80, 90), (0.97, 0.975, 0.98)):
        rs = [run(ein, bi, eo, bo, a, b) for a, b in R.PER]
        rr = run(ein, bi, eo, bo, *R.REAL, real=True)
        res.append(((ein, bi, eo, bo), rs, rr))
    base = next(x for x in res if x[0] == (60, 1.01, 80, 0.975))
    better = [x for x in res if all(a[0] >= b[0] - 1e-9 for a, b in zip(x[1], base[1])) and x[2][0] >= base[2][0] - 1e-9 and x[1][0][1] > -0.5]
    L.append(f"現行 MA60x1.01／MA80x0.975：" + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in base[1]) + f" | 真實 {base[2][0]:.1%}")
    cs = sorted(x[1][0][0] for x in res)
    L.append(f"81 組全期中位 {cs[40]:.1%}；現行排名 {sorted(cs, reverse=True).index(base[1][0][0]) + 1}/81；四段都 ≥ 現行的組數 {len(better)}")
    L.append("全期前 10 名：")
    for p, rs, rr in sorted(res, key=lambda x: -x[1][0][0])[:10]:
        L.append(f"  MA{p[0]}x{p[1]}／MA{p[2]}x{p[3]}  " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in rs) + f" | 真實 {rr[0]:.1%}/{rr[1]:.1%}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究60_新版參數格點.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
