"""研究 413：日盤尾盤方向 → 當晚夜盤
X1＝加權 13:00→13:30（1 分 K，收盤集合競價含在內）；X2＝加權當天全天報酬；X3＝13:00→13:30 減去 09:30→13:00 方向（尾盤反轉）
Y＝台指期近月當晚夜盤（tx_daily_ohlc.csv session=night，夜盤歸到下一個交易日）開→收
檢定：相關、依 X 方向在 15:00 做多／空的每筆（扣 6 點）、置換 5,000 次；2017-05～2021／2022～
用法：python -X utf8 backtest/research_413_尾盤預測夜盤.py
"""
import csv
import glob
import gzip
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402

bars = {}
for f in sorted(glob.glob(os.path.join(HERE, "taiex_1min", "*.csv.gz"))):
    if int(os.path.basename(f)[:4]) < 2017:
        continue
    for r in csv.DictReader(gzip.open(f, "rt")):
        bars.setdefault(r["date"], {})[r["time"]] = float(r["close"])


def at(b, t):
    h, m = map(int, t.split(":"))
    for back in range(5):
        mm = h * 60 + m - back
        k = f"{mm // 60:02d}:{mm % 60:02d}"
        if k in b:
            return b[k]
    return None


# 夜盤：每個交易日 trade_day 的 night 列＝前一天 15:00 開始；取近月（量最大）
night = {}
for r in csv.DictReader(open(os.path.join(HERE, "tx_daily_ohlc.csv"))):
    if r["session"] != "night" or r["open"] in ("-", ""):
        continue
    v = float(r["volume"] or 0)
    d = r["date"]
    if d not in night or v > night[d][2]:
        night[d] = (float(r["open"]), float(r["close"]), v)
days = sorted(bt.DAYS)
nxt = {days[i]: days[i + 1] for i in range(len(days) - 1)}
prev = {days[i]: bt.PX[i - 1] for i in range(1, len(days))}
rows = []
for d in sorted(bars):
    b = bars[d]
    if d not in nxt or nxt[d] not in night or d not in prev:
        continue
    p930, p1300 = at(b, "09:29"), at(b, "12:59")
    pc = b.get("13:30") or at(b, "13:29")
    if None in (p930, p1300, pc):
        continue
    o, c, v = night[nxt[d]]
    if v < 1000:
        continue
    rows.append((d, pc / p1300 - 1, pc / prev[d] - 1, (pc / p1300 - 1) - (p1300 / p930 - 1), c / o - 1, o))
D = [r[0] for r in rows]
X1, X2, X3, Y, O = (np.array([r[i] for r in rows]) for i in (1, 2, 3, 4, 5))
cost = 6 / O
rng = np.random.default_rng(413)
L = [f"研究 413：日盤尾盤 → 當晚夜盤（{D[0]}～{D[-1]}，{len(D)} 晚；夜盤平均 {Y.mean():+.3%}、標準差 {Y.std():.2%}）", ""]
for name, x in (("尾盤 13:00→13:30", X1), ("全天報酬", X2), ("尾盤減盤中（反轉）", X3)):
    s = np.sign(x) * Y - cost
    perm = np.array([np.mean(np.sign(rng.permutation(x)) * Y) for _ in range(5000)])
    p = np.mean(perm >= np.mean(np.sign(x) * Y))
    seg = [np.mean(s[np.array([lo <= d < hi for d in D])]) for lo, hi in (("2017", "2022"), ("2022", "2099"))]
    L.append(f"【{name}】相關 {np.corrcoef(x, Y)[0, 1]:+.3f}｜順向做（15:00 進、05:00 出、扣 6 點）每筆 {s.mean():+.3%} 勝率 {np.mean(s > 0):.0%}｜置換 p {p:.3f}｜兩段 {seg[0]:+.3%}／{seg[1]:+.3%}")
    q = np.quantile(np.abs(x), 0.8)
    m = np.abs(x) >= q
    L.append(f"   |x| 前 20%：{m.sum()} 晚 順向每筆 {s[m].mean():+.3%} 勝率 {np.mean(s[m] > 0):.0%}")
out = "\n".join(L)
print(out)
open(os.path.join(HERE, "結果_研究413_尾盤預測夜盤.txt"), "w", encoding="utf-8").write(out + "\n")
