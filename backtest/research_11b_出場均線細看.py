"""研究 11b：出場均線 MA80～100 細看（是否為穩定高原），以及逐年差異。用法：python -X utf8 backtest/research_11b_出場均線細看.py"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r11", os.path.join(HERE, "research_11_進出場細掃.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
L = ["研究 11b：出場均線細看（全期 | 前段 | 後段 | 真實）"]
for ein, bi in ((60, 1.01), (60, 1.0), (55, 1.005), (65, 1.005)):
    L.append(f"\n進場 MA{ein}x{bi}：")
    for eo in (80, 82, 84, 86, 88, 90, 92, 95, 100, 110, 120):
        for bo in (0.975, 0.98, 0.985):
            r, rr = R.evaluate(R.signals(ein, bi, eo, bo))
            L.append(f"  出 MA{eo}x{bo}  {R.fmt(r, rr)}")


def yearly(sig):
    i0, i1 = R.IDX[R.PER[0]]
    eq, pos, pend, ys = 1.0, False, None, {}
    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + (R.bt.R2[i] if pos else R.bt.RC)
        if pend is not None:
            eq *= 1 - R.bt.COST * 2
            pos, pend = pend, None
        ys[R.DAYS[i][:4]] = eq
        if R.WE[i] and sig[i] != pos:
            pend = sig[i]
    out, prev = {}, 1.0
    for y in sorted(ys):
        out[y], prev = ys[y] / prev - 1, ys[y]
    return out


a = yearly(R.signals(60, 1.01, 80, 0.98))
b = yearly(R.signals(60, 1.01, 90, 0.98))
c = yearly(R.signals(60, 1.0, 90, 0.98))
L.append("\n逐年：現行 | 出場改 MA90x0.98 | 進 MA60x1.0＋出 MA90x0.98")
for y in sorted(a):
    L.append(f"  {y} {a[y]:+7.1%} | {b[y]:+7.1%} | {c[y]:+7.1%}")
out = "\n".join(L) + "\n"
print(out)
open(os.path.join(HERE, "結果_研究11b_出場均線細看.txt"), "w", encoding="utf-8").write(out)
