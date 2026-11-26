"""研究 205：研究 204 的台美背離訊號當成台指期部位，疊在現行 V+F（研究 141 引擎，2018-06～）上

訊號：加權 20 日報酬 − S&P 20 日報酬 ≤ −x（x＝8／10／12%），D 收盤（13:45，用台指期日盤收）進，抱 H＝5／10 個交易日收盤出；
持有中再觸發不延長（避免一直續抱）；加 u＝0.5／1 倍名目；每邊成本 3 點
家族：3 × 2 × 2＝12 組；背離序列環狀平移 400 次（避開 ±20 天）、最小 p 值法
另：1998～2017 用加權指數（無台指期全期資料）做「單獨帳戶」樣本外：每筆淨報酬與勝率
用法：python -X utf8 backtest/research_205_台美背離台指期部位.py
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


R141 = _load("r141", "research_141_加碼總曝險上限.py")
R204 = _load("r204", "research_204_台美背離補漲.py")
bt = R141.bt
COST = 3.0

tw20 = np.array([R204.TW[k] / R204.TW[k - 20] - 1 if k >= 20 else np.nan for k in range(R204.N)])
us20 = np.array([R204.US[k] / R204.US[k - 20] - 1 if k >= 20 else np.nan for k in range(R204.N)])
GAP = dict(zip(R204.DAYS, tw20 - us20))


def positions(g, x, H, u):
    """g：每個 T 日的背離；回傳每天持有的倍數（當天收盤→收盤報酬適用前一天收盤時的部位）"""
    n = len(g)
    pos = np.zeros(n)
    k = 0
    while k < n:
        if g[k] <= -x:
            pos[k + 1:k + 1 + H] = u  # D 收盤進 → D+1..D+H 的收對收報酬
            k += H + 1
        else:
            k += 1
    return pos


def main():
    S = int(os.environ.get("R205_SHIFTS", "400"))
    T = R141.build()
    n = len(T)
    _, _, base_r, _ = R141.run(T)
    g = np.array([GAP.get(t["d"], np.nan) for t in T])
    g = np.nan_to_num(g, nan=0.0)
    rcc = np.array([t["rcc"] for t in T])
    c = np.array([t["c"] for t in T])
    GRID = [(x, H, u) for x in (0.08, 0.10, 0.12) for H in (5, 10) for u in (0.5, 1.0)]

    def one(gg, x, H, u):
        pos = positions(gg, x, H, u)
        prev = np.r_[0.0, pos[:-1]]
        add = pos * rcc
        add -= np.where((pos > 0) & (prev == 0), u * COST / c, 0.0)  # 近似：進出各一次成本
        add -= np.where((prev > 0) & (pos == 0), u * COST / c, 0.0)
        r = base_r + add[1:]
        e = np.cumprod(1 + r)
        trades = int(((pos > 0) & (prev == 0)).sum())
        return e[-1] ** (bt.TD / len(r)) - 1, (e / np.maximum.accumulate(e) - 1).min(), trades, add

    e0 = np.cumprod(1 + base_r)
    c0, m0 = e0[-1] ** (bt.TD / len(base_r)) - 1, (e0 / np.maximum.accumulate(e0) - 1).min()
    real = [one(g, *p) for p in GRID]
    rng = np.random.default_rng(205)
    shifts = rng.integers(20, n - 20, S)
    null = np.array([[one(np.roll(g, s), *p)[0] for p in GRID] for s in shifts])
    realc = np.array([r[0] for r in real])
    single = (1 + (null >= realc).sum(axis=0)) / (S + 1)
    ranks = np.array([[(1 + np.sum(null[:, j] >= null[s, j])) / (S + 1) for j in range(len(GRID))] for s in range(S)])
    minp = ranks.min(axis=1)
    out = [f"研究 205：台美背離 → 台指期 D 收盤進、抱 H 日，疊在現行 V+F 上（{T[0]['d']}～{T[-1]['d']}；平移 {S} 次）",
           f"現行 V+F：{c0:.1%}／{m0:.1%}", ""]
    for j, (x, H, u) in enumerate(GRID):
        cc, mm, k, _ = real[j]
        fam = (1 + np.sum(minp <= single[j])) / (S + 1)
        out.append(f"背離≤-{x:.0%} 抱{H:2d} 加{u}x  {k:2d} 筆  {cc:6.1%}／{mm:6.1%}（{cc - c0:+.2%}）  平移中位 {np.median(null[:, j]) - c0:+.2%}  單組 p {single[j]:.3f}  家族 p {fam:.3f}")
    # 逐筆（10%、5 日、1x）
    pos = positions(g, 0.10, 5, 1.0)
    prev = np.r_[0.0, pos[:-1]]
    starts = np.where((pos > 0) & (prev == 0))[0]
    out.append("\n逐筆（背離≤-10%、抱 5 日、1x，台指期收對收）：")
    for s in starts:
        rr = np.prod(1 + rcc[s:s + 5]) - 1
        out.append(f"  {T[s - 1]['d']} 進 → {rr:+.1%}")
    # 1998～2017 單獨帳戶（加權指數，成本 0.1%）
    D = R204.DAYS
    TW = R204.TW
    gg = tw20 - us20
    res = {}
    for x in (0.08, 0.10, 0.12):
        for H in (5, 10):
            v, k = [], 20
            while k < len(D):
                if D[k] >= "2018-06-01":
                    break
                if gg[k] <= -x and k + H < len(D):
                    v.append(TW[k + H] / TW[k] - 1 - 0.001)
                    k += H + 1
                else:
                    k += 1
            v = np.array(v)
            res[(x, H)] = v
    out.append("\n1998～2018-05 樣本外（加權指數、單獨帳戶、每筆成本 0.1%）：")
    allH = {H: np.array([TW[k + H] / TW[k] - 1 for k in range(20, len(D) - H) if D[k] < "2018-06-01"]) for H in (5, 10)}
    for (x, H), v in res.items():
        out.append(f"  背離≤-{x:.0%} 抱{H:2d}：{len(v)} 筆 每筆 {v.mean():+.2%}（全部日 {allH[H].mean():+.2%}）勝率 {np.mean(v > 0):.0%} 最差 {v.min():+.1%}")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究205_台美背離台指期部位.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
