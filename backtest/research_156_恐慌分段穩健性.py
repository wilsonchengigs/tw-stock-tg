"""研究 156：候選 6（已上線）分段穩健性——研究 155 的教訓：全期顯著可能只靠早期少數事件

規則：夜盤或 S&P 跌 ≥2% → D 開盤做多、D+1 開盤出（扣 3 點）；1998～2026 每 4～5 年一段，同波動度對照 2000 次
另列：去掉每段最好 3 筆後的平均
用法：python -X utf8 backtest/research_156_恐慌分段穩健性.py
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
SEGS = [("1998", "2003"), ("2003", "2008"), ("2008", "2012"), ("2012", "2017-05-15"), ("2017-05-15", "2022"), ("2022", "2099")]


def main():
    rows = R148.build()
    n = len(rows)
    cc = np.array([0.0] + [rows[k]["c"] / rows[k - 1]["c"] - 1 for k in range(1, n)])
    vol = np.array([np.std(cc[max(1, k - 20):k]) if k > 5 else np.nan for k in range(n)])
    ok = ~np.isnan(vol)
    dec = np.digitize(vol, np.nanpercentile(vol, np.arange(10, 100, 10)))
    sig = np.array([x["sig"] for x in rows])
    r = np.array([x["r"] for x in rows])
    rng = np.random.default_rng(156)
    out = ["研究 156：恐慌隔天做多 分段穩健性（D 開→D+1 開，扣 3 點；2017-05 前只有 S&P 觸發）", ""]
    for lo, hi in SEGS:
        inp = np.array([lo <= x["d"] < hi for x in rows])
        idx = np.where(sig & ok & inp)[0]
        pools = {k: np.where(~sig & ok & inp & (dec == dec[k]))[0] for k in idx}
        diff = np.mean([r[k] - r[pools[k]].mean() for k in idx])
        null = np.array([np.mean([r[rng.choice(pools[k])] - r[pools[k]].mean() for k in idx]) for _ in range(2000)])
        pv = (1 + np.sum(null >= diff)) / 2001
        v = np.sort(r[idx])[::-1]
        out.append(f"{lo[:7]}～{hi[:7] if hi != '2099' else '2026'}：{len(idx):3d} 次  每筆 {r[idx].mean():+.2%}  中位 {np.median(r[idx]):+.2%}  勝率 {np.mean(r[idx] > 0):.0%}  "
                   f"去掉最好 3 筆 {v[3:].mean():+.2%}  比同波動 {diff:+.2%}（p {pv:.3f}）")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究156_恐慌分段穩健性.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
