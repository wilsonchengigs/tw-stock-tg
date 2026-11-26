"""研究 207b：台美背離參數表面——回看 W × 門檻 的 5 日報酬（原始、去叢集 W 天）與 204b 同一套同跌幅對照（tw20 ±2% 且 |背離|<5%）
W＝10／15／20／25／30／40；門檻 −6～−16%；另列 2018-06 以後（205 的回測期）與之前
用法：python -X utf8 backtest/research_207b_背離參數表面.py
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_206_台美背離延伸 as R  # noqa: E402

TW, DAYS, N, US, f5 = R.TW, R.DAYS, R.N, R.BENCH["GSPC"], R.F[5]
base = np.nanmean(f5)
L = ["研究 207b：W × 門檻 的 5 日表現（每格：次數 原始平均／同跌幅超額；前段＝~2018-05、後段＝2018-06~ 的超額）", f"全部日 5 日平均 {base:+.2%}"]
for W in (10, 15, 20, 25, 30, 40):
    twW = np.array([TW[k] / TW[k - W] - 1 if k >= W else np.nan for k in range(N)])
    gap = twW - np.array([US[k] / US[k - W] - 1 if k >= W else np.nan for k in range(N)])
    okc = ~np.isnan(gap) & (np.abs(gap) < 0.05) & ~np.isnan(f5)
    xs = twW[okc]
    ys = f5[okc]
    L.append(f"\nW {W}")
    for th in (0.06, 0.08, 0.10, 0.12, 0.14, 0.16):
        ev, last = [], -99
        for k in range(W, N - 5):
            if gap[k] <= -th and k - last > W:
                ev.append(k)
                last = k
        if len(ev) < 3:
            continue
        exs = []
        for k in ev:
            m = np.abs(xs - twW[k]) <= 0.02
            exs.append(f5[k] - ys[m].mean() if m.sum() >= 20 else np.nan)
        exs = np.array(exs)
        pre = [e for k, e in zip(ev, exs) if DAYS[k] < "2018-06" and not np.isnan(e)]
        post = [e for k, e in zip(ev, exs) if DAYS[k] >= "2018-06" and not np.isnan(e)]
        t = np.nanmean(exs) / (np.nanstd(exs) / np.sqrt(np.sum(~np.isnan(exs))))
        L.append(f"  ≤-{th:.0%}：{len(ev):3d} 次 原始 {np.mean(f5[ev]):+.2%}／超額 {np.nanmean(exs):+.2%}（t {t:+.1f}）  前段 {np.mean(pre) if pre else np.nan:+.2%}（{len(pre)}）後段 {np.mean(post) if post else np.nan:+.2%}（{len(post)}）")
out = "\n".join(L) + "\n"
print(out)
open(os.path.join(HERE, "結果_研究207b_背離參數表面.txt"), "w", encoding="utf-8").write(out)
