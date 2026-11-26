"""研究 266：年底效應外部驗證（研究 262 的 12 月最後交易日前 3 天收盤 → 1 月第 5 個交易日收盤）
市場：加權、S&P500、日經、KOSPI、恆生（Yahoo json）；各自交易日曆；1998～
每筆、勝率、相對同長度（8 天）所有窗格平均的超額、t 值；台股超額 vs S&P 同期報酬的相關與「扣掉美股 β 後」的殘差
用法：python -X utf8 backtest/research_266_年底效應外部驗證.py
"""
import json
import os
from datetime import datetime, timedelta, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TZ = {"GSPC": -5, "N225": 9, "KS11": 9, "HSI": 8, "TWII": 8}


def load(name):
    g = json.load(open(os.path.join(HERE, f"{name}.json")))
    tz = timezone(timedelta(hours=TZ[name]))
    r = g["chart"]["result"][0] if "chart" in g else g
    return [(datetime.fromtimestamp(t, tz).strftime("%Y-%m-%d"), c) for t, c in zip(r["timestamp"], r["indicators"]["quote"][0]["close"]) if c]


def study(rows):
    d = [x[0] for x in rows]
    p = np.array([x[1] for x in rows])
    ev = {}
    for k in range(3, len(d) - 5):
        if d[k][5:7] == "12" and d[k + 1][:4] != d[k][:4] and d[k] >= "1998":
            ev[d[k][:4]] = p[k + 5] / p[k - 3] - 1
    allw = p[8:] / p[:-8] - 1
    return ev, allw.mean()


import sys  # noqa: E402
sys.path.insert(0, HERE)
import bt  # noqa: E402

out = ["研究 266：年底效應外部驗證（12 月最後交易日前 3 天收盤 → 1 月第 5 個交易日收盤；不扣成本）", ""]
res = {}
tw = [(d, p) for d, p in zip(bt.DAYS, bt.PX)]
for nm, rows in (("加權", tw),) + tuple((n, load(n)) for n in ("GSPC", "N225", "KS11", "HSI")):
    ev, base = study(rows)
    x = np.array(list(ev.values()))
    res[nm] = ev
    late = np.array([v for y, v in ev.items() if y >= "2013"])
    t = (x.mean() - base) / (x.std(ddof=1) / np.sqrt(len(x)))
    out.append(f"{nm:<5s}：{len(x)} 次 每筆 {x.mean():+.2%} 勝率 {np.mean(x > 0):.0%} 一般 8 天 {base:+.2%} 超額 {x.mean() - base:+.2%}（t {t:+.2f}）｜2013～ {late.mean():+.2%}（{len(late)} 次）")
ys = sorted(set(res["加權"]) & set(res["GSPC"]))
a = np.array([res["加權"][y] for y in ys])
b = np.array([res["GSPC"][y] for y in ys])
beta = np.cov(a, b)[0, 1] / b.var(ddof=1)
resid = a - beta * b
out.append("")
out.append(f"加權 vs S&P 同窗格：相關 {np.corrcoef(a, b)[0, 1]:+.2f}、β {beta:.2f}；扣掉 β×S&P 後加權每筆殘差 {resid.mean():+.2%}（t {resid.mean() / (resid.std(ddof=1) / np.sqrt(len(resid))):+.2f}）")
out.append("逐年 加權／S&P：" + "、".join(f"{y} {res['加權'][y]:+.1%}/{res['GSPC'][y]:+.1%}" for y in ys))
txt = "\n".join(out)
print(txt)
open(os.path.join(HERE, "結果_研究266_年底效應外部驗證.txt"), "w", encoding="utf-8").write(txt + "\n")
