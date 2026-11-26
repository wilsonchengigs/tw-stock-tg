"""研究 264：季底效應（3／6／9 月最後交易日；年底已在研究 262）
窗格：PRE 3（L−3 收盤買、L 收盤出）、OVER 3,4（L−3 買、L+5 收盤出）、POST 4（L 收盤買、L+5 出）、PRE 7（L−7 買、L 出）、OVER 7,4
每季另拆；同波動度對照、錨點平移 ±40～200 交易日 1,000 次（但平移後若落到其他季底附近仍算，偏保守）、最小 p；兩段
用法：python -X utf8 backtest/research_264_季底效應.py
"""
import datetime as dt
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_261_春節效應 as R  # noqa: E402

DAYS, PX, N, win, CTRL, VDEC = R.DAYS, R.PX, R.N, R.win, R.CTRL, R.VDEC
Q = []
for k in range(N - 1):
    a, b = dt.date.fromisoformat(DAYS[k]), dt.date.fromisoformat(DAYS[k + 1])
    if DAYS[k] >= "1998-01-01" and a.month in (3, 6, 9) and b.month != a.month:
        Q.append(k)
Q = np.array(Q)
TESTS = [("PRE 3", -3, 0), ("OVER 3,4", -3, 5), ("POST 4", 0, 5), ("PRE 7", -7, 0), ("OVER 7,4", -7, 5)]
for _, a, b in TESTS:
    h = b - a
    if h not in CTRL:
        x = np.array([win(k, k + h) for k in range(30, N - h)])
        dec = VDEC[30:N - h]
        CTRL[h] = {d: x[dec == d].mean() for d in range(10)}


def ev(anc, a, b, mask=None):
    ks = [k for k in anc if k + a >= 30 and k + b < N and (mask is None or mask(k))]
    x = np.array([win(k + a, k + b) for k in ks])
    c = np.array([CTRL[b - a][max(VDEC[k + a], 0)] for k in ks])
    return len(x), x.mean(), (x - c).mean(), (x > 0).mean()


def evaluate(anc, mask=None):
    return [ev(anc, a, b, mask) for _, a, b in TESTS]


obs = evaluate(Q)
s1 = evaluate(Q, lambda k: DAYS[k] <= "2012-12-31")
s2 = evaluate(Q, lambda k: DAYS[k] > "2012-12-31")
rng = np.random.default_rng(264)
S = 1000
null = np.zeros((S, len(TESTS)))
for s in range(S):
    off = int(rng.integers(40, 201)) * (1 if rng.random() < 0.5 else -1)
    anc = Q + off
    null[s] = [r[2] for r in evaluate(anc[(anc > 40) & (anc < N - 10)])]
ob = np.array([r[2] for r in obs])
pe = np.array([(np.sum(null[:, j] >= ob[j]) + 1) / (S + 1) for j in range(len(TESTS))])
pmin = np.array([min(np.sum(null[:, j] >= null[s, j]) / S for j in range(len(TESTS))) for s in range(S)])
out = [f"研究 264：季底（3／6／9 月）效應 {len(Q)} 次；做多加權、扣 6 點、同波動度對照", ""]
out.append("窗格      | 全期 筆數 每筆 超額 勝率 | 單一p 家族p | 1998–2012 每筆 超額 | 2013～ 每筆 超額")
for j, (nm, _, _) in enumerate(TESTS):
    n, m, e, w = obs[j]
    fam = (np.sum(pmin <= pe[j]) + 1) / (S + 1)
    out.append(f"{nm:<9s}| {n:3d} {m:+6.2%} {e:+6.2%} {w:4.0%} | {pe[j]:.3f} {fam:.3f} | {s1[j][0]:3d} {s1[j][1]:+6.2%} {s1[j][2]:+6.2%} | {s2[j][0]:3d} {s2[j][1]:+6.2%} {s2[j][2]:+6.2%}")
out.append("")
for mth in ("03", "06", "09"):
    sub = np.array([k for k in Q if DAYS[k][5:7] == mth])
    r = evaluate(sub)
    out.append(f"{mth} 月：" + "、".join(f"{nm} {x[1]:+.2%}（超額 {x[2]:+.2%}）" for (nm, _, _), x in zip(TESTS, r)))
txt = "\n".join(out)
print(txt)
open(os.path.join(HERE, "結果_研究264_季底效應.txt"), "w", encoding="utf-8").write(txt + "\n")
