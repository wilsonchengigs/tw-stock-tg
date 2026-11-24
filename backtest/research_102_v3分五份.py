"""研究 102：v3 資金分 5 份、週一～週五各自判斷（去掉判斷日運氣），當作期望值參考
用法：python -X utf8 backtest/research_102_v3分五份.py
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r101", os.path.join(HERE, "research_101_v3判斷日.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
V = R.V


def blended(start, end, real=False):
    orig = V.WE
    curves = []
    for k in range(1, 6):
        V.WE = R.flags(k) if k < 5 else orig
        curves.append(V.run(start, end, real=real, curve=True)[2])
    V.WE = orig
    n = min(len(c) for c in curves)
    eq = [sum(c[i] for c in curves) / 5 for i in range(n)]
    peak, mdd = eq[0], 0.0
    for x in eq:
        peak = max(peak, x)
        mdd = min(mdd, x / peak - 1)
    return eq[-1] ** (V.bt.TD / (n - 1)) - 1, mdd


def main():
    L = ["研究 102：v3 分 5 份（週一～五各自判斷）"]
    rs = [blended(a, b) for a, b in V.PER]
    rr = blended(*V.REAL, real=True)
    L.append("分 5 份  " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in rs) + f" | 真實 {rr[0]:.1%}/{rr[1]:.1%}")
    L.append("只週五   " + V.fmt())
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究102_v3分五份.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
