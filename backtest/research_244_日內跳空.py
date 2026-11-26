"""研究 244：日內跳空回補還是延續（加權 1 分 K，taiex_1min/；資料仍在往回補，可重跑）
每天：跳空＝09:00 K 棒開盤 ÷ 昨收 − 1（台指期 08:45 開盤時已大致知道）；
報酬：09:05 收→13:30、09:30 收→13:30、09:00 開→09:30（開盤後 30 分鐘）
分組：跳空 ≤-1.5%、-1.5～-0.5%、±0.5%、+0.5～+1.5%、≥+1.5%；每組平均、t、勝率（依跳空方向反向＝回補為正）、逐年
成本：台指期當沖來回約 4 點（2 萬點時 0.02%；期交稅當沖減半已含）
用法：python -X utf8 backtest/research_244_日內跳空.py
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

prev = {bt.DAYS[i]: bt.PX[i - 1] for i in range(1, len(bt.DAYS))}
bars = {}
for f in sorted(glob.glob(os.path.join(HERE, "taiex_1min", "*.csv.gz"))):
    for r in csv.DictReader(gzip.open(f, "rt")):
        bars.setdefault(r["date"], {})[r["time"]] = (float(r["open"]), float(r["close"]))


def at(b, t):
    h, m = map(int, t.split(":"))
    for back in range(5):
        mm = h * 60 + m - back
        k = f"{mm // 60:02d}:{mm % 60:02d}"
        if k in b:
            return b[k][1]
    return None


rows = []
for d in sorted(bars):
    b = bars[d]
    if d not in prev or "09:00" not in b:
        continue
    o, p905, p930 = b["09:00"][0], at(b, "09:04"), at(b, "09:29")
    cl = b.get("13:30", (None, None))[1] or at(b, "13:29")
    if None in (p905, p930, cl):
        continue
    rows.append((d, o / prev[d] - 1, cl / p905 - 1, cl / p930 - 1, p930 / o - 1))
D = [r[0] for r in rows]
gp, r905, r930, r_open = (np.array([r[i] for r in rows]) for i in range(1, 5))
L = [f"研究 244：日內跳空（{D[0]}～{D[-1]}，{len(D)} 天；正＝回補方向〔跳空下跌後上漲、跳空上漲後下跌〕）", ""]
for lab, lo, hi in (("≤-1.5%", -9, -0.015), ("-1.5～-0.5%", -0.015, -0.005), ("±0.5%", -0.005, 0.005), ("+0.5～+1.5%", 0.005, 0.015), ("≥+1.5%", 0.015, 9)):
    m = (gp > lo) & (gp <= hi)
    sgn = -np.sign(gp[m]) if lab != "±0.5%" else np.ones(m.sum())
    L.append(f"跳空 {lab}：{m.sum()} 天")
    for nm, x in (("09:00→09:30", r_open), ("09:05→收盤", r905), ("09:30→收盤", r930)):
        v = sgn * x[m]
        t = v.mean() / (v.std() / np.sqrt(len(v))) if len(v) > 2 else np.nan
        L.append(f"  {nm}：回補方向平均 {v.mean():+.3%}（t {t:+.2f}）勝率 {np.mean(v > 0):.0%}" + ("" if lab != "±0.5%" else "（此組為原始方向）"))
big = np.abs(gp) >= 0.01
v = -np.sign(gp[big]) * r905[big]
L.append(f"\n|跳空| ≥1%：{big.sum()} 天，09:05 反向進、收盤出 每筆 {v.mean():+.3%}、扣 0.02% 後 {v.mean() - 0.0002:+.3%}、勝率 {np.mean(v > 0):.0%}")
L.append("  逐年：" + "  ".join(f"{y}:{np.mean([x for d, x in zip(np.array(D)[big], v) if d[:4] == y]):+.2%}({sum(1 for d in np.array(D)[big] if d[:4] == y)})" for y in sorted(set(d[:4] for d in D))))
out = "\n".join(L) + "\n"
print(out)
open(os.path.join(HERE, "結果_研究244_日內跳空.txt"), "w", encoding="utf-8").write(out)
