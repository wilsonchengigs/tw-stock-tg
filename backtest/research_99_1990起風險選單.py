"""研究 99：1990～2026 全期風險選單（核心均線規則，無融資濾網；固定槓桿 1／1.25／1.5／1.75／2x，與長抱比較）
用法：python -X utf8 backtest/research_99_1990起風險選單.py
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r98", os.path.join(HERE, "research_98_極端波動降槓桿.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
D, P, N, WE, R1, RC, TD = R.D, R.P, R.N, R.WE, R.R1, R.RC, R.TD


def run(lev, start, end, hold=False):
    i0 = next(i for i, d in enumerate(D) if d >= start and R.M80[i] is not None and i >= 130)
    i1 = max(i for i, d in enumerate(D) if d <= end)
    eq = peak = 1.0
    mdd, on, cur, pend = 0.0, False, 0.0, None
    for i in range(i0, i1 + 1):
        if i > i0:
            L_ = lev if hold else cur
            eq *= 1 + ((L_ * R1[i] - max(L_ - 1, 0) * 0.01 / TD) if L_ > 0 else RC)
        if pend is not None:
            eq *= 1 - 0.0025 * abs(pend - cur)
            cur, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if not hold and WE[i]:
            on = (not P[i] < R.M80[i] * 0.975) if on else (P[i] > R.M60[i] * 1.01)
            t = lev if on else 0.0
            if t != cur:
                pend = t
    yrs = (i1 - i0) / TD
    return eq ** (1 / yrs) - 1, mdd


def main():
    pers = (("1990-01-01", "1997-12-31"), ("1998-01-01", "2026-12-31"), ("1990-01-01", "2026-12-31"))
    L = ["研究 99：1990～2026 風險選單（核心均線規則、無融資濾網；1990-1997 | 1998-2026 | 1990-2026 全期）"]
    for lev in (1.0, 1.25, 1.5, 1.75, 2.0):
        L.append(f"策略 {lev:.2f}x  " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in (run(lev, a, b) for a, b in pers)))
    for lev in (1.0, 2.0):
        L.append(f"長抱 {lev:.0f}x     " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in (run(lev, a, b, hold=True) for a, b in pers)))
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究99_1990起風險選單.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
