"""研究 91：在 v3（融資過熱每天檢查）之下，其他規則要不要也每天判斷
A 價格出場（< MA80×0.975）每天檢查；B 過熱後回補每天判斷；C 進場（> MA60×1.01）每天判斷；以及組合
全期 2002- | 前段 | 後段 | 真實；年交易次數
用法：python -X utf8 backtest/research_91_其他規則每日.py
"""
import importlib.util
import itertools
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("v3", os.path.join(HERE, "strategy_v3.py"))
V = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V)
bt, DAYS, PX, N, WE = V.bt, V.DAYS, V.PX, V.N, V.WE


def run(start, end, d_exit=False, d_reent=False, d_entry=False, real=False):
    r2 = V.R2R if real else bt.R2
    i0 = next(i for i, x in enumerate(DAYS) if x >= start)
    i1 = max(i for i, x in enumerate(DAYS) if x <= end)
    eq = peak = 1.0
    mdd, st, heat_out, pos, pend, tr = 0.0, 0, False, False, None, 0
    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + (r2[i] if pos else bt.RC)
        if pend is not None:
            eq *= 1 - bt.COST * 2
            pos, pend = pend, None
            tr += 1
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if i < 260:
            continue
        hot = V.hot_at(i)
        p = PX[i]
        above = p >= V.M80[i] * 0.975
        wk = WE[i]
        if st == 1:
            if hot:
                st, heat_out = 0, True
            elif not above and (wk or d_exit):
                st, heat_out = 0, False
        else:
            if heat_out and not above and (wk or d_reent):
                heat_out = False
            cooled = V.DEV[i] is None or (V.DEV[i] < 0.125 and V.Z[i] <= 2.0)
            if (wk or d_entry) and p > V.M60[i] * 1.01 and not hot:
                st, heat_out = 1, False
            elif (wk or d_reent) and heat_out and cooled and above:
                st, heat_out = 1, False
        if (st == 1) != pos and pend is None:
            pend = st == 1
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd, tr / yrs


def main():
    L = ["研究 91：v3 下其他規則改每天（全期 2002- | 前段 | 後段 | 真實 | 年交易）"]
    for a, b, c in itertools.product((False, True), repeat=3):
        nm = "v3（只有過熱每天）" if not (a or b or c) else "＋".join(x for x, f in (("出場每天", a), ("回補每天", b), ("進場每天", c)) if f)
        rs = [run(s, e, a, b, c) for s, e in V.PER]
        rr = run(*V.REAL, a, b, c, real=True)
        L.append(f"{nm:20s} " + " | ".join(f"{x[0]:.1%}/{x[1]:.1%}" for x in rs) + f" | 真實 {rr[0]:.1%}/{rr[1]:.1%} | {rs[0][2]:.1f} 次/年")
        print(L[-1], flush=True)
    open(os.path.join(HERE, "結果_研究91_其他規則每日.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
