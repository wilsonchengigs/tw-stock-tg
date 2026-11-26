"""研究 251（描述性）：主策略（v3）空手時遇到 D 台美背離觸發，之後多快重新進場？
對照：v3 空手、加權 20 日跌幅相近（±3%）但背離 > -5% 的日子（台股跟美股一起跌）
指標：之後 20／60／120 個交易日內 v3 重新進場的比例、之後 60 日加權報酬
用法：python -X utf8 backtest/research_251_背離後主策略回場.py
"""
import io
import contextlib
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
with contextlib.redirect_stdout(io.StringIO()):
    import research_206_台美背離延伸 as R
    import research_138_金字塔加碼與分段停損 as R138

ST = dict(zip(R138.DAYS, R138.ST))
D, TW, N, tw20 = R.DAYS, R.TW, R.N, R.tw20
st = np.array([ST.get(d, np.nan) for d in D])
gap = R.GAP["GSPC"]


def reentry(k, h):
    seg = st[k + 1:k + 1 + h]
    return np.nan if len(seg) < h else float((seg == 1).any())


ev = [k for k in R.events(gap <= -0.10) if st[k] == 0 and k + 120 < N]
L = ["研究 251：主策略空手時 D 觸發後，v3 多快重新進場（1998～）", ""]
ctrl = [k for k in range(20, N - 120) if st[k] == 0 and gap[k] > -0.05 and not np.isnan(tw20[k])]
for lab, ks in (("D 觸發（空手）", ev),):
    for h in (20, 60, 120):
        a = np.nanmean([reentry(k, h) for k in ks])
        # 對照：每個事件找 tw20 相近的對照日平均
        c = np.nanmean([np.nanmean([reentry(j, h) for j in ctrl if abs(tw20[j] - tw20[k]) <= 0.03][::5]) for k in ks])
        L.append(f"  {h:3d} 日內重新進場：D {a:.0%}｜同跌幅、台股跟美股一起跌 {c:.0%}")
    r60 = np.mean([TW[k + 60] / TW[k] - 1 for k in ks])
    c60 = np.nanmean([np.nanmean([TW[j + 60] / TW[j] - 1 for j in ctrl if abs(tw20[j] - tw20[k]) <= 0.03]) for k in ks])
    L.append(f"  之後 60 日加權：D {r60:+.1%}｜對照 {c60:+.1%}（{len(ks)} 次）")
out = "\n".join(L)
print(out)
open(os.path.join(HERE, "結果_研究251_背離後主策略回場.txt"), "w", encoding="utf-8").write(out + "\n")
