"""研究 95：保留樣本（holdout）——只用 2002～2012 挑融資濾網參數（偏離門檻 × z × 回補 × 每日／週五），看 2013～2026 與真實價格
同時看「2002～2012 排名」與「2013～2026 排名」的相關（排名相關高＝參數選擇有延續性）
用法：python -X utf8 backtest/research_95_保留樣本.py
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


def rank(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0] * len(xs)
    for k, i in enumerate(order):
        r[i] = k
    return r


def spearman(a, b):
    ra, rb = rank(a), rank(b)
    n = len(a)
    return 1 - 6 * sum((x - y) ** 2 for x, y in zip(ra, rb)) / (n * (n * n - 1))


def main():
    grid = list(itertools.product((0.125, 0.15, 0.175, 0.2, 0.25, None), (1.5, 2.0, 2.5, None), (0.10, 0.125, 0.15), (True, False)))
    res = []
    for th, zt, re_, dh in grid:
        if th is None and zt is None:
            kw = dict(use_heat=False)
        else:
            kw = dict(th=th if th is not None else 9.9, zth=zt, reentry=re_, daily_heat=dh)
        a = V.run("2002-01-01", "2012-12-31", **kw)
        b = V.run("2013-01-01", "2026-12-31", **kw)
        r = V.run(*V.REAL, real=True, **kw)
        res.append(((th, zt, re_, dh), a, b, r))
    L = ["研究 95：保留樣本（只看 2002-2012 挑參數 → 2013-2026、真實 2015-09～）", f"格點 {len(res)} 組"]
    rho = spearman([x[1][0] for x in res], [x[2][0] for x in res])
    L.append(f"前段 vs 後段 年化排名的 Spearman 相關：{rho:+.2f}")
    nofilter = next(x for x in res if x[0][0] is None and x[0][1] is None)
    L.append(f"無融資濾網：前段 {nofilter[1][0]:.1%} → 後段 {nofilter[2][0]:.1%}、真實 {nofilter[3][0]:.1%}")
    v3 = next(x for x in res if x[0] == (0.175, 2.0, 0.125, True))
    L.append(f"v3（17.5%、z2、12.5%、每日）：前段 {v3[1][0]:.1%} → 後段 {v3[2][0]:.1%}、真實 {v3[3][0]:.1%}")
    top = sorted(res, key=lambda x: -x[1][0])
    L.append("\n只看前段挑出的前 10 名，在後段的表現：")
    for p, a, b, r in top[:10]:
        L.append(f"  偏離 {p[0]} z {p[1]} 回補 {p[2]} {'每日' if p[3] else '週五'}：前段 {a[0]:.1%}/{a[1]:.1%} → 後段 {b[0]:.1%}/{b[1]:.1%}、真實 {r[0]:.1%}/{r[1]:.1%}")
    b_all = sorted(x[2][0] for x in res)
    top10_b = sorted(x[2][0] for x in top[:10])
    L.append(f"\n後段年化：全部格點中位 {b_all[len(b_all) // 2]:.1%}；前段前 10 名在後段的中位 {top10_b[5]:.1%}；無濾網 {nofilter[2][0]:.1%}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究95_保留樣本.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
