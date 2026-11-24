"""研究 64e：在場時爆量收黑加碼（研究 64b）的鄰近參數穩定度
k 1.4／1.5／1.6／1.7／1.8 × H 3／5／7／10／15 × 加碼 0.5／1.0；看三段年化是否都勝現行、最大回檔加深幅度
用法：python -X utf8 backtest/research_64e_在場加碼鄰近參數.py
"""
import importlib.util
import itertools
import os

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("r64b", os.path.join(HERE, "research_64b_在場時爆量收黑加碼.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
P = (("2002-01-01", "2026-12-31"), ("2002-01-01", "2012-12-31"), ("2013-01-01", "2026-12-31"))


def main():
    base = [m.sim(s, e) for s, e in P]
    L = ["研究 64e：在場加碼鄰近參數（每格：全期年化差／最大回檔差；✓＝三段年化都勝現行且回檔加深 ≤3 點）",
         "現行：" + "  ".join(f"{c:.1%}/{d:.1%}" for c, d, _a in base)]
    ok = tot = 0
    for add in (0.5, 1.0):
        L.append(f"\n加碼 {add}x：")
        L.append("k \ H   " + "".join(f"{h:>16d}" for h in (3, 5, 7, 10, 15)))
        for k in (1.4, 1.5, 1.6, 1.7, 1.8):
            cells = []
            for H in (3, 5, 7, 10, 15):
                res = [m.sim(s, e, k, add, H) for s, e in P]
                good = all(r[0] > b[0] for r, b in zip(res, base)) and res[0][1] >= base[0][1] - 0.03
                ok += good
                tot += 1
                cells.append(f"{res[0][0] - base[0][0]:+.1%}/{res[0][1] - base[0][1]:+.1%}{'✓' if good else ' '}".rjust(16))
            L.append(f"{k:.1f}    " + "".join(cells))
    L.append(f"\n通過：{ok}/{tot}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究64e_在場加碼鄰近參數.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
