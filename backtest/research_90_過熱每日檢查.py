"""研究 90：融資過熱改成每天檢查（過熱當天就決定隔天出場），價格進出場仍每週五
v3 基準；另試「過熱每日檢查，但回補仍週五」
用法：python -X utf8 backtest/research_90_過熱每日檢查.py
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("v3", os.path.join(HERE, "strategy_v3.py"))
V = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V)
bt, DAYS, PX, N, WE = V.bt, V.DAYS, V.PX, V.N, V.WE


def run(start, end, daily_heat=False, real=False, log=None):
    r2 = V.R2R if real else bt.R2
    i0 = next(i for i, x in enumerate(DAYS) if x >= start)
    i1 = max(i for i, x in enumerate(DAYS) if x <= end)
    eq = peak = 1.0
    mdd, st, heat_out, pos, pend = 0.0, 0, False, False, None
    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + (r2[i] if pos else bt.RC)
        if pend is not None:
            eq *= 1 - bt.COST * 2
            pos, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if i < 260:
            continue
        hot = V.hot_at(i)
        if daily_heat and st == 1 and hot and not WE[i]:
            st, heat_out = 0, True
            if log is not None:
                log.append((DAYS[i], "盤中週過熱出", round(PX[i])))
        if WE[i]:
            p = PX[i]
            above = p >= V.M80[i] * 0.975
            if st == 0:
                if heat_out and not above:
                    heat_out = False
                cooled = V.DEV[i] is None or (V.DEV[i] < 0.125 and V.Z[i] <= 2.0)
                if (p > V.M60[i] * 1.01 and not hot) or (heat_out and cooled and above):
                    st, heat_out = 1, False
            elif hot:
                st, heat_out = 0, True
            elif not above:
                st, heat_out = 0, False
        if (st == 1) != pos and pend is None:
            pend = st == 1
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd


def main():
    L = ["研究 90：融資過熱每日檢查（全期 2002- | 前段 | 後段 | 真實）"]
    for nm, kw in (("v3（週五檢查）", {}), ("過熱每日檢查", dict(daily_heat=True))):
        rs = [run(a, b, **kw) for a, b in V.PER]
        rr = run(*V.REAL, real=True, **kw)
        L.append(f"{nm:14s} " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in rs) + f" | 真實 {rr[0]:.1%}/{rr[1]:.1%}")
    log = []
    run("2020-01-01", "2026-12-31", daily_heat=True, log=log)
    L.append("2020 起每日檢查額外觸發：" + "、".join(f"{d} {x} {p}" for d, x, p in log))
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究90_過熱每日檢查.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
