"""研究 276：美股休市（前一晚美國放假：感恩節、7/4、陣亡將士、勞動節、MLK、總統日、耶穌受難日、聖誕新年等）時的台股
事件日 k：台股前一交易日 k−1 到 k 之間「沒有任何一個美股交易日」（美股日期 ∈ [DAYS[k−1], DAYS[k])，用 GSPC.json）
檢定（加權收盤對收盤，同前 20 日波動十分位對照）：
  BEFORE  k−1 當天報酬（美股今晚放假的前一天）
  DAY     k 當天報酬（沒有美股訊息的一天）
  ABS     k 當天 |報酬|（波動是否較小）
  NEXT    k+1 當天報酬（一次消化兩天美股）
  ABS N   k+1 當天 |報酬|
家族：事件序列環狀平移 1,000 次（平移 ≥250 天）最小 p 值法、雙尾；兩段 1998–2012／2013～
用法：python -X utf8 backtest/research_276_美股休市.py
"""
import bisect
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402

i0 = next(i for i, d in enumerate(bt.DAYS) if d >= "1998-01-01")
DAYS = bt.DAYS[i0:]
PX = np.array(bt.PX[i0:])
N = len(DAYS)
r1 = np.r_[0.0, PX[1:] / PX[:-1] - 1]
vol = np.array([r1[max(1, k - 19):k + 1].std() if k >= 21 else np.nan for k in range(N)])
qs = np.nanquantile(vol, np.linspace(0, 1, 11)[1:-1])
VDEC = np.where(np.isnan(vol), -1, np.searchsorted(qs, np.nan_to_num(vol)))

NY = timezone(timedelta(hours=-5))
g = json.load(open(os.path.join(HERE, "GSPC.json")))
SPD = sorted({datetime.fromtimestamp(t, NY).strftime("%Y-%m-%d") for t, p in zip(g["timestamp"], g["indicators"]["quote"][0]["close"]) if p})
NUS = np.zeros(N, int)
for k in range(1, N):
    NUS[k] = bisect.bisect_left(SPD, DAYS[k]) - bisect.bisect_left(SPD, DAYS[k - 1])
NUS[0] = 1
ev = (NUS == 0) & (np.arange(N) > 30) & (np.arange(N) < N - 2) & (VDEC >= 0)
ev &= np.array([d <= SPD[-1] for d in DAYS])

# 量值序列：(名稱, 對每個 k 取的值, 對照用的波動十分位索引偏移)
A1 = np.abs(r1)
SER = {"BEFORE（休市前一天）": (np.r_[r1[1:], np.nan], 0), "DAY（沒有美股訊息）": (r1, 0), "ABS DAY |報酬|": (A1, 0),
       "NEXT（消化兩天）": (np.r_[r1[1:], np.nan], 0), "ABS NEXT |報酬|": (np.r_[A1[1:], np.nan], 0)}
# BEFORE 要對應 k−1：用事件位移處理
SHIFT = {"BEFORE（休市前一天）": -1, "DAY（沒有美股訊息）": 0, "ABS DAY |報酬|": 0, "NEXT（消化兩天）": 1, "ABS NEXT |報酬|": 1}
BASE = {"BEFORE（休市前一天）": r1, "DAY（沒有美股訊息）": r1, "ABS DAY |報酬|": A1, "NEXT（消化兩天）": r1, "ABS NEXT |報酬|": A1}
NAMES = list(SHIFT)
CTRL = {}
for nm in NAMES:
    x = BASE[nm]
    CTRL[nm] = {d: np.nanmean(x[31:][VDEC[30:-1] == d]) for d in range(10)}  # 以前一天收盤的波動十分位分組


def stats(evmask, mask=None):
    out = []
    idx = np.flatnonzero(evmask if mask is None else evmask & mask)
    for nm in NAMES:
        kk = idx + SHIFT[nm]
        kk = kk[(kk > 30) & (kk < N)]
        x = BASE[nm][kk]
        c = np.array([CTRL[nm][max(VDEC[k - 1], 0)] for k in kk])
        out.append((len(x), x.mean(), (x - c).mean(), (x > 0).mean()))
    return out


obs = stats(ev)
seg1 = np.array([d <= "2012-12-31" for d in DAYS])
s1 = stats(ev, seg1)
s2 = stats(ev, ~seg1)
rng = np.random.default_rng(276)
S = 1000
null = np.zeros((S, len(NAMES)))
valid = (np.arange(N) > 30) & (np.arange(N) < N - 2) & (VDEC >= 0)
for s in range(S):
    sh = int(rng.integers(250, N - 250))
    null[s] = [r[2] for r in stats(np.roll(ev, sh) & valid)]
ob = np.array([r[2] for r in obs])
pe = np.array([(np.sum(np.abs(null[:, j]) >= abs(ob[j])) + 1) / (S + 1) for j in range(len(NAMES))])
pmin = np.array([min(np.sum(np.abs(null[:, j]) >= abs(null[s, j])) / S for j in range(len(NAMES))) for s in range(S)])

L = [f"研究 276：前一晚美股休市的台股（{ev.sum()} 天，{DAYS[np.flatnonzero(ev)[0]]}～{DAYS[np.flatnonzero(ev)[-1]]}；同波動度對照；雙尾）", ""]
L.append(f"{'檢定':<20s} | 全期 天數 平均 超額 上漲比 | 單一p 家族p | 1998–2012 天 平均 超額 | 2013～ 天 平均 超額")
for j, nm in enumerate(NAMES):
    n, m, e, w = obs[j]
    fam = (np.sum(pmin <= pe[j]) + 1) / (S + 1)
    L.append(f"{nm:<18s} | {n:4d} {m:+7.3%} {e:+7.3%} {w:4.0%} | {pe[j]:.3f} {fam:.3f} | {s1[j][0]:3d} {s1[j][1]:+7.3%} {s1[j][2]:+7.3%} | {s2[j][0]:3d} {s2[j][1]:+7.3%} {s2[j][2]:+7.3%}")
L.append("")
L.append("所有台股交易日：平均 " + f"{np.nanmean(r1[31:]):+.3%}、|報酬| {np.nanmean(A1[31:]):.3%}")
L.append("事件日（月-日）分布：" + "、".join(f"{k}:{v}" for k, v in sorted({d[5:]: 0 for d in []}.items())))
from collections import Counter  # noqa: E402
cnt = Counter(DAYS[k][5:7] for k in np.flatnonzero(ev))
L[-1] = "事件日月份分布：" + "、".join(f"{m}月 {cnt[m]}" for m in sorted(cnt))
txt = "\n".join(L)
print(txt)
open(os.path.join(HERE, "結果_研究276_美股休市.txt"), "w", encoding="utf-8").write(txt + "\n")
