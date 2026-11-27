"""研究 444：P 恐慌做多依觸發當天台指 VIX 調倍數（接 443）
基準：研究 407 長歷史（主策略 1.7x＋P 1x＋D 0.5x，2002～）；P 每筆損益記在出場日（R.padd，1x）
變體（VIX＝觸發當天 vixtwn，用前一天值避免偷看）：A <25 → 0.5x；B <25 → 0x；C <25 0.5／25～35 1／≥35 1.5x；D 依 250 日滾動分位 <30% → 0.5x
與同平均曝險固定倍數比；VIX 序列環狀平移 300 次、家族最小 p
用法：python -X utf8 backtest/research_444_P依VIX倍數.py
"""
import csv
import io
import contextlib
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
with contextlib.redirect_stdout(io.StringIO()):
    import research_407_實際配置長歷史 as R  # noqa: E402
vx = {r["date"]: float(r["vix"]) for r in csv.DictReader(open(os.path.join(HERE, "vixtwn.csv")))}
D = R.D
V = np.array([vx.get(d, np.nan) for d in D])
for k in range(1, len(V)):
    if np.isnan(V[k]):
        V[k] = V[k - 1]
Vp = np.r_[np.nan, V[:-1]]  # 前一天
pq = np.array([np.mean(Vp[max(0, k - 250):k] < Vp[k]) if k > 250 else 0.5 for k in range(len(Vp))])
# P 進場日＝出場日的前一天（padd 記在 D+1）；倍數用進場日前一天 VIX
idxp = np.where(R.padd != 0)[0]
base_r = R.main + R.dadd


def scale_of(name, vv, qq):
    if name == "A":
        return np.where(vv < 25, 0.5, 1.0)
    if name == "B":
        return np.where(vv < 25, 0.0, 1.0)
    if name == "C":
        return np.where(vv < 25, 0.5, np.where(vv < 35, 1.0, 1.5))
    return np.where(qq < 0.3, 0.5, 1.0)


def run(name, vv, qq):
    s = np.ones(len(D))
    sc = scale_of(name, vv, qq)
    for k in idxp:
        s[k] = sc[k - 1] if k >= 1 and not np.isnan(vv[k - 1]) else 1.0
    r = base_r + R.padd * s
    eq = np.cumprod(1 + r)
    return eq[-1] ** (R.bt.TD / len(r)) - 1, (eq / np.maximum.accumulate(eq) - 1).min(), np.mean(s[idxp])


def fixed(u):
    r = base_r + R.padd * u
    eq = np.cumprod(1 + r)
    return eq[-1] ** (R.bt.TD / len(r)) - 1


c0 = run("none", Vp, pq) if False else None
L = ["研究 444：P 依台指 VIX 調倍數（基準＝研究 407：主策略 1.7x＋P 1x＋D 0.5x，2002～）", f"現行 P 1x：{fixed(1.0):.1%}", ""]
rng = np.random.default_rng(444)
shifts = rng.integers(250, len(D) - 250, 300)
names = ["A", "B", "C", "D"]
real = {}
null = np.zeros((300, 4))
for j, nm in enumerate(names):
    cg, mdd, avg = run(nm, Vp, pq)
    real[nm] = cg
    for si, s_ in enumerate(shifts):
        null[si, j] = run(nm, np.roll(Vp, s_), np.roll(pq, s_))[0]
    L.append(f"{nm}：{cg:.1%}／{mdd:.1%}｜平均倍數 {avg:.2f}｜同曝險固定 {fixed(avg):.1%}｜比同曝險 {cg - fixed(avg):+.2%}")
rv = np.array([real[n] for n in names])
single = (1 + (null >= rv).sum(axis=0)) / 301
ranks = np.array([[(1 + np.sum(null[:, j] >= null[s, j])) / 301 for j in range(4)] for s in range(300)])
minp = ranks.min(axis=1)
L.append("\n平移安慰劑：" + "、".join(f"{n} 單組 p {single[j]:.3f} 家族 p {(1 + np.sum(minp <= single[j])) / 301:.3f}" for j, n in enumerate(names)))
out = "\n".join(L)
print(out)
open(os.path.join(HERE, "結果_研究444_P依VIX倍數.txt"), "w", encoding="utf-8").write(out + "\n")
