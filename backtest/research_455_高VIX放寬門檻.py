"""研究 455：前一天清洗 VIX ≥35／≥30 時，P 門檻放寬到 夜盤或 S&P 跌 ≥1%／≥1.5%：只看「新增」的交易（原 -2% 沒觸發）
D 開→D+1 開，台指期真實價；對照＝同 VIX 組的其他非訊號日
用法：python -X utf8 backtest/research_455_高VIX放寬門檻.py
"""
import io
import contextlib
import os
import sys
from datetime import datetime, timedelta

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
with contextlib.redirect_stdout(io.StringIO()):
    import research_148_恐慌連續觸發 as R
    import research_444_P依VIX倍數 as M
med = np.array([np.median(M.V[max(0, k - 2):k + 1]) for k in range(len(M.V))])
vix = {d: med[k] for k, d in enumerate(M.R.D) if not np.isnan(med[k])}
dates, day, night, near = R.R144.R139.load_tx()
US = R.R144.us("GSPC.json")
rows = []
for k in range(1, len(dates) - 1):
    d, pd_, d1 = dates[k], dates[k - 1], dates[k + 1]
    m = near[pd_]
    b, b1 = day[d].get(m), day[d1].get(m)
    v = vix.get(pd_)
    if not (b and b1) or v is None:
        continue
    nb = night[d].get(m)
    nr = (nb[3] / nb[0] - 1) if nb and nb[4] >= 1000 else None
    u = None
    for back in range(1, 5):
        kk = (datetime.fromisoformat(d) - timedelta(days=back)).strftime("%Y-%m-%d")
        if kk in US:
            u = US[kk]
            break
    worst = min([x for x in (nr, u) if x is not None], default=0.0)
    rows.append((d, v, worst, (b1[0] - b[0] - R.COST) / b[0]))
d_, v_, w_, r_ = (np.array(x) for x in zip(*rows))
y_ = np.array([x[:4] for x in d_])
L = ["研究 455：高 VIX 時放寬 P 門檻（只看新增的交易；D 開→D+1 開）", ""]
for vl in (30, 35):
    for th in (-0.01, -0.015):
        m = (v_ >= vl) & (w_ <= th) & (w_ > -0.02)
        c = (v_ >= vl) & (w_ > th)
        seg = [r_[m & (y_ >= lo) & (y_ < hi)] for lo, hi in (("1998", "2013"), ("2013", "2099"))]
        L.append(f"VIX≥{vl} 跌 {th:.1%}～-2%：{m.sum()} 筆 平均 {r_[m].mean():+.2%} 勝率 {np.mean(r_[m] > 0):.0%}｜同 VIX 其他日 {r_[c].mean():+.2%}｜兩段 {seg[0].mean():+.2%}（{len(seg[0])}）／{seg[1].mean():+.2%}（{len(seg[1])}）")
o = "\n".join(L)
print(o)
open(os.path.join(HERE, "結果_研究455_高VIX放寬門檻.txt"), "w", encoding="utf-8").write(o + "\n")
# 不看 VIX 的 -1%～-2%、VIX 環狀平移的家族檢定（4 組取最大 t）
m0 = (w_ <= -0.01) & (w_ > -0.02)
L2 = ["", f"不看 VIX 跌 -1%～-2%：{m0.sum()} 筆 平均 {r_[m0].mean():+.2%}（VIX<30 部分 {r_[m0 & (v_ < 30)].mean():+.2%}）"]


def tmax(vv):
    best = -9
    for vl in (30, 35):
        for th in (-0.01, -0.015):
            m = (vv >= vl) & (w_ <= th) & (w_ > -0.02)
            x = r_[m]
            if len(x) > 5:
                best = max(best, x.mean() / (x.std() / np.sqrt(len(x))))
    return best


t0 = tmax(v_)
rng = np.random.default_rng(455)
null = [tmax(np.roll(v_, int(s))) for s in rng.integers(250, len(v_) - 250, 500)]
L2.append(f"家族（4 組）最大 t {t0:.2f}；VIX 平移 500 次 p {np.mean(np.array(null) >= t0):.3f}")
o2 = "\n".join(L2)
print(o2)
open(os.path.join(HERE, "結果_研究455_高VIX放寬門檻.txt"), "a", encoding="utf-8").write(o2 + "\n")
