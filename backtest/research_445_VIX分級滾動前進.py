"""研究 445：研究 444（P 依台指 VIX 調倍數）的滾動前進驗證——門檻是看過研究 443 才定的，要確認不是事後挑選
候選：低 VIX 門檻 lo ∈ {20,25,30} × 低時倍數 a ∈ {0, 0.5} × 高 VIX 門檻 hi ∈ {none, 35, 45}（高時 1.5x）＝18 組
每年 Y（2006～2026）用 2002～Y−1 的 P 逐筆（研究 407 的 padd 與前一天 VIX）挑「每單位平均倍數的增量最高」的一組套到 Y
比較：滾動挑選、固定 1x、研究 444 的 C（25／0.5／35）；以 P 部分的累積損益（占資金，加總）衡量
用法：python -X utf8 backtest/research_445_VIX分級滾動前進.py
"""
import io
import contextlib
import os
import sys
from collections import Counter

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
with contextlib.redirect_stdout(io.StringIO()):
    import research_444_P依VIX倍數 as R4  # noqa: E402
R = R4.R
D = R.D
idx = R4.idxp
pv = np.array([R4.Vp[k - 1] if k >= 1 else np.nan for k in idx])
pr = R.padd[idx]
yrs = np.array([D[k][:4] for k in idx])
ok = ~np.isnan(pv)
C = [(lo, a, hi) for lo in (20, 25, 30) for a in (0.0, 0.5) for hi in (None, 35, 45)]


def size(c, v):
    lo, a, hi = c
    return np.where(v < lo, a, np.where((hi is not None) & (v >= (hi or 999)), 1.5, 1.0))


def score(c, m):
    s = size(c, pv[m])
    return np.sum(s * pr[m]) / max(np.mean(s), 1e-9)  # 每單位平均曝險的總損益


wf, fx, c444, picks = [], [], [], []
for Y in range(2006, 2027):
    y = str(Y)
    past = ok & (yrs < y)
    cur = ok & (yrs == y)
    if past.sum() < 30 or cur.sum() == 0:
        continue
    best = max(C, key=lambda c: score(c, past))
    picks.append(best)
    wf.append(np.sum(size(best, pv[cur]) * pr[cur]))
    fx.append(np.sum(pr[cur]))
    c444.append(np.sum(size((25, 0.5, 35), pv[cur]) * pr[cur]))
wf, fx, c444 = np.array(wf), np.array(fx), np.array(c444)
L = ["研究 445：P 依 VIX 調倍數的滾動前進（2006～2026 樣本外；P 部分逐年損益加總、占資金）", ""]
L.append(f"滾動挑選：合計 {wf.sum():+.1%}｜每年平均 {wf.mean():+.2%}｜贏固定 1x 的年數 {np.sum(wf > fx)}／{len(wf)}")
L.append(f"固定 1x：合計 {fx.sum():+.1%}｜每年平均 {fx.mean():+.2%}")
L.append(f"研究 444 C（25/0.5/35）：合計 {c444.sum():+.1%}｜贏固定 1x 的年數 {np.sum(c444 > fx)}／{len(fx)}")
L.append("每年挑到：" + "、".join(f"lo{c[0]}/a{c[1]}/hi{c[2]}×{v}" for c, v in Counter(picks).most_common(4)))
out = "\n".join(L)
print(out)
open(os.path.join(HERE, "結果_研究445_VIX分級滾動前進.txt"), "w", encoding="utf-8").write(out + "\n")
