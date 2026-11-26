"""研究 268：春節效應外部驗證（接研究 261、266）
台股錨點：L＝封關日、R＝開紅盤日；窗格 PRE3（L−3 收→L 收）、OVER（L−3 收→R+4 收，即研究 261 的 OVER 3,4）
其他市場：用「≤ 台股 L−3 日期的最後收盤」到「≤ 台股 R+4 日期的最後收盤」（同一段日曆時間）；以及只看 L−3→L
超額＝減同市場所有同長度（日曆天相近：用交易日數平均）窗格的平均；t 值；台股對 S&P 同期間回歸殘差
用法：python -X utf8 backtest/research_268_春節效應外部驗證.py
"""
import bisect
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_261_春節效應 as R  # noqa: E402
import research_266_年底效應外部驗證 as X  # noqa: E402

DAYS, L_IDX = R.DAYS, R.L_IDX
spans = [(DAYS[k - 3], DAYS[k], DAYS[k + 5]) for k in L_IDX if k + 5 < R.N]
out = ["研究 268：春節效應外部驗證（同一段日曆時間；不扣成本）", ""]
res = {}
mk = [("加權", list(zip(R.DAYS, R.PX)))] + [(n, X.load(n)) for n in ("GSPC", "HSI", "KS11", "N225")]
for nm, rows in mk:
    d = [x[0] for x in rows]
    p = np.array([x[1] for x in rows])

    def px_at(day):
        j = bisect.bisect_right(d, day) - 1
        return p[j] if j >= 0 else np.nan
    over = np.array([px_at(c) / px_at(a) - 1 for a, b, c in spans])
    pre = np.array([px_at(b) / px_at(a) - 1 for a, b, c in spans])
    base8 = (p[8:] / p[:-8] - 1).mean()
    base3 = (p[3:] / p[:-3] - 1).mean()
    res[nm] = over
    late = np.array([s[0] >= "2013" for s in spans])
    t = (over.mean() - base8) / (over.std(ddof=1) / np.sqrt(len(over)))
    out.append(f"{nm:<5s}：OVER 每筆 {over.mean():+.2%} 勝率 {np.mean(over > 0):.0%} 超額 {over.mean() - base8:+.2%}（t {t:+.2f}）2013～ {over[late].mean():+.2%}｜PRE3 每筆 {pre.mean():+.2%} 超額 {pre.mean() - base3:+.2%}")
a, b = res["加權"], res["GSPC"]
beta = np.cov(a, b)[0, 1] / b.var(ddof=1)
rr = a - beta * b
out.append("")
out.append(f"加權 vs S&P 同期間：相關 {np.corrcoef(a, b)[0, 1]:+.2f}、β {beta:.2f}、殘差 {rr.mean():+.2%}（t {rr.mean() / (rr.std(ddof=1) / np.sqrt(len(rr))):+.2f}）")
out.append(f"加權 vs 恆生 相關 {np.corrcoef(a, res['HSI'])[0, 1]:+.2f}、vs KOSPI {np.corrcoef(a, res['KS11'])[0, 1]:+.2f}")
txt = "\n".join(out)
print(txt)
open(os.path.join(HERE, "結果_研究268_春節效應外部驗證.txt"), "w", encoding="utf-8").write(txt + "\n")
