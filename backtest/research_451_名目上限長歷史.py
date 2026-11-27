"""研究 451：主策略在場時期貨加碼合計 >1.5x 名目（15% 現金的保證金上限）在 2002～ 多常發生、照日報規則縮 P 的影響
模型＝研究 411（主策略 1.7x＋P 1x＋D 0.5x＋V 1x；F、獨立短線不含）。持有日：P＝訊號隔天、D／V＝進場到出場日
超限時照日報：P 縮到「1.5 − 當天其他加碼」（最少 0）；V、D 先到先做不縮
用法：python -X utf8 backtest/research_451_名目上限長歷史.py
"""
import io
import contextlib
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
with contextlib.redirect_stdout(io.StringIO()):
    import research_411_實際配置含V as V
R = V.R
D, idx, ds = R.D, R.idx, R.ds
n = len(D)
inmain = np.zeros(n, bool)
for k, d in enumerate(ds):
    if d in idx:
        inmain[idx[d]] = V.st[k] == 1
expo = np.zeros(n)


def hold(fn_sig, size, maxh, stopmain):
    k = 0
    while k < len(ds) - 2:
        if fn_sig(k):
            j = k + 1
            last = min(j + maxh - 1, len(ds) - 1)
            if stopmain:
                for h in range(maxh):
                    last = min(j + h, len(ds) - 1)
                    if V.st[last] == 0:
                        break
            for t in range(j, last + 1):
                if ds[t] in idx:
                    expo[idx[ds[t]]] += size
            k = last + 1
        else:
            k += 1


g = np.array([R.R205.GAP.get(d, np.nan) for d in ds])
hold(lambda k: g[k] <= -0.10, 0.5, 5, False)
hold(lambda k: V.vsig[k] and V.st[k] == 1, 1.0, 10, True)
pk = np.where(R.padd != 0)[0]
pnew = R.padd.copy()
over = []
for k in pk:
    tot = expo[k] + 1.0
    if inmain[k] and tot > 1.5:
        s = max(0.0, 1.5 - expo[k])
        over.append((D[k], expo[k], R.padd[k], s))
        pnew[k] = R.padd[k] * s


def cg(r):
    eq = np.cumprod(1 + r)
    return eq[-1] ** (R.bt.TD / len(r)) - 1, (eq / np.maximum.accumulate(eq) - 1).min()


base = R.main + R.padd + R.dadd + V.vadd
L = ["研究 451：期貨加碼名目上限 1.5x（主策略在場）長歷史 2002～", ""]
dm = inmain.sum()
L.append(f"主策略在場 {dm} 天；V＋D 已持有 >1.5x：{np.sum(inmain & (expo > 1.5))} 天；P 觸發 {len(pk)} 次，其中在場且合計 >1.5x：{len(over)} 次")
for d, e, r, s in over:
    L.append(f"  {d} 其他加碼 {e:.1f}x → P 縮成 {s:.1f}x；P 原本損益 {r:+.2%}")
a, b = cg(base), cg(R.main + pnew + R.dadd + V.vadd)
L.append(f"\n不設上限：年化 {a[0]:.1%} 回檔 {a[1]:.1%}｜照上限縮 P：年化 {b[0]:.1%} 回檔 {b[1]:.1%}")
out = "\n".join(L)
print(out)
open(os.path.join(HERE, "結果_研究451_名目上限長歷史.txt"), "w", encoding="utf-8").write(out + "\n")
