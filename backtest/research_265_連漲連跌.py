"""研究 265：連漲／連跌 N 天之後（加權收盤）
事件：加權連續 N 天收紅（或收黑），N＝4／5／6／7，以「剛好達到 N」那天為事件日（連 8 天只算 N=4..7 各一次）
結果：事件日收盤做多 H＝1／5／10 天的淨報酬（扣 6 點）；連漲看「做空是否有利」＝做多是否顯著為負
對照：同前 20 日波動十分位的所有日子；家族 4 N × 2 方向 × 3 H＝24 檢定，事件序列環狀平移 1,000 次，雙尾最小 p
另：v3 在場／空手拆分；兩段 1998–2012／2013～
用法：python -X utf8 backtest/research_265_連漲連跌.py
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_261_春節效應 as R  # noqa: E402
import research_138_金字塔加碼與分段停損 as R138  # noqa: E402

DAYS, PX, N, win, VDEC, r1 = R.DAYS, R.PX, R.N, R.win, R.VDEC, R.r1
i0 = R138.DAYS.index(DAYS[0])
ST = np.array(R138.ST[i0:i0 + N])
up, dn = np.zeros(N, int), np.zeros(N, int)
for k in range(1, N):
    up[k] = up[k - 1] + 1 if r1[k] > 0 else 0
    dn[k] = dn[k - 1] + 1 if r1[k] < 0 else 0
HS = (1, 5, 10)
FWD = {H: np.array([win(k, k + H) if k + H < N else np.nan for k in range(N)]) for H in HS}
CT = {}
for H in HS:
    for d in range(10):
        m = (VDEC == d) & ~np.isnan(FWD[H])
        m[:30] = False
        CT[(H, d)] = FWD[H][m].mean()
TESTS = [(dirn, n, H) for dirn in ("連漲", "連跌") for n in (4, 5, 6, 7) for H in HS]


def sigs():
    return {(d, n): ((up if d == "連漲" else dn) == n) for d in ("連漲", "連跌") for n in (4, 5, 6, 7)}


SIG = sigs()


def ex(s, H, mask=None):
    k = np.flatnonzero(s)
    k = k[(k >= 30) & (k + H < N)]
    if mask is not None:
        k = k[mask[k]]
    if len(k) == 0:
        return 0, np.nan, np.nan, np.nan
    x = FWD[H][k]
    c = np.array([CT[(H, VDEC[j])] for j in k])
    return len(k), x.mean(), (x - c).mean(), (x > 0).mean()


obs = np.array([ex(SIG[(d, n)], H)[2] for d, n, H in TESTS])
rng = np.random.default_rng(265)
S = 1000
null = np.zeros((S, len(TESTS)))
for s in range(S):
    sh = int(rng.integers(250, N - 250))
    null[s] = [ex(np.roll(SIG[(d, n)], sh), H)[2] for d, n, H in TESTS]
pe = np.array([min(1, 2 * min((np.sum(null[:, j] >= obs[j]) + 1) / (S + 1), (np.sum(null[:, j] <= obs[j]) + 1) / (S + 1))) for j in range(len(TESTS))])
pn = np.array([min(min(1, 2 * min(np.mean(null[:, j] >= null[s, j]), np.mean(null[:, j] <= null[s, j]))) for j in range(len(TESTS))) for s in range(S)])
seg1 = np.array([d <= "2012-12-31" for d in DAYS])
out = ["研究 265：連漲／連跌 N 天後做多 H 天（扣 6 點、同波動度對照；雙尾）", "", "事件 N H | 筆數 每筆 超額 勝率 | 雙尾p 家族p | 1998–2012 超額 | 2013～ 超額 | v3 在場 超額 | v3 空手 超額"]
for j, (d, n, H) in enumerate(TESTS):
    c, m, e, w = ex(SIG[(d, n)], H)
    fam = (np.sum(pn <= pe[j]) + 1) / (S + 1)
    a = ex(SIG[(d, n)], H, seg1)
    b = ex(SIG[(d, n)], H, ~seg1)
    on = ex(SIG[(d, n)], H, ST == 1)
    off = ex(SIG[(d, n)], H, ST == 0)
    out.append(f"{d} {n} {H:2d} | {c:4d} {m:+6.2%} {e:+6.2%} {w:4.0%} | {pe[j]:.3f} {fam:.3f} | {a[2]:+6.2%} | {b[2]:+6.2%} | {on[0]:3d} {on[2]:+6.2%} | {off[0]:3d} {off[2]:+6.2%}")
txt = "\n".join(out)
print(txt)
open(os.path.join(HERE, "結果_研究265_連漲連跌.txt"), "w", encoding="utf-8").write(txt + "\n")
