"""研究 411：研究 407 的長歷史實際配置再加 V 爆量收黑加碼（v3 在場、量 ≥1.5 倍 20 日均且收黑 → 隔天開盤 1x 台指期抱 10 天，5% 停損，v3 出場提前平；研究 164／175 逐筆）
用法：python -X utf8 backtest/research_411_實際配置含V.py
"""
import io
import contextlib
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
with contextlib.redirect_stdout(io.StringIO()):
    import research_407_實際配置長歷史 as R  # noqa: E402
R175 = R.R175
R139, R138, bt = R175.R139, R175.R138, R175.bt
dates, day, night, near = R.dates, R.day, R.night, R.near
bi = {d: k for k, d in enumerate(R138.DAYS)}
ds = R.ds
n = len(ds)
st = np.array([R138.ST[bi[d]] for d in ds])
vsig = np.zeros(n, bool)
for k, d in enumerate(ds):
    i = bi[d]
    amts = [R139.AMT.get(R138.DAYS[j]) for j in range(i - 20, i)]
    amts = [a for a in amts if a]
    a0 = R139.AMT.get(d)
    vsig[k] = bool(a0 and len(amts) >= 16 and a0 / (sum(amts) / len(amts)) >= 1.5 and bt.PX[i] < bt.PX[i - 1])
vadd = np.zeros(len(R.D))
cnt, k = 0, 0
while k < n - 2:
    if vsig[k] and st[k] == 1:
        j = k + 1
        last = j
        for h in range(10):
            last = min(j + h, n - 1)
            if st[last] == 0:
                break
        r = R175.trade(day, night, ds, j, near[ds[k]], (last, "close"), 0.05)
        if ds[last] in R.idx:
            vadd[R.idx[ds[last]]] += 1.0 * r
            cnt += 1
        k = last + 1
    else:
        k += 1
yrs = R.yrs
L = [f"研究 411：實際配置長歷史＋V（2002～；V {cnt} 筆）", ""]
for lab, r in (("主策略 1.7x＋P＋D（研究 407）", R.main + R.padd + R.dadd), ("＋V 1x", R.main + R.padd + R.dadd + vadd)):
    eq = np.cumprod(1 + r)
    cg = eq[-1] ** (bt.TD / len(r)) - 1
    mdd = (eq / np.maximum.accumulate(eq) - 1).min()
    seg = []
    for lo, hi in (("2002", "2013"), ("2013", "2099")):
        m = (yrs >= lo) & (yrs < hi)
        x = np.cumprod(1 + r[m])
        seg.append(f"{x[-1] ** (bt.TD / m.sum()) - 1:.1%}")
    L.append(f"{lab:24s} 年化 {cg:5.1%}  回檔 {mdd:6.1%}｜2002–2012 {seg[0]}｜2013～ {seg[1]}")
nz = vadd != 0
L.append(f"V 每筆（資金）平均 {vadd[nz].mean():+.2%}、勝率 {np.mean(vadd[nz] > 0):.0%}、最差 {vadd[nz].min():+.1%}")
out = "\n".join(L)
print(out)
open(os.path.join(HERE, "結果_研究411_實際配置含V.txt"), "w", encoding="utf-8").write(out + "\n")
