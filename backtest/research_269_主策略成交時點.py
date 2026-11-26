"""研究 269：主策略（v3）切換時的成交時點
訊號在 i 日收盤確定（週五價格訊號、或每天的融資過熱出場）；現行規則＝i+1 日收盤成交
比較：A 訊號日 i 收盤（實務上 13:25 前試撮下單，近似收盤價）、B i+1 日開盤、C i+1 日收盤（現行）
對每次切換計算「相對現行的價格優勢」：買進＝C 價 ÷ X 價 − 1；賣出＝X 價 ÷ C 價 − 1（正＝比現行好）
資料：00631L 真實 OHLC（2015-10～）；台指期近月日盤 OHLC（1998-07～，研究 63d 的 tx_daily_ohlc.csv）；加權收盤（A vs C，1998～）
用法：python -X utf8 backtest/research_269_主策略成交時點.py
"""
import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_138_金字塔加碼與分段停損 as R138  # noqa: E402

DAYS, ST, PX = R138.DAYS, R138.ST, R138.PX
sw = [(i, "買" if ST[i] == 1 else "賣") for i in range(261, len(DAYS) - 1) if ST[i] != ST[i - 1]]

tz = timezone(timedelta(hours=8))
g = json.load(open(os.path.join(HERE, "00631L.TW.json")))
r = g["chart"]["result"][0] if "chart" in g else g
q = r["indicators"]["quote"][0]
L = {datetime.fromtimestamp(t, tz).strftime("%Y-%m-%d"): (o, c) for t, o, c in zip(r["timestamp"], q["open"], q["close"]) if o and c}
TX = {}
with open(os.path.join(HERE, "tx_daily_ohlc.csv"), encoding="utf-8") as f:
    rd = csv.DictReader(f)
    cols = rd.fieldnames
    for row in rd:
        d = row[cols[0]]
        d = d if "-" in d else f"{d[:4]}-{d[4:6]}-{d[6:]}"
        try:
            TX[d] = (float(row["open"]), float(row["close"]))
        except (KeyError, ValueError):
            pass


def adv(kind, x, c):
    return c / x - 1 if kind == "買" else x / c - 1


out = ["研究 269：主策略切換成交時點（正＝比現行「下一交易日收盤」好）", f"切換 {len(sw)} 次（{DAYS[sw[0][0]]}～{DAYS[sw[-1][0]]}）", ""]
for nm, src, start in (("00631L 真實價", L, "2015-10-01"), ("台指期近月", TX, "1998-08-01")):
    rows = []
    for i, k in sw:
        d0, d1 = DAYS[i], DAYS[i + 1]
        if d0 < start or d0 not in src or d1 not in src:
            continue
        rows.append((k, adv(k, src[d0][1], src[d1][1]), adv(k, src[d1][0], src[d1][1]), d0))
    for kind in ("買", "賣", "全部"):
        sub = [x for x in rows if kind == "全部" or x[0] == kind]
        a = np.array([x[1] for x in sub])
        b = np.array([x[2] for x in sub])
        late = np.array([x[3] >= "2013" for x in sub])
        out.append(f"{nm} {kind}（{len(sub)} 次）：A 訊號日收盤 {a.mean():+.2%}（勝 {np.mean(a > 0):.0%}、t {a.mean() / (a.std(ddof=1) / np.sqrt(len(a))):+.1f}）｜B 隔天開盤 {b.mean():+.2%}（勝 {np.mean(b > 0):.0%}、t {b.mean() / (b.std(ddof=1) / np.sqrt(len(b))):+.1f}）"
                   + (f"｜2013～ A {a[late].mean():+.2%} B {b[late].mean():+.2%}" if nm.startswith("台指") else ""))
    out.append("")
a = np.array([adv(k, PX[i], PX[i + 1]) for i, k in sw if DAYS[i] >= "1998"])
out.append(f"加權收盤 1998～（{len(a)} 次）：A 訊號日收盤 vs 隔天收盤 {a.mean():+.2%}（勝 {np.mean(a > 0):.0%}）；2x 部位約 {2 * a.mean():+.2%}／次、一年約 {2 * a.mean() * len(a) / 28:+.2%}")
txt = "\n".join(out)
print(txt)
open(os.path.join(HERE, "結果_研究269_主策略成交時點.txt"), "w", encoding="utf-8").write(txt + "\n")
