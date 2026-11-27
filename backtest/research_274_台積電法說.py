"""研究 274：台積電法說會前後的加權指數效應
法說日 C（盤後召開）：2012～ 每年 1／4／7／10 月，取當月 8～24 日的週四中「隔天 2330 成交量 ÷ 前 20 日均量」最大的那天（重建，非官方日曆）
  R274_MODE=thu3：改用當月第三個週四（台積電近年多數在第三個週四）當穩健性檢查
窗格（做多加權，收盤對收盤，扣來回 6 點）：
  PRE 5   C−5 收盤 → C 收盤（法說前卡位）
  PRE 1   C−1 收盤 → C 收盤
  REACT   C 收盤 → C+1 收盤（法說後第一天）
  POST 5  C+1 收盤 → C+6 收盤（法說後續漂移）
  REV 5   POST 5 的條件版：REACT ≤ -1% 時做多（跌後反彈）
對照：同天數、同前 20 日波動十分位所有窗格平均；家族：所有錨點一起平移 ±40～200 交易日 1,000 次（最小 p 值法）；兩段 2012–2018／2019～
用法：python -X utf8 backtest/research_274_台積電法說.py
"""
import datetime as dt
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402

i0 = next(i for i, d in enumerate(bt.DAYS) if d >= "2005-01-01")
DAYS = bt.DAYS[i0:]
PX = np.array(bt.PX[i0:])
N = len(DAYS)
r1 = np.r_[0.0, PX[1:] / PX[:-1] - 1]
vol = np.array([r1[max(1, k - 19):k + 1].std() if k >= 21 else np.nan for k in range(N)])
qs = np.nanquantile(vol, np.linspace(0, 1, 11)[1:-1])
VDEC = np.where(np.isnan(vol), -1, np.searchsorted(qs, np.nan_to_num(vol)))
POS = {d: k for k, d in enumerate(DAYS)}

g = json.load(open(os.path.join(HERE, "2330.json")))
q = g["indicators"]["quote"][0]
TS = {}
for t, v, c in zip(g["timestamp"], q["volume"], q["close"]):
    if v and c:
        TS[(dt.datetime.utcfromtimestamp(t) + dt.timedelta(hours=8)).strftime("%Y-%m-%d")] = (v, c)
SD = sorted(TS)
SV = np.array([TS[d][0] for d in SD], float)
SPOS = {d: k for k, d in enumerate(SD)}

CALLS = []
for y in range(2012, 2027):
    for m in (1, 4, 7, 10):
        best = None
        for day in range(8, 25):
            d = dt.date(y, m, day)
            ds = d.isoformat()
            if d.weekday() != 3 or ds not in SPOS or ds not in POS:
                continue
            j = SPOS[ds]
            if j < 21 or j + 1 >= len(SD):
                continue
            ratio = SV[j + 1] / SV[j - 20:j].mean()
            if best is None or ratio > best[1]:
                best = (ds, ratio)
        if os.environ.get("R274_MODE") == "thu3":  # 替代：當月第三個週四（若休市取前一交易日）
            d0 = dt.date(y, m, 1)
            d3 = d0 + dt.timedelta(days=(3 - d0.weekday()) % 7 + 14)
            ds = d3.isoformat()
            while ds not in POS and d3.day > 1:
                d3 -= dt.timedelta(days=1)
                ds = d3.isoformat()
            j = SPOS.get(ds)
            best = (ds, SV[j + 1] / SV[j - 20:j].mean() if j and j + 1 < len(SD) else float("nan")) if ds in POS else None
        if best and POS[best[0]] + 7 < N:
            CALLS.append(best)
C_IDX = np.array([POS[d] for d, _ in CALLS])


def win(a, b):
    return PX[b] / PX[a] - 1 - 6.0 / PX[a]


REACT = np.array([PX[k + 1] / PX[k] - 1 if k + 1 < N else np.nan for k in range(N)])
TESTS = [("PRE 5", -5, 0, None), ("PRE 1", -1, 0, None), ("REACT", 0, 1, None),
         ("POST 5", 1, 6, None), ("REV 5（法說後跌≥1%）", 1, 6, -0.01)]
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
s1 = evaluate(C_IDX, lambda k: DAYS[k] < "2019-01-01")
s2 = evaluate(C_IDX, lambda k: DAYS[k] >= "2019-01-01")
rng = np.random.default_rng(274)
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

out = [f"研究 274：台積電法說會前後（重建法說日 {len(CALLS)} 次，{CALLS[0][0]}～{CALLS[-1][0]}；做多加權、扣 6 點；同波動度對照；雙尾）", ""]
out.append(f"{'窗格':<18s} | 全期 筆數 每筆 超額 勝率 | 單一p 家族p | 2012–2018 筆 每筆 超額 | 2019～ 筆 每筆 超額")
for j, (nm, _, _, _) in enumerate(TESTS):
    n, m, e, w = obs[j]
    fam = (np.sum(pmin <= pe[j]) + 1) / (S + 1)
    out.append(f"{nm:<18s} | {n:3d} {m:+6.2%} {e:+6.2%} {w:4.0%} | {pe[j]:.3f} {fam:.3f} | {s1[j][0]:2d} {s1[j][1]:+6.2%} {s1[j][2]:+6.2%} | {s2[j][0]:2d} {s2[j][1]:+6.2%} {s2[j][2]:+6.2%}")
out.append("")
out.append("重建的法說日（隔天 2330 量比）：" + "、".join(f"{d}({r:.1f})" for d, r in CALLS))
txt = "\n".join(out)
print(txt)
open(os.path.join(HERE, "結果_研究274_台積電法說.txt"), "w", encoding="utf-8").write(txt + "\n")
