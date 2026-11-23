"""研究 1：多條均線投票、時間序列動能（12-1）、與現行策略比較；全押 2x，週五判斷"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import bt  # noqa: E402

PER = {"全期": ("1998-01-01", "2026-12-31"), "前段": ("1998-01-01", "2012-12-31"), "後段": ("2013-01-01", "2026-12-31")}
PX = bt.PX
M = {n: bt.get_sma(n) for n in (20, 40, 60, 80, 100, 120, 150, 200, 240)}


def run(start, end, target_fn, lev=2.0):
    i0 = next(i for i, d in enumerate(bt.DAYS) if d >= start)
    i1 = max(i for i, d in enumerate(bt.DAYS) if d <= end)
    eq = peak = 1.0
    mdd, pos, pend, n = 0.0, 0.0, None, 0
    state = {"on": False}
    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + (pos * bt.R1[i] - max(pos - 1, 0) * bt.DRAG / bt.TD if pos else bt.RC)
        if pend is not None:
            eq *= 1 - bt.COST * abs(pend - pos)
            pos, pend = pend, None
            n += 1
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if not bt.WEEK_END[i] or M[240][i] is None:
            continue
        frac = target_fn(i, state)  # 0～1
        t = round(frac * lev * 4) / 4  # 以 0.25x 為單位
        if t != pos:
            pend = t
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd, n / yrs


def current(i, s):
    if not s["on"] and PX[i] > M[60][i] * 1.01:
        s["on"] = True
    elif s["on"] and PX[i] < M[80][i] * 0.98:
        s["on"] = False
    return 1.0 if s["on"] else 0.0


def vote(ns, need):
    def f(i, s):
        k = sum(1 for n in ns if PX[i] > M[n][i])
        return 1.0 if k >= need else 0.0
    return f


def vote_frac(ns):
    return lambda i, s: sum(1 for n in ns if PX[i] > M[n][i]) / len(ns)


def tsmom(lb, skip=20):
    def f(i, s):
        j, k = i - skip, i - lb
        return 1.0 if k >= 0 and PX[j] > PX[k] else 0.0
    return f


def tsmom_vote(lbs):
    def f(i, s):
        return sum(1 for lb in lbs if PX[i - 20] > PX[i - lb]) / len(lbs)
    return f


def combo(i, s):
    # 現行均線訊號且 12-1 動能為正才持有
    return current(i, s) * (1.0 if PX[i - 20] > PX[i - 245] else 0.0)


def row(name, fn, **kw):
    cells = []
    for p, (a, b) in PER.items():
        c, m, t = run(a, b, fn, **kw)
        cells.append(f"{p} {c:5.1%}/{m:6.1%}")
    return f"{name:36s} " + " | ".join(cells) + f" | 年交易 {run(*PER['全期'], fn, **kw)[2]:.1f}"


out = ["格式：年化/最大回檔；全押 2x（或依比例 0～2x），週五判斷、隔日收盤成交", ""]
out.append(row("現行（MA60+1% 進／MA80-2% 出）", current))
out.append("\n— 多條均線投票（全有或全無）—")
S = (20, 60, 120, 240)
for need in (2, 3, 4):
    out.append(row(f"MA20/60/120/240 至少 {need} 條站上", vote(S, need)))
S2 = (40, 80, 150, 240)
for need in (2, 3, 4):
    out.append(row(f"MA40/80/150/240 至少 {need} 條站上", vote(S2, need)))
out.append("\n— 多條均線投票（依站上比例給部位）—")
out.append(row("MA20/60/120/240 比例", vote_frac(S)))
out.append(row("MA40/80/150/240 比例", vote_frac(S2)))
out.append(row("MA20/40/60/80/100/120/150/200/240 比例", vote_frac(tuple(M))))
out.append("\n— 時間序列動能（過去 N 天報酬 > 0，跳過最近 1 個月）—")
for lb in (60, 120, 180, 245):
    out.append(row(f"TSMOM {lb} 日", tsmom(lb)))
out.append(row("TSMOM 60/120/245 比例", tsmom_vote((60, 120, 245))))
out.append("\n— 組合 —")
out.append(row("現行 × 12-1 動能為正", combo))
open(os.path.join(os.path.dirname(__file__), "r1.txt"), "w", encoding="utf-8").write("\n".join(out))
