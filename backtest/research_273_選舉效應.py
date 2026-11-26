"""研究 273（使用者 11/26 問）：台灣選舉前後的加權表現
總統大選：2000-03-18、2004-03-20、2008-03-22、2012-01-14、2016-01-16、2020-01-11、2024-01-13
地方／合併選舉：1998-12-05、2001-12-01、2005-12-03、2009-12-05、2010-11-27、2014-11-29、2018-11-24、2022-11-26（2026-11-28 九合一在即）
L＝投票日前最後交易日；R＝投票日後第一個交易日
窗格：選前 20 日（L−20→L）、選前 5 日、開票後第一天（L 收→R 收）、選後 5／20／60 日（L 收→R+4／R+19／R+59）
對照：所有同長度窗格平均；附逐次表
用法：python -X utf8 backtest/research_273_選舉效應.py
"""
import bisect
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402

D, P = bt.DAYS, np.array(bt.PX)
PRES = ["2000-03-18", "2004-03-20", "2008-03-22", "2012-01-14", "2016-01-16", "2020-01-11", "2024-01-13"]
LOCAL = ["1998-12-05", "2001-12-01", "2005-12-03", "2009-12-05", "2010-11-27", "2014-11-29", "2018-11-24", "2022-11-26"]
W = [("選前20日", -20, 0), ("選前5日", -5, 0), ("開票後首日", 0, 1), ("選後5日", 0, 5), ("選後20日", 0, 20), ("選後60日", 0, 60)]


def r(a, b):
    return P[b] / P[a] - 1


base = {nm: np.mean([r(k + a, k + b) for k in range(60, len(P) - 61)]) for nm, a, b in W}
out = ["研究 273：台灣選舉前後的加權表現（L＝投票前最後交易日；報酬不含息）", ""]
out.append("一般同長度窗格平均：" + "、".join(f"{nm} {v:+.2%}" for nm, v in base.items()))
for lab, days in (("總統大選", PRES), ("地方選舉", LOCAL)):
    out.append(f"\n== {lab} ==")
    out.append("投票日      " + " ".join(f"{nm:>8s}" for nm, _, _ in W))
    rows = []
    for v in days:
        k = bisect.bisect_left(D, v) - 1
        rows.append([r(k + a, k + b) for _, a, b in W])
        out.append(f"{v}  " + " ".join(f"{x:+8.1%}" for x in rows[-1]))
    m = np.array(rows)
    out.append("平均        " + " ".join(f"{x:+8.1%}" for x in m.mean(0)))
    out.append("上漲次數    " + " ".join(f"{int((m[:, j] > 0).sum()):>5d}/{len(m)}" for j in range(len(W))))
    out.append("減一般平均  " + " ".join(f"{m[:, j].mean() - base[nm]:+8.1%}" for j, (nm, _, _) in enumerate(W)))
allm = []
for v in PRES + LOCAL:
    k = bisect.bisect_left(D, v) - 1
    allm.append(r(k, k + 1))
allm = np.array(allm)
sd = np.std([r(k, k + 1) for k in range(60, len(P) - 2)])
out.append(f"\n開票後首日絕對漲跌幅平均 {np.abs(allm).mean():.1%}（一般交易日 {np.mean(np.abs(np.diff(P) / P[:-1])):.1%}）；15 次中 {int((allm > 0).sum())} 次漲")
txt = "\n".join(out)
print(txt)
open(os.path.join(HERE, "結果_研究273_選舉效應.txt"), "w", encoding="utf-8").write(txt + "\n")
