"""研究 428：長假後（台股休市 ≥4 個日曆天）開紅盤日，用「假期間 S&P 累積漲跌」判斷恐慌做多
現行 P 只看前一個美國交易日；長假時美股可能連跌數天但最後一天沒跌 ≥2%
事件：休市 ≥4 天後的第一個交易日 D；累積＝台股休市前最後一天之後到 D 前一晚的 S&P 漲跌
台指期 D 開 → D+1 開（研究 148 資料），扣 3 點；分組：累積 ≤-2%／-2～0／>0；以及現行 P 是否已觸發
用法：python -X utf8 backtest/research_428_長假後恐慌.py
"""
import importlib.util
import io
import contextlib
import os
import sys
from datetime import date

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r417", os.path.join(HERE, "research_417_P滾動前進.py"))
R = importlib.util.module_from_spec(spec)
with contextlib.redirect_stdout(io.StringIO()):
    spec.loader.exec_module(R)
rows = R.rows  # (d, 夜盤, S&P 前一晚, D開→D+1開)
US = R.US  # {美國日期: 漲跌}
usd = sorted(US)
out = []
for k in range(1, len(rows)):
    d0, d = rows[k - 1][0], rows[k][0]
    gap = (date.fromisoformat(d) - date.fromisoformat(d0)).days
    if gap < 4:
        continue
    cum = 1.0
    for u in usd:
        if d0 <= u < d:
            cum *= 1 + US[u]
    cur = (rows[k][1] is not None and rows[k][1] <= -0.02) or (rows[k][2] is not None and rows[k][2] <= -0.02)
    out.append((d, gap, cum - 1, cur, rows[k][3]))
v = np.array([x[4] for x in out])
L = [f"研究 428：長假（休市 ≥4 天）後第一天（{len(out)} 次；台指期 D 開 → D+1 開、扣 3 點）", f"全部：每筆 {v.mean():+.2%} 勝率 {np.mean(v > 0):.0%}"]
for lab, f in (("假期間 S&P 累積 ≤-2%", lambda x: x[2] <= -0.02), ("-2%～0", lambda x: -0.02 < x[2] <= 0), ("> 0", lambda x: x[2] > 0)):
    s = [x for x in out if f(x)]
    if s:
        r = np.array([x[4] for x in s])
        L.append(f"  {lab}：{len(s)} 次 每筆 {r.mean():+.2%} 勝率 {np.mean(r > 0):.0%}；其中現行 P 已觸發 {sum(x[3] for x in s)} 次")
miss = [x for x in out if x[2] <= -0.02 and not x[3]]
L.append(f"\n現行 P 沒觸發但累積 ≤-2%（新規則會多做的）：{len(miss)} 次 " + "、".join(f"{x[0]}（累積 {x[2]:+.1%}→{x[4]:+.1%}）" for x in miss))
o = "\n".join(L)
print(o)
open(os.path.join(HERE, "結果_研究428_長假後恐慌.txt"), "w", encoding="utf-8").write(o + "\n")
