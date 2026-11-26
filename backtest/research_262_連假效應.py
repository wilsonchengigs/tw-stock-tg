"""研究 262：春節以外的連假前後效應＋年底／年初
連假錨點 L＝下一個交易日相隔 ≥4 個日曆天的交易日（一般週末是 3 天），排除 1、2 月 ≥6 天的春節（研究 261）
年底錨點 L＝每年 12 月最後一個交易日
窗格同研究 261：PRE p（L−p 收盤買、L 收盤出）、OVER p,q（L−p 買、R+q 收盤出）、POST q（R 收盤買、R+q 出）
對照、家族（錨點一起平移 ±40～200 交易日 1,000 次、最小 p）、兩段同研究 261
用法：python -X utf8 backtest/research_262_連假效應.py
"""
import datetime as dt
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_261_春節效應 as R  # noqa: E402

DAYS, PX, N, win, CTRL, VDEC = R.DAYS, R.PX, R.N, R.win, R.CTRL, R.VDEC
HOL, YE = [], []
for k in range(N - 1):
    a, b = dt.date.fromisoformat(DAYS[k]), dt.date.fromisoformat(DAYS[k + 1])
    gap = (b - a).days
    if DAYS[k] < "1998-01-01":
        continue
    if gap >= 4 and not (gap >= 6 and a.month in (1, 2)):
        HOL.append(k)
    if a.month == 12 and b.year > a.year:
        YE.append(k)
HOL, YE = np.array(HOL), np.array(YE)
W = [("PRE 1", -1, 0), ("PRE 3", -3, 0), ("OVER 0,0", 0, 1), ("OVER 3,4", -3, 5), ("POST 3", 1, 4)]
TESTS = [("連假", nm, a, b) for nm, a, b in W] + [("年底", "PRE 3", -3, 0), ("年底", "OVER 3,4", -3, 5)]
for _, _, a, b in TESTS:
    h = b - a
    if h not in CTRL:
        x = np.array([win(k, k + h) for k in range(30, N - h)])
        dec = VDEC[30:N - h]
        CTRL[h] = {d: x[dec == d].mean() for d in range(10)}


def ev(anchors, a, b, mask=None):
    ks = [k for k in anchors if k + a >= 30 and k + b < N and (mask is None or mask(k))]
    x = np.array([win(k + a, k + b) for k in ks])
    c = np.array([CTRL[b - a][max(VDEC[k + a], 0)] for k in ks])
    return len(x), x.mean(), (x - c).mean(), (x > 0).mean()


def evaluate(hol, ye, mask=None):
    return [ev(hol if g == "連假" else ye, a, b, mask) for g, _, a, b in TESTS]


obs = evaluate(HOL, YE)
s1 = evaluate(HOL, YE, lambda k: DAYS[k] <= "2012-12-31")
s2 = evaluate(HOL, YE, lambda k: DAYS[k] > "2012-12-31")
rng = np.random.default_rng(262)
S = 1000
null = np.zeros((S, len(TESTS)))
for s in range(S):
    off = int(rng.integers(40, 201)) * (1 if rng.random() < 0.5 else -1)
    sh = lambda x: x[(x + off > 40) & (x + off < N - 10)] + off  # noqa: E731
    null[s] = [r[2] for r in evaluate(sh(HOL), sh(YE))]
ob = np.array([r[2] for r in obs])
pe = np.array([(np.sum(null[:, j] >= ob[j]) + 1) / (S + 1) for j in range(len(TESTS))])
pmin = np.array([min(np.sum(null[:, j] >= null[s, j]) / S for j in range(len(TESTS))) for s in range(S)])
out = [f"研究 262：春節以外連假（{len(HOL)} 次）與年底（{len(YE)} 次）前後效應；做多加權、扣 6 點、同波動度對照", ""]
out.append("群組 窗格     | 全期 筆數 每筆 超額 勝率 | 單一p 家族p | 1998–2012 每筆 超額 | 2013～ 每筆 超額")
for j, (g, nm, _, _) in enumerate(TESTS):
    n, m, e, w = obs[j]
    fam = (np.sum(pmin <= pe[j]) + 1) / (S + 1)
    out.append(f"{g} {nm:<9s}| {n:3d} {m:+6.2%} {e:+6.2%} {w:4.0%} | {pe[j]:.3f} {fam:.3f} | {s1[j][0]:3d} {s1[j][1]:+6.2%} {s1[j][2]:+6.2%} | {s2[j][0]:3d} {s2[j][1]:+6.2%} {s2[j][2]:+6.2%}")
# 依月份拆連假 OVER 0,0 與 PRE 3
out.append("")
for nm, a, b in (("PRE 3", -3, 0), ("OVER 3,4", -3, 5)):
    by = {}
    for k in HOL:
        if k + b < N:
            by.setdefault(DAYS[k][5:7], []).append(win(k + a, k + b))
    out.append(f"連假 {nm} 依月份：" + "、".join(f"{m}月 {len(v)}次 {np.mean(v):+.2%}" for m, v in sorted(by.items())))
txt = "\n".join(out)
print(txt)
open(os.path.join(HERE, "結果_研究262_連假效應.txt"), "w", encoding="utf-8").write(txt + "\n")
