"""研究 153：日盤大跌（台指期 D-1 收盤對收盤 ≤ −x%）→ D 開盤做多、D+1 開盤出——是否在候選 6（P）之外有增量

研究 139 顯示「前日盤跌 ≥2% → 夜盤續跌」（夜收 -0.25%），但隔天開盤進可能已反映；這裡看：
- 全部：D-1 日盤收對收 ≤ −2／−3／−4%
- 增量：同時 P（夜盤或 S&P 跌 ≥2%）沒觸發的日子
報酬 D 開→D+1 開扣 3 點；同波動度對照；2017-05～、1998–2017 兩段；Bonferroni 12 格
用法：python -X utf8 backtest/research_153_日盤大跌隔天做多.py
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
    prevcc = np.r_[0.0, cc[:-1]]  # D-1 的收對收
    vol = np.array([np.std(cc[max(1, k - 20):k]) if k > 5 else np.nan for k in range(n)])
    ok = ~np.isnan(vol)
    dec = np.digitize(vol, np.nanpercentile(vol, np.arange(10, 100, 10)))
    P = np.array([x["sig"] for x in rows])
    r = np.array([x["r"] for x in rows])
    rng = np.random.default_rng(153)
    out = ["研究 153：日盤大跌隔天做多（D-1 台指期收對收 ≤ −x% → D 開盤進、D+1 開盤出）", ""]
    for per, lo, hi in (("2017-05～", "2017-05-15", "2099"), ("1998～2017-05", "1998", "2017-05-15")):
        inp = np.array([lo <= x["d"] < hi for x in rows])
        out.append(f"== {per} ==")
        for th in (0.02, 0.03, 0.04):
            base = ok & inp & (prevcc <= -th)
            ctrl = ok & inp & (prevcc > -0.01) & ~P
            for lab, msk in (("全部", base), ("P 沒觸發（增量）", base & ~P)):
                idx = np.where(msk)[0]
                if len(idx) < 5:
                    out.append(f"跌≥{th:.0%} {lab} {len(idx)} 次")
                    continue
                pools = {k: np.where(ctrl & (dec == dec[k]))[0] for k in idx}
                diff = np.mean([r[k] - r[pools[k]].mean() for k in idx])
                null = np.array([np.mean([r[rng.choice(pools[k])] - r[pools[k]].mean() for k in idx]) for _ in range(2000)])
                pv = (1 + np.sum(null >= diff)) / 2001
                out.append(f"跌≥{th:.0%} {lab:10s} {len(idx):3d} 次  每筆 {r[msk].mean():+.2%}  勝率 {np.mean(r[msk] > 0):.0%}  比同波動 {diff:+.2%}（p {pv:.3f}，Bonferroni {min(1, pv * 12):.3f}）")
        out.append("")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究153_日盤大跌隔天做多.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
