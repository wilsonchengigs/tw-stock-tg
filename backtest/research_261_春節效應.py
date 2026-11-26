"""研究 261：春節（農曆年）封關前／開紅盤後效應
春節＝1、2 月中相隔 ≥6 個日曆天的休市；L＝封關日（最後交易日）、R＝開紅盤日。1998～2026 共 29 次
窗格（做多加權，收盤對收盤，扣來回 6 點；不計台指期正價差收益＝保守）：
  PRE p    L−p 收盤買、L 收盤出（不抱過年）p＝1／3／5
  OVER p,q L−p 收盤買、R+q 收盤出（抱過年）  (p,q)＝(0,0)、(0,4)、(3,0)、(3,4)
  POST q   R 收盤買、R+q 收盤出               q＝3／5
對照：同天數、同前 20 日波動十分位的所有窗格平均；超額＝事件 − 對照
家族：9 檢定，所有事件錨點一起平移 40～200 個交易日（1,000 次），最小 p 值法；兩段 1998–2012／2013～
用法：python -X utf8 backtest/research_261_春節效應.py
"""
import datetime as dt
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402

i0 = next(i for i, d in enumerate(bt.DAYS) if d >= "1997-10-01")
DAYS = bt.DAYS[i0:]
PX = np.array(bt.PX[i0:])
N = len(DAYS)
r1 = np.r_[0.0, PX[1:] / PX[:-1] - 1]
vol = np.array([r1[max(1, k - 19):k + 1].std() if k >= 21 else np.nan for k in range(N)])
qs = np.nanquantile(vol, np.linspace(0, 1, 11)[1:-1])
VDEC = np.where(np.isnan(vol), -1, np.searchsorted(qs, np.nan_to_num(vol)))

L_IDX = []
for k in range(N - 1):
    a, b = dt.date.fromisoformat(DAYS[k]), dt.date.fromisoformat(DAYS[k + 1])
    if (b - a).days >= 6 and a.month in (1, 2) and DAYS[k] >= "1998-01-01":
        L_IDX.append(k)
L_IDX = np.array(L_IDX)

TESTS = [("PRE 1", -1, 0), ("PRE 3", -3, 0), ("PRE 5", -5, 0),
         ("OVER 0,0", 0, 1), ("OVER 0,4", 0, 5), ("OVER 3,0", -3, 1), ("OVER 3,4", -3, 5),
         ("POST 3", 1, 4), ("POST 5", 1, 6)]  # (名稱, 進場相對 L, 出場相對 L)


def win(a, b):
    return PX[b] / PX[a] - 1 - 6.0 / PX[a]


CTRL = {}
for _, a, b in TESTS:
    h = b - a
    if h in CTRL:
        continue
    x = np.array([win(k, k + h) for k in range(30, N - h)])
    dec = VDEC[30:N - h]
    CTRL[h] = {d: x[dec == d].mean() for d in range(10)}


def evaluate(anchors, mask=None):
    res = []
    for _, a, b in TESTS:
        ks = [k for k in anchors if k + a >= 30 and k + b < N and (mask is None or mask(k))]
        x = np.array([win(k + a, k + b) for k in ks])
        c = np.array([CTRL[b - a][max(VDEC[k + a], 0)] for k in ks])
        res.append((len(x), x.mean(), (x - c).mean(), (x > 0).mean()))
    return res


obs = evaluate(L_IDX)
s1 = evaluate(L_IDX, lambda k: DAYS[k] <= "2012-12-31")
s2 = evaluate(L_IDX, lambda k: DAYS[k] > "2012-12-31")
rng = np.random.default_rng(261)
S = 1000
null = np.zeros((S, len(TESTS)))
for s in range(S):
    off = int(rng.integers(40, 201)) * (1 if rng.random() < 0.5 else -1)
    anc = L_IDX + off
    anc = anc[(anc > 40) & (anc < N - 10)]
    null[s] = [r[2] for r in evaluate(anc)]
ob = np.array([r[2] for r in obs])
pe = np.array([(np.sum(null[:, j] >= ob[j]) + 1) / (S + 1) for j in range(len(TESTS))])
pmin = np.array([min(np.sum(null[:, j] >= null[s, j]) / S for j in range(len(TESTS))) for s in range(S)])

out = [f"研究 261：春節封關前／開紅盤後（{len(L_IDX)} 次，{DAYS[L_IDX[0]]}～{DAYS[L_IDX[-1]]}；做多加權、扣 6 點；同波動度對照）", ""]
out.append(f"{'窗格':<10s} | 全期 筆數 每筆 超額 勝率 | 單一p 家族p | 1998–2012 每筆 超額 | 2013～ 每筆 超額")
for j, (nm, _, _) in enumerate(TESTS):
    n, m, e, w = obs[j]
    fam = (np.sum(pmin <= pe[j]) + 1) / (S + 1)
    out.append(f"{nm:<10s} | {n:3d} {m:+6.2%} {e:+6.2%} {w:4.0%} | {pe[j]:.3f} {fam:.3f} | {s1[j][0]:2d} {s1[j][1]:+6.2%} {s1[j][2]:+6.2%} | {s2[j][0]:2d} {s2[j][1]:+6.2%} {s2[j][2]:+6.2%}")
out.append("")
out.append("逐年 PRE 3／開紅盤當天（L→R）：" + "、".join(f"{DAYS[k][:4]} {win(k - 3, k):+.1%}/{win(k, k + 1):+.1%}" for k in L_IDX))
txt = "\n".join(out)
print(txt)
open(os.path.join(HERE, "結果_研究261_春節效應.txt"), "w", encoding="utf-8").write(txt + "\n")
