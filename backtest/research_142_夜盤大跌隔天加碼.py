"""研究 142：研究 139 的「夜盤跌 ≥x% → 隔天日盤開盤做多、收盤平倉」放進現行 V+F 加碼之上，看增量與家族檢定

訊號：交易日 D 的夜盤（D-1 15:00→D 05:00）近月 開→收 ≤ −x；D 08:45 開盤買台指期 u 倍、13:45 收盤平；成本來回 3 點
條件：(a) 不管 v3 狀態 (b) 只在 v3 在場（前一天收盤狀態）
家族：x 1.5／2／2.5／3% × u 0.5／1 × (a)(b) ＝ 16 組；虛無：夜盤報酬序列環狀平移 400 次（避開 ±20 天），最小 p 值法
比較基準：研究 141 的現行 V+F（2018-06～，00631L＋台指期真實價）
用法：python -X utf8 backtest/research_142_夜盤大跌隔天加碼.py （R142_SHIFTS 控制平移次數）
"""
import importlib.util
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r141", os.path.join(HERE, "research_141_加碼總曝險上限.py"))
R141 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R141)
bt = R141.bt


def night_series(T):
    dates, day, night, near = R141.R139.load_tx()
    di = {d: k for k, d in enumerate(dates)}
    out = []
    for t in T:
        k = di[t["d"]]
        m = near[dates[k - 1]]
        nb = night[t["d"]].get(m)
        out.append(nb[3] / nb[0] - 1 if nb and nb[4] >= 1000 else 0.0)
    return np.array(out)


def main():
    S = int(os.environ.get("R142_SHIFTS", "400"))
    T = R141.build()
    n = len(T)
    _, _, base_r, _ = R141.run(T)  # 現行 V+F；base_r[k-1] 對應 T[k]
    NN = night_series(T)
    roc = np.array([t["roc"] for t in T])
    o = np.array([t["o"] for t in T])
    on_prev = np.array([0] + [T[k - 1]["st"] for k in range(1, n)]) == 1
    GRID = [(x, u, only) for x in (0.015, 0.02, 0.025, 0.03) for u in (0.5, 1.0) for only in (False, True)]

    def stats(nn):
        res = []
        for x, u, only in GRID:
            sig = (nn <= -x) & (on_prev if only else True)
            add = np.where(sig, u * (roc - 3.0 / o), 0.0)[1:]
            r = base_r + add
            e = np.cumprod(1 + r)
            res.append((e[-1] ** (bt.TD / len(r)) - 1, (e / np.maximum.accumulate(e) - 1).min(), int(sig.sum())))
        return res

    real = stats(NN)
    e0 = np.cumprod(1 + base_r)
    c0 = e0[-1] ** (bt.TD / len(base_r)) - 1
    m0 = (e0 / np.maximum.accumulate(e0) - 1).min()
    rng = np.random.default_rng(142)
    shifts = rng.integers(20, n - 20, S)
    null = np.array([[c for c, _, _ in stats(np.roll(NN, s))] for s in shifts])  # S × K
    realc = np.array([c for c, _, _ in real])
    single = (1 + (null >= realc).sum(axis=0)) / (S + 1)
    ranks = np.array([[(1 + np.sum(null[:, j] >= null[s, j])) / (S + 1) for j in range(len(GRID))] for s in range(S)])
    minp = ranks.min(axis=1)
    out = [f"研究 142：夜盤大跌隔天日盤加碼 疊在現行 V+F 之上（{T[0]['d']}～{T[-1]['d']}；平移 {S} 次）",
           f"現行 V+F：{c0:.1%}／{m0:.1%}", ""]
    for j, (x, u, only) in enumerate(GRID):
        c, m, k = real[j]
        fam = (1 + np.sum(minp <= single[j])) / (S + 1)
        out.append(f"夜跌≥{x:.1%} 加{u}x {'只在場' if only else '不分  '}  {k:3d} 次  {c:6.1%}／{m:6.1%}（{c - c0:+.2%}）  "
                   f"平移中位 {np.median(null[:, j]) - c0:+.2%}  單組 p {single[j]:.3f}  家族 p {fam:.3f}")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究142_夜盤大跌隔天加碼.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()


def vol_placebo():
    """同波動度對照：訊號日 vs 前 20 日實現波動落在同一十分位、但夜盤沒有大跌（> −1%）的日子，比隔天日盤 開→收"""
    T = R141.build()
    NN = night_series(T)
    roc = np.array([t["roc"] for t in T])
    rcc = np.array([t["rcc"] for t in T])
    vol = np.array([np.std(rcc[max(1, k - 20):k]) if k > 5 else np.nan for k in range(len(T))])
    ok = ~np.isnan(vol)
    qs = np.nanpercentile(vol, np.arange(10, 100, 10))
    dec = np.digitize(vol, qs)
    out = ["", "== 同波動度對照（前 20 日實現波動十分位相同、夜盤 > −1% 的日子）=="]
    rng = np.random.default_rng(1421)
    for x in (0.015, 0.02, 0.025, 0.03):
        sig = ok & (NN <= -x)
        ctrl = ok & (NN > -0.01)
        diffs, nulls = [], []
        for k in np.where(sig)[0]:
            pool = np.where(ctrl & (dec == dec[k]))[0]
            diffs.append(roc[k] - roc[pool].mean())
        # 虛無：從同十分位對照日抽一天當假訊號，看差的分布
        for _ in range(2000):
            nulls.append(np.mean([roc[rng.choice(np.where(ctrl & (dec == dec[k]))[0])] - roc[np.where(ctrl & (dec == dec[k]))[0]].mean() for k in np.where(sig)[0]]))
        pv = (1 + np.sum(np.array(nulls) >= np.mean(diffs))) / 2001
        up = ok & (NN >= x)
        out.append(f"夜跌≥{x:.1%} {sig.sum():3d} 次：隔天日盤 {roc[sig].mean():+.3%}，同波動對照 {np.mean([roc[k] for k in np.where(sig)[0]]) - np.mean(diffs):+.3%}，"
                   f"差 {np.mean(diffs):+.3%}（p {pv:.3f}）｜反向：夜漲≥{x:.1%} {up.sum()} 次 隔天日盤 {roc[up].mean():+.3%}")
    return out


if __name__ == "__main__" and os.environ.get("R142_PLACEBO"):
    txt = "\n".join(vol_placebo())
    print(txt)
    open(os.path.join(HERE, "結果_研究142_夜盤大跌隔天加碼.txt"), "a", encoding="utf-8").write(txt + "\n")
