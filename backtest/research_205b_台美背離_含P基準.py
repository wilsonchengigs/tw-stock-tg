"""研究 205b：研究 205 的台美背離台指期部位（D），基準改成現行全部上線規則 V+F+P（P 1x，研究 170）
看 D 跟 P 重不重疊、加 D 後最高曝險與最差單日；家族同 205（背離序列環狀平移 400 次、12 組）
用法：python -X utf8 backtest/research_205b_台美背離_含P基準.py
"""
import importlib.util
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


R152 = _load("r152", "research_152_全部加碼疊加風險.py")
R205 = _load("r205", "research_205_台美背離台指期部位.py")
R141, R142, R145, bt = R152.R141, R152.R142, R152.R145, R152.bt
COST = 3.0


def main():
    S = 400
    T = R141.build()
    n = len(T)
    vf_r, fo = R152.run_vf(T)
    vf_units = np.array([x[0] for x in fo])
    base_units = np.array([b for _, b in fo])
    NN, SP = R142.night_series(T), R145.sp_series(T)
    o = np.array([t["o"] for t in T])
    c = np.array([t["c"] for t in T])
    rcc = np.array([t["rcc"] for t in T])
    roc, gap = c / o - 1, np.r_[0.0, o[1:] / c[:-1] - 1]
    psig = (NN <= -0.02) | (SP <= -0.02)
    pu = np.where(psig, 1.0, 0.0)
    pug = np.r_[0.0, pu[:-1]]
    padd = (pug * gap + pu * roc - np.abs(pu - pug) * COST / o)[1:]
    base_r = vf_r + padd
    e0 = np.cumprod(1 + base_r)
    c0, m0 = e0[-1] ** (bt.TD / len(base_r)) - 1, (e0 / np.maximum.accumulate(e0) - 1).min()
    g = np.nan_to_num(np.array([R205.GAP.get(t["d"], np.nan) for t in T]), nan=0.0)
    GRID = [(x, H, u) for x in (0.08, 0.10, 0.12) for H in (5, 10) for u in (0.5, 1.0)]

    def one(gg, x, H, u, detail=False):
        pos = R205.positions(gg, x, H, u)
        prev = np.r_[0.0, pos[:-1]]
        add = pos * rcc - np.where((pos > 0) & (prev == 0), u * COST / c, 0) - np.where((prev > 0) & (pos == 0), u * COST / c, 0)
        r = base_r + add[1:]
        e = np.cumprod(1 + r)
        cg, mdd = e[-1] ** (bt.TD / len(r)) - 1, (e / np.maximum.accumulate(e) - 1).min()
        if not detail:
            return cg
        expo = base_units + vf_units + pu[1:] + pos[1:]
        return cg, mdd, r.min(), expo.max(), int(((pos > 0) & (prev == 0)).sum()), pos

    real = np.array([one(g, *p) for p in GRID])
    rng = np.random.default_rng(2052)
    shifts = rng.integers(20, n - 20, S)
    null = np.array([[one(np.roll(g, s), *p) for p in GRID] for s in shifts])
    single = (1 + (null >= real).sum(axis=0)) / (S + 1)
    ranks = np.array([[(1 + np.sum(null[:, j] >= null[s, j])) / (S + 1) for j in range(len(GRID))] for s in range(S)])
    minp = ranks.min(axis=1)
    e1 = np.cumprod(1 + vf_r)
    out = [f"研究 205b：基準＝V+F+P(1x)（{T[0]['d']}～{T[-1]['d']}）",
           f"V+F：{e1[-1] ** (bt.TD / len(vf_r)) - 1:.1%}；V+F+P：{c0:.1%}／{m0:.1%}、最差單日 {base_r.min():+.1%}", ""]
    for j, p in enumerate(GRID):
        cg, mdd, worst, mx, k, pos = one(g, *p, detail=True)
        fam = (1 + np.sum(minp <= single[j])) / (S + 1)
        ov = int(((pos[1:] > 0) & (pu[1:] > 0)).sum())
        out.append(f"背離≤-{p[0]:.0%} 抱{p[1]:2d} 加{p[2]}x {k:2d} 筆 {cg:6.1%}／{mdd:6.1%}（{cg - c0:+.2%}）最差單日 {worst:+.1%} 最高曝險 {mx:.1f}x 與 P 同天 {ov} 天  單組 p {single[j]:.3f} 家族 p {fam:.3f}")
    yrs = np.array([t["d"][:4] for t in T])[1:]
    _, _, _, _, _, pos = one(g, 0.10, 5, 1.0, detail=True)
    prev = np.r_[0.0, pos[:-1]]
    add = (pos * rcc - np.where((pos > 0) & (prev == 0), COST / c, 0) - np.where((prev > 0) & (pos == 0), COST / c, 0))[1:]
    out.append("\n背離≤-10% 抱 5 加 1x 逐年增量：" + "  ".join(f"{y}:{add[yrs == y].sum():+.1%}" for y in sorted(set(yrs))))
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究205b_台美背離_含P基準.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
