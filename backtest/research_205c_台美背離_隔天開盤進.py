"""研究 205c：研究 205b 的台美背離部位改成實際做得到的進場時點——D 晚上 21:30 日報才知道 → D+1 08:45 開盤進
抱到 D+H 收盤（H＝5／10），基準 V+F+P(1x)；比較 D 收盤進（205b）、D 15:00 夜盤開盤進（近似用 D 收盤，14:40 提醒）、D+1 開盤進
家族：門檻 3 × H 2 × u 2 ＝ 12 組 只換進場方式；平移 400 次
用法：python -X utf8 backtest/research_205c_台美背離_隔天開盤進.py
"""
import importlib.util
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r205b", os.path.join(HERE, "research_205b_台美背離_含P基準.py"))
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)
COST = 3.0


def main():
    T = B.R141.build()
    n = len(T)
    vf_r, fo = B.R152.run_vf(T)
    NN, SP = B.R142.night_series(T), B.R145.sp_series(T)
    o = np.array([t["o"] for t in T])
    c = np.array([t["c"] for t in T])
    rcc = np.array([t["rcc"] for t in T])
    roc, gap = c / o - 1, np.r_[0.0, o[1:] / c[:-1] - 1]
    psig = (NN <= -0.02) | (SP <= -0.02)
    pu = np.where(psig, 1.0, 0.0)
    pug = np.r_[0.0, pu[:-1]]
    base_r = vf_r + (pug * gap + pu * roc - np.abs(pu - pug) * COST / o)[1:]
    e0 = np.cumprod(1 + base_r)
    c0 = e0[-1] ** (B.bt.TD / len(base_r)) - 1
    g = np.nan_to_num(np.array([B.R205.GAP.get(t["d"], np.nan) for t in T]), nan=0.0)

    def add_series(gg, x, H, u):
        """D+1 開盤進：D+1 只吃 roc，D+2..D+H 吃 rcc，D+H 收盤出"""
        add = np.zeros(n)
        k, trades = 0, []
        while k < n:
            if gg[k] <= -x and k + 1 < n:
                add[k + 1] += u * roc[k + 1] - u * COST / o[k + 1]
                end = min(n - 1, k + H)
                for j in range(k + 2, end + 1):
                    add[j] += u * rcc[j]
                add[end] -= u * COST / c[end]
                trades.append((k, c[end] / o[k + 1] - 1))
                k = end + 1
            else:
                k += 1
        return add, trades

    GRID = [(x, H, u) for x in (0.08, 0.10, 0.12) for H in (5, 10) for u in (0.5, 1.0)]

    def cagr(add):
        r = base_r + add[1:]
        e = np.cumprod(1 + r)
        return e[-1] ** (B.bt.TD / len(r)) - 1, (e / np.maximum.accumulate(e) - 1).min()

    real = np.array([cagr(add_series(g, *p)[0])[0] for p in GRID])
    rng = np.random.default_rng(2053)
    shifts = rng.integers(20, n - 20, 400)
    null = np.array([[cagr(add_series(np.roll(g, s), *p)[0])[0] for p in GRID] for s in shifts])
    single = (1 + (null >= real).sum(axis=0)) / 401
    ranks = np.array([[(1 + np.sum(null[:, j] >= null[s, j])) / 401 for j in range(len(GRID))] for s in range(400)])
    minp = ranks.min(axis=1)
    out = [f"研究 205c：D+1 08:45 開盤進、抱到 D+H 收盤；基準 V+F+P(1x) {c0:.1%}（{T[0]['d']}～{T[-1]['d']}）", ""]
    for j, p in enumerate(GRID):
        add, tr = add_series(g, *p)
        cg, mdd = cagr(add)
        fam = (1 + np.sum(minp <= single[j])) / 401
        v = np.array([r for _, r in tr])
        out.append(f"背離≤-{p[0]:.0%} 抱{p[1]:2d} 加{p[2]}x {len(tr):2d} 筆 每筆 {v.mean():+.2%} 勝率 {np.mean(v > 0):.0%}  {cg:6.1%}／{mdd:6.1%}（{cg - c0:+.2%}） 單組 p {single[j]:.3f} 家族 p {fam:.3f}")
    _, tr = add_series(g, 0.10, 5, 0.5)
    out.append("\n逐筆（≤-10%、D+1 開→D+5 收，台指期）：" + "、".join(f"{T[k]['d']} {r:+.1%}" for k, r in tr))
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究205c_台美背離_隔天開盤進.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
