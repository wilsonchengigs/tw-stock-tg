"""研究 212：日內動能（Gao, Han, Li, Zhou 2018：開盤第一個半小時的報酬預測最後半小時）在台股
資料：加權指數 1 分 K（taiex_1min/*.csv.gz，證交所 MI_5MINS_INDEX），前一天收盤取 bt.PX
每天：r1＝09:30 收 ÷ 昨收 − 1（含跳空）；r1x＝09:30 ÷ 09:00 K 棒開盤 − 1（不含跳空）；r12＝13:00 ÷ 12:30 − 1；
      rL＝13:30 收盤 ÷ 13:00 − 1（最後半小時，13:25～13:30 是收盤集合競價）
檢定：rL 對 r1、r1x、r12 的相關與 OLS t；「依 r1 方向在 13:00 進、收盤出」的每筆報酬；
      依 |r1| 大小分組；置換（打亂日期 5,000 次）p；逐年；成本：台指期每邊約 2 點≈0.006%（2025 指數 2 萬點）
用法：python -X utf8 backtest/research_212_日內動能.py
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

pclose = dict(zip(bt.DAYS, bt.PX))
prev = {bt.DAYS[i]: bt.PX[i - 1] for i in range(1, len(bt.DAYS))}
bars = {}
for f in sorted(glob.glob(os.path.join(HERE, "taiex_1min", "*.csv.gz"))):
    for r in csv.DictReader(gzip.open(f, "rt")):
        bars.setdefault(r["date"], {})[r["time"]] = (float(r["open"]), float(r["close"]))


def at(b, t):
    """t 這一分鐘的收盤（沒有就往前找）"""
    h, m = map(int, t.split(":"))
    for back in range(0, 5):
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
    p930, p1230, p1300 = at(b, "09:29"), at(b, "12:29"), at(b, "12:59")
    pc = b.get("13:30", (None, None))[1] or at(b, "13:29")
    if None in (p930, p1230, p1300, pc):
        continue
    rows.append((d, p930 / prev[d] - 1, p930 / b["09:00"][0] - 1, p1300 / p1230 - 1, pc / p1300 - 1))
D = [r[0] for r in rows]
r1, r1x, r12, rL = (np.array([r[i] for r in rows]) for i in range(1, 5))
n = len(D)
COST = 0.00012  # 來回約 4 點／2 萬點


def ols_t(y, x):
    X = np.c_[np.ones_like(x), x]
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ b
    se = np.sqrt(e.var(ddof=2) / ((x - x.mean()) ** 2).sum())
    return b[1], b[1] / se


rng = np.random.default_rng(212)
L = [f"研究 212：日內動能（{D[0]}～{D[-1]}，{n} 天）", f"最後半小時 rL 平均 {rL.mean():+.3%}、標準差 {rL.std():.3%}；r1 標準差 {r1.std():.2%}", ""]
for name, x in (("r1 前 30 分（含跳空）", r1), ("r1x 前 30 分（不含跳空）", r1x), ("r12 12:30～13:00", r12)):
    beta, t = ols_t(rL, x)
    s = np.sign(x) * rL
    perm = np.array([np.mean(np.sign(rng.permutation(x)) * rL) for _ in range(5000)])
    L.append(f"【{name}】相關 {np.corrcoef(x, rL)[0, 1]:+.3f}、β {beta:+.4f}（t {t:+.2f}）")
    L.append(f"  依方向 13:00 進、收盤出：每筆 {s.mean():+.4%}（扣成本 {s.mean() - COST:+.4%}）勝率 {np.mean(s > 0):.0%}  置換 p {np.mean(perm >= s.mean()):.3f}")
    q = np.quantile(np.abs(x), [0.5, 0.8])
    for lab, m in (("|x| 小半", np.abs(x) < q[0]), ("|x| 前 50～20%", (np.abs(x) >= q[0]) & (np.abs(x) < q[1])), ("|x| 前 20%", np.abs(x) >= q[1])):
        L.append(f"    {lab}：{m.sum()} 天 每筆 {s[m].mean():+.4%} 勝率 {np.mean(s[m] > 0):.0%}")
    yrs = sorted(set(d[:4] for d in D))
    L.append("    逐年：" + "  ".join(f"{y}:{np.mean([v for d, v in zip(D, s) if d[:4] == y]):+.3%}" for y in yrs))
both = np.sign(r1) == np.sign(r12)
s = np.sign(r1) * rL
L.append(f"\n【r1 與 r12 同向】{both.sum()} 天 每筆 {s[both].mean():+.4%} 勝率 {np.mean(s[both] > 0):.0%}；不同向 {(~both).sum()} 天 {s[~both].mean():+.4%}")
out = "\n".join(L) + "\n"
print(out)
open(os.path.join(HERE, "結果_研究212_日內動能.txt"), "w", encoding="utf-8").write(out)
