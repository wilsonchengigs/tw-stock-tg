"""研究 196：恐慌隔天做多（P）「低波動時不做」的家族檢定（接研究 194 的觀察）

研究 194：訊號日 20 日波動在低三分位時，P 每筆約 0（全期 -0.08%、兩段都 ≤0），中／高波動 +0.55%／+1.21%。
這是事後分組看到的，要先做家族檢定才能列候選：
- 家族：波動回看 10／20／60 日 × 門檻＝過去 3 年（735 天）波動分布的 20／33／40 分位（不偷看未來）＝9 組
- 指標：跳過的那些交易的報酬合計取負（＝避開的損失；>0 代表過濾有幫助），也看留下來的每筆平均
- 安慰劑：把「要跳過」的旗標在 P 交易序列上環狀平移（保留跳過筆數與群聚），所有位移都算；
  每個位移取 9 組中最大的標準化增益，與實際最大值比較＝家族 p（最小 p 值法，研究 129／130）
- 兩段：1998～2017-05（只有 S&P 觸發）、2017-05～（夜盤＋S&P）
用法：python -X utf8 backtest/research_196_P低波動不做家族檢定.py
"""
import importlib.util
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r148", os.path.join(HERE, "research_148_恐慌連續觸發.py"))
R148 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R148)


def main():
    rows = R148.build()
    n = len(rows)
    cc = np.array([0.0] + [rows[k]["c"] / rows[k - 1]["c"] - 1 for k in range(1, n)])
    sig = np.array([x["sig"] for x in rows])
    r = np.array([x["r"] for x in rows])
    dates = np.array([x["d"] for x in rows])
    L = ["研究 196：P 低波動不做 家族檢定（9 組；環狀平移全部位移；跳過＝訊號日 lb 日波動 < 過去 735 天的 q 分位）"]
    variants = [(lb, q) for lb in (10, 20, 60) for q in (20, 33, 40)]
    for seg, lo, hi in (("全期", "1998", "2099"), ("1998～2017-05", "1998", "2017-05-15"), ("2017-05～", "2017-05-15", "2099")):
        idx = np.where(sig & (dates >= lo) & (dates < hi))[0]
        idx = idx[idx > 800]
        rr = r[idx]
        skips = {}
        for lb, q in variants:
            vol = np.array([np.std(cc[max(1, k - lb):k]) for k in range(n)])
            sk = np.array([vol[k] < np.percentile(vol[k - 735:k], q) for k in idx])
            skips[(lb, q)] = sk
        m = len(idx)

        def gains(shift):
            out = {}
            for v, sk in skips.items():
                s2 = np.roll(sk, shift)
                out[v] = -rr[s2].sum()
            return out

        real = gains(0)
        allg = {v: np.array([gains(s)[v] for s in range(1, m)]) for v in variants}
        mu = {v: allg[v].mean() for v in variants}
        sd = {v: allg[v].std() or 1e-9 for v in variants}
        zmax_null = np.array([max((allg[v][s] - mu[v]) / sd[v] for v in variants) for s in range(m - 1)])
        L.append(f"\n【{seg}】P {m} 筆、每筆 {rr.mean():+.2%}、合計 {rr.sum():+.1%}")
        for v in variants:
            sk = skips[v]
            z = (real[v] - mu[v]) / sd[v]
            p1 = np.mean(allg[v] >= real[v])
            pf = np.mean(zmax_null >= z)
            kept = rr[~sk]
            L.append(f"  回看 {v[0]:>2} 日、{v[1]} 分位：跳過 {sk.sum():>3} 筆（{sk.mean():.0%}）、跳過的每筆 {rr[sk].mean() if sk.any() else 0:+.2%}、"
                     f"留下每筆 {kept.mean():+.2%}、避開合計 {real[v]:+.1%}｜單組 p {p1:.3f}、家族 p {pf:.3f}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究196_P低波動不做家族檢定.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
