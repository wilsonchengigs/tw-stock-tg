"""研究 277：財報公布截止日前後的加權指數
截止日（法定最後公布日；2013 起 3/31、5/15、8/14、11/14；2012 前 4/30、8/31、10/31），取當天或之前最後一個交易日 C
窗格（做多加權，收盤對收盤，扣來回 6 點）：PRE 10、PRE 5（截止前，財報陸續公布期間）、POST 5、POST 10（全部公布完之後）
對照、家族檢定同研究 274（同波動度、錨點平移 ±40～200 日、最小 p 值法、雙尾）；兩段 1999–2012／2013～
用法：python -X utf8 backtest/research_277_財報截止日.py
"""
import datetime as dt
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402

i0 = next(i for i, d in enumerate(bt.DAYS) if d >= "1998-06-01")
DAYS = bt.DAYS[i0:]
PX = np.array(bt.PX[i0:])
N = len(DAYS)
r1 = np.r_[0.0, PX[1:] / PX[:-1] - 1]
vol = np.array([r1[max(1, k - 19):k + 1].std() if k >= 21 else np.nan for k in range(N)])
qs = np.nanquantile(vol, np.linspace(0, 1, 11)[1:-1])
VDEC = np.where(np.isnan(vol), -1, np.searchsorted(qs, np.nan_to_num(vol)))
POS = {d: k for k, d in enumerate(DAYS)}

import bisect  # noqa: E402

# 財報公布截止日：2013 起（IFRS）年報 3/31、Q1 5/15、Q2 8/14、Q3 11/14；2012 以前 年報 4/30、Q1 4/30（與年報同天，只算一次）、半年報 8/31、Q3 10/31
DL = []
for y in range(1999, 2027):
    ds = ([f"{y}-03-31", f"{y}-05-15", f"{y}-08-14", f"{y}-11-14"] if y >= 2013
          else [f"{y}-04-30", f"{y}-08-31", f"{y}-10-31"])
    for d in ds:
        k = bisect.bisect_right(DAYS, d) - 1  # 截止日當天或之前最後一個交易日
        if 40 < k < N - 12:
            DL.append(DAYS[k])
CALLS = [(d, 0.0) for d in DL]
C_IDX = np.array([POS[d] for d, _ in CALLS])


def win(a, b):
    return PX[b] / PX[a] - 1 - 6.0 / PX[a]


REACT = np.array([PX[k + 1] / PX[k] - 1 if k + 1 < N else np.nan for k in range(N)])
TESTS = [("PRE 10 截止前", -10, 0, None), ("PRE 5", -5, 0, None), ("POST 5 截止後", 0, 5, None),
         ("POST 10", 0, 10, None)]
CTRL = {}
for _, a, b, _ in TESTS:
    h = b - a
    if h not in CTRL:
        x = np.array([win(k, k + h) for k in range(30, N - h)])
        dec = VDEC[30:N - h]
        CTRL[h] = {d: x[dec == d].mean() for d in range(10)}


def evaluate(anchors, mask=None):
    res = []
    for _, a, b, cond in TESTS:
        ks = [k for k in anchors if k + a >= 30 and k + b < N and (mask is None or mask(k))
              and (cond is None or REACT[k] <= cond)]
        if not ks:
            res.append((0, np.nan, np.nan, np.nan))
            continue
        x = np.array([win(k + a, k + b) for k in ks])
        c = np.array([CTRL[b - a][max(VDEC[k + a], 0)] for k in ks])
        res.append((len(x), x.mean(), (x - c).mean(), (x > 0).mean()))
    return res


obs = evaluate(C_IDX)
s1 = evaluate(C_IDX, lambda k: DAYS[k] < "2013-01-01")
s2 = evaluate(C_IDX, lambda k: DAYS[k] >= "2013-01-01")
rng = np.random.default_rng(277)
S = 1000
null = np.zeros((S, len(TESTS)))
for s in range(S):
    off = int(rng.integers(40, 201)) * (1 if rng.random() < 0.5 else -1)
    anc = C_IDX + off
    anc = anc[(anc > 40) & (anc < N - 10)]
    null[s] = [r[2] for r in evaluate(anc)]
ob = np.array([r[2] for r in obs])
# 雙尾：看絕對值（多空都算）
pe = np.array([(np.sum(np.abs(null[:, j]) >= abs(ob[j])) + 1) / (S + 1) for j in range(len(TESTS))])
pmin = np.array([min(np.sum(np.abs(null[:, j]) >= abs(null[s, j])) / S for j in range(len(TESTS))) for s in range(S)])

out = [f"研究 277：財報公布截止日前後（截止日 {len(CALLS)} 次，{CALLS[0][0]}～{CALLS[-1][0]}；做多加權、扣 6 點；同波動度對照；雙尾）", ""]
out.append(f"{'窗格':<18s} | 全期 筆數 每筆 超額 勝率 | 單一p 家族p | 1999–2012 筆 每筆 超額 | 2013～ 筆 每筆 超額")
for j, (nm, _, _, _) in enumerate(TESTS):
    n, m, e, w = obs[j]
    fam = (np.sum(pmin <= pe[j]) + 1) / (S + 1)
    out.append(f"{nm:<18s} | {n:3d} {m:+6.2%} {e:+6.2%} {w:4.0%} | {pe[j]:.3f} {fam:.3f} | {s1[j][0]:2d} {s1[j][1]:+6.2%} {s1[j][2]:+6.2%} | {s2[j][0]:2d} {s2[j][1]:+6.2%} {s2[j][2]:+6.2%}")
out.append("")
out.append("截止日（交易日）：" + "、".join(d for d, _ in CALLS[-12:]) + "…（最近 12 個）")
txt = "\n".join(out)
print(txt)
open(os.path.join(HERE, "結果_研究277_財報截止日.txt"), "w", encoding="utf-8").write(txt + "\n")
