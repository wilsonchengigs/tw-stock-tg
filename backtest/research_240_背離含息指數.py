"""研究 240：D 台美背離用含息報酬指數重算（除息季價格指數會被機械性拉低，可能造成假的「台股獨跌」）
價格版：加權價格指數 20 日 − S&P 價格 20 日（現行 D）
含息版：證交所發行量加權報酬指數（tr_index_daily.csv，2003～）20 日 − ^SP500TR 20 日
比較 2003～：事件（≤-10%，去叢集 20 天）、只在其中一種出現的事件、6～9 月事件；之後 5 日加權報酬（價格與含息）與同跌幅超額（研究 204b 方法）
用法：python -X utf8 backtest/research_240_背離含息指數.py
"""
import bisect
import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_206_台美背離延伸 as R  # noqa: E402

DAYS, N, TW, tw20 = R.DAYS, R.N, R.TW, R.tw20
tr = {r["date"]: float(r["tr"]) for r in csv.DictReader(open(os.path.join(HERE, "tr_index_daily.csv")))}
TR = np.array([tr.get(d, np.nan) for d in DAYS])
g = json.load(open(os.path.join(HERE, "SP500TR.json")))
NY = timezone(timedelta(hours=-5))
rows = [(datetime.fromtimestamp(t, NY).strftime("%Y-%m-%d"), p) for t, p in zip(g["timestamp"], g["indicators"]["quote"][0]["close"]) if p]
sd, sp = [x for x, _ in rows], [x for _, x in rows]
USTR = np.array([sp[bisect.bisect_left(sd, d) - 1] for d in DAYS])
tr20 = np.array([TR[k] / TR[k - 20] - 1 if k >= 20 else np.nan for k in range(N)])
ustr20 = np.array([USTR[k] / USTR[k - 20] - 1 if k >= 20 else np.nan for k in range(N)])
gap_p = R.GAP["GSPC"]
gap_t = tr20 - ustr20
start = DAYS.index(next(d for d in DAYS if d >= "2003-02-01"))
f5 = R.F[5]
EXP = R.EX[("GSPC", 5)]
mon = np.array([int(d[5:7]) for d in DAYS])


def events(gap):
    out, last = [], -99
    for k in range(start, N):
        if gap[k] <= -0.10 and k - last > 20:
            out.append(k)
            last = k
    return out


ep, et = events(gap_p), events(gap_t)
near = lambda k, ev: any(abs(k - j) <= 5 for j in ev)  # noqa: E731
L = [f"研究 240：台美背離 價格指數 vs 含息報酬指數（{DAYS[start]}～{DAYS[-1]}，門檻 -10%）",
     f"現況：價格版 {gap_p[-1]:+.1%}、含息版 {gap_t[-1]:+.1%}", ""]
for lab, ev in (("價格版（現行 D）", ep), ("含息版", et)):
    v, x = f5[ev], EXP[ev]
    m = ~np.isnan(v)
    L.append(f"{lab}：{len(ev)} 次 5 日 {np.nanmean(v):+.2%}、同跌幅超額 {np.nanmean(x):+.2%}、勝率 {np.mean(v[m] > 0):.0%}；6～9 月 {sum(1 for k in ev if 6 <= mon[k] <= 9)} 次")
only_p = [k for k in ep if not near(k, et)]
only_t = [k for k in et if not near(k, ep)]
L.append(f"\n只在價格版出現 {len(only_p)} 次：" + "、".join(f"{DAYS[k]}（5 日 {f5[k]:+.1%}）" for k in only_p))
L.append(f"只在含息版出現 {len(only_t)} 次：" + "、".join(f"{DAYS[k]}（5 日 {f5[k]:+.1%}）" for k in only_t))
diff = gap_p - gap_t
L.append("\n價格版 − 含息版 背離差（平均，依月份）：" + "  ".join(f"{m}月 {np.nanmean(diff[(mon == m) & (np.arange(N) >= start)]):+.2%}" for m in range(1, 13)))
out = "\n".join(L) + "\n"
print(out)
open(os.path.join(HERE, "結果_研究240_背離含息指數.txt"), "w", encoding="utf-8").write(out)
