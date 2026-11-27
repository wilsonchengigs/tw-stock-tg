"""研究 403：P 恐慌隔天做多的日內進場時點（加權 1 分 K 2010～；指數代理台指期，08:45 開盤以 09:00 K 棒開盤近似）
P 觸發日：研究 148 的 build()（夜盤跌 ≥2% 或 S&P 前一晚跌 ≥2%）
進場：09:00 開、09:15、09:30、10:00、11:00、13:25 收；條件式：09:30 時已比開盤再跌 ≥1% 才進（否則 09:00 已進）
出場：隔天 09:00 K 棒開盤（≈ 台指期隔天 08:45 開盤）
報告：每筆平均、勝率、與 09:00 進的差（配對）、兩段 2010–2017／2018～
用法：python -X utf8 backtest/research_403_P日內進場.py
"""
import csv
import glob
import gzip
import importlib.util
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r148", os.path.join(HERE, "research_148_恐慌連續觸發.py"))
R148 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R148)

bars = {}
for f in sorted(glob.glob(os.path.join(HERE, "taiex_1min", "*.csv.gz"))):
    for r in csv.DictReader(gzip.open(f, "rt")):
        bars.setdefault(r["date"], {})[r["time"]] = (float(r["open"]), float(r["close"]))
days = sorted(bars)
nxt = {days[i]: days[i + 1] for i in range(len(days) - 1)}


def at(b, t):
    h, m = map(int, t.split(":"))
    for back in range(5):
        mm = h * 60 + m - back
        k = f"{mm // 60:02d}:{mm % 60:02d}"
        if k in b:
            return b[k][1]
    return None


sig = [x["d"] for x in R148.build() if x["sig"] and x["d"] in bars and x["d"] in nxt]
T = ("09:00", "09:15", "09:30", "10:00", "11:00", "13:25")
rows = []
for d in sig:
    b, nb = bars[d], bars[nxt[d]]
    if "09:00" not in b or "09:00" not in nb:
        continue
    out = nb["09:00"][0]
    px = {"09:00": b["09:00"][0]}
    for t in T[1:]:
        px[t] = at(b, t)
    if None in px.values():
        continue
    r = {t: out / px[t] - 1 for t in T}
    dip = px["09:30"] / px["09:00"] - 1
    r["條件"] = r["09:30"] if dip <= -0.01 else r["09:00"]
    rows.append((d, r, dip))
L = [f"研究 403：P 日內進場時點（{rows[0][0]}～{rows[-1][0]}，{len(rows)} 筆；出場＝隔天 09:00 開；指數代理、未扣成本）", ""]
for seg, lo, hi in (("全部", "2000", "2099"), ("2010–2017", "2010", "2018"), ("2018～", "2018", "2099")):
    sel = [r for d, r, _ in rows if lo <= d < hi]
    if not sel:
        continue
    L.append(f"【{seg}】{len(sel)} 筆")
    base = np.array([r["09:00"] for r in sel])
    for t in T + ("條件",):
        v = np.array([r[t] for r in sel])
        diff = v - base
        L.append(f"  {t:5s} 進：每筆 {v.mean():+.2%} 勝率 {np.mean(v > 0):.0%}" + ("" if t == "09:00" else f"｜比 09:00 {diff.mean():+.2%}（較好 {np.mean(diff > 0):.0%}）"))
dips = np.array([x for _, _, x in rows])
L.append(f"\n09:00→09:30 走勢：平均 {dips.mean():+.2%}、再跌 ≥1% 的 {np.mean(dips <= -0.01):.0%}、漲的 {np.mean(dips > 0):.0%}")
out = "\n".join(L)
print(out)
open(os.path.join(HERE, "結果_研究403_P日內進場.txt"), "w", encoding="utf-8").write(out + "\n")
