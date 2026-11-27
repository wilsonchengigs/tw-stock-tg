"""研究 297：漲停家數多的大漲日 → 之後的加權（研究 296 的反面）

漲停判定同研究 296（2015-06 前 7%、之後 10%；4 碼普通股）。事件＝加權當日 ≥+2%。
問題：急漲日裡「漲停家數多」（全面噴出）是續漲還是過熱回吐？
做法：依漲停比例中位切兩組比較 5／20 日；迴歸 fwd ~ 同日報酬＋漲停比例＋RV20；去叢集（5 日內只留第一天）
另列漲停比例最高的日子（含 2026-11-24）
用法：python -X utf8 backtest/research_297_漲停家數.py
"""
import importlib.util
import math
import os
import statistics
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r296", os.path.join(HERE, "research_296_跌停家數.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
D, P = R.s.DAYS, R.s.PX
HS = (5, 20)


def main():
    LD = R.load_ld()
    idx = {d: i for i, d in enumerate(D)}
    rows = []
    for d, (ld, lu, n) in LD.items():
        i = idx.get(d)
        if i is None or i < 22:
            continue
        r = P[i] / P[i - 1] - 1
        if r < 0.02:
            continue
        rv = statistics.pstdev([math.log(P[k] / P[k - 1]) for k in range(i - 20, i)]) * math.sqrt(252) * 100
        f = {h: ((P[i + h] / P[i] - 1) * 100 if i + h < len(P) else None) for h in HS}
        rows.append((d, i, lu * 100, r * 100, rv, f))
    rows.sort()
    out = [f"研究 297：加權 ≥+2% 的大漲日 {len(rows)} 天（{rows[0][0]}～{rows[-1][0]}）\n"]
    out.append("漲停比例最高的 12 天：")
    for x in sorted(rows, key=lambda x: -x[2])[:12]:
        out.append(f"  {x[0]}  漲停 {x[2]:4.1f}%  加權 {x[3]:+5.1f}%  RV20 {x[4]:4.0f}%  " +
                   "  ".join(f"{h}日 {x[5][h]:+5.1f}%" if x[5][h] is not None else f"{h}日 —" for h in HS))
    for h in HS:
        g = [x for x in rows if x[5][h] is not None]
        med = statistics.median(x[2] for x in g)
        hi = [x for x in g if x[2] > med]
        lo = [x for x in g if x[2] <= med]
        out.append(f"\n{h} 日（{len(g)} 天，漲停比例中位 {med:.1f}%）：漲停多 {statistics.mean(x[5][h] for x in hi):+.2f}%（勝 {sum(x[5][h] > 0 for x in hi) / len(hi) * 100:.0f}%）"
                   f"｜漲停少 {statistics.mean(x[5][h] for x in lo):+.2f}%（勝 {sum(x[5][h] > 0 for x in lo) / len(lo) * 100:.0f}%）")
        for lab, sel in (("全部", g), ("去叢集", None)):
            if sel is None:
                sel, last = [], -99
                for x in g:
                    if x[1] - last > 5:
                        sel.append(x)
                        last = x[1]
            X = np.array([[1, x[3], x[2], x[4]] for x in sel])
            y = np.array([x[5][h] for x in sel])
            b, *_ = np.linalg.lstsq(X, y, rcond=None)
            res = y - X @ b
            se = np.sqrt(np.diag(res @ res / (len(y) - 4) * np.linalg.inv(X.T @ X)))
            out.append(f"  迴歸（{lab} {len(sel)} 天）：漲停比例 {b[2]:+.3f}（t {b[2] / se[2]:+.2f}）、同日漲幅 t {b[1] / se[1]:+.2f}、RV20 t {b[3] / se[3]:+.2f}")
    text = "\n".join(out)
    print(text)
    open(os.path.join(HERE, "結果_研究297_漲停家數.txt"), "w", encoding="utf-8").write(text + "\n")


if __name__ == "__main__":
    main()
