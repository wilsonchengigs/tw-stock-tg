import math
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import bt  # noqa: E402

PER = {"全期": ("1998-01-01", "2026-12-31"), "前段": ("1998-01-01", "2012-12-31"), "後段": ("2013-01-01", "2026-12-31")}
PX, R1 = bt.PX, bt.R1
m60, m80, m240 = bt.get_sma(60), bt.get_sma(80), bt.get_sma(240)
# 20 日實現波動（年化）
VOL = [None] * len(PX)
for i in range(21, len(PX)):
    rs = [PX[k] / PX[k - 1] - 1 for k in range(i - 19, i + 1)]
    mu = sum(rs) / 20
    VOL[i] = math.sqrt(sum((x - mu) ** 2 for x in rs) / 19) * math.sqrt(245)


def trend_state():
    st, out = False, [False] * len(PX)
    for i in range(len(PX)):
        if m80[i] is not None:
            if bt.WEEK_END[i]:
                if not st and PX[i] > m60[i] * 1.01:
                    st = True
                elif st and PX[i] < m80[i] * 0.98:
                    st = False
        out[i] = st
    return out


TS = trend_state()


def run_lev(levf, start, end, drag=bt.DRAG, cost=bt.COST, min_step=0.25):
    """levf(i) -> 目標曝險倍數（0～2）；週末判斷、隔日收盤成交；變動小於 min_step 不調"""
    i0 = next(i for i, d in enumerate(bt.DAYS) if d >= start)
    i1 = max(i for i, d in enumerate(bt.DAYS) if d <= end)
    eq = peak = 1.0
    mdd = 0.0
    lev, pending, trades = 0.0, None, 0
    for i in range(i0, i1 + 1):
        if i > i0:
            # 曝險 lev 倍：超過 1 的部分要付槓桿成本
            r = lev * R1[i] - max(lev - 1, 0) * drag / bt.TD + (1 - min(lev, 1)) * bt.RC if lev <= 1 else lev * R1[i] - (lev - 1) * drag / bt.TD
            eq *= 1 + r
        if pending is not None:
            eq *= 1 - cost * abs(pending - lev)
            lev, pending = pending, None
            trades += 1
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if bt.WEEK_END[i]:
            t = levf(i)
            if abs(t - lev) >= min_step or (t == 0 and lev > 0) or (lev == 0 and t > 0):
                pending = t
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd, trades / yrs


def show(name, levf, **kw):
    cells = []
    for p, (a, b) in PER.items():
        c, m, t = run_lev(levf, a, b, **kw)
        cells.append(f"{p} {c:5.1%}/{m:6.1%}/{t:4.1f}")
    return f"{name:34s} " + " | ".join(cells)


out = ["格式：年化/最大回檔/年調整次數；趨勢訊號＝進場 MA60+1%、出場 MA80-2%（週五判斷）", ""]
out.append(show("大盤買進持有 1x", lambda i: 1.0))
out.append(show("現行：趨勢 → 1.5x / 現金", lambda i: 1.5 if TS[i] else 0.0))
out.append(show("趨勢 → 2x（全押正2）/ 現金", lambda i: 2.0 if TS[i] else 0.0))
out.append(show("趨勢 → 1x / 現金", lambda i: 1.0 if TS[i] else 0.0))
out.append("")
out.append("— 按比例：波動目標（波動大就降槓桿）—")
for tgt in (0.20, 0.25, 0.30):
    out.append(show(f"趨勢＋波動目標 {tgt:.0%}（上限 2x）", lambda i, tgt=tgt: (min(2.0, tgt / VOL[i]) if VOL[i] else 1.0) if TS[i] else 0.0))
out.append("")
out.append("— 按比例：分層（年線之上加碼）—")
out.append(show("趨勢且在年線上 2x，其他趨勢 1x", lambda i: (2.0 if (m240[i] and PX[i] > m240[i]) else 1.0) if TS[i] else 0.0))
out.append(show("趨勢且在年線上 1.5x，其他趨勢 1x", lambda i: (1.5 if (m240[i] and PX[i] > m240[i]) else 1.0) if TS[i] else 0.0))
out.append(show("趨勢 1.5x；空手時保留 0.5x", lambda i: 1.5 if TS[i] else 0.5))
out.append("")
out.append("— 期貨 vs 正2（槓桿成本：正2 每年 1% vs 期貨約 0.3%，期貨交易成本較低）—")
out.append(show("1.5x 用期貨（成本 0.3%/年、換手 0.05%）", lambda i: 1.5 if TS[i] else 0.0, drag=0.003, cost=0.0005))
out.append(show("2x 用期貨", lambda i: 2.0 if TS[i] else 0.0, drag=0.003, cost=0.0005))
open(os.path.join(os.path.dirname(__file__), "var.txt"), "w", encoding="utf-8").write("\n".join(out))
