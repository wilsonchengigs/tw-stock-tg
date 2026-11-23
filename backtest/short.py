import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import bt  # noqa: E402

PER = {"全期": ("1998-01-01", "2026-12-31"), "前段": ("1998-01-01", "2012-12-31"), "後段": ("2013-01-01", "2026-12-31")}
PX = bt.PX
m60, m80, m240 = bt.get_sma(60), bt.get_sma(80), bt.get_sma(240)
INV_FEE = 0.01  # 反向 ETF 內扣


def day_ret(pos, i):
    if pos > 0:
        return pos * bt.R1[i] - max(pos - 1, 0) * bt.DRAG / bt.TD
    if pos < 0:
        k = -pos
        # 做空：賺 -（價格＋配息），抵押的現金有利息，扣內扣
        return -k * bt.R1[i] + bt.RC - k * INV_FEE / bt.TD
    return bt.RC


def run(start, end, short_rule, long_lev=2.0, short_lev=1.0):
    i0 = next(i for i, d in enumerate(bt.DAYS) if d >= start)
    i1 = max(i for i, d in enumerate(bt.DAYS) if d <= end)
    eq = peak = 1.0
    mdd = 0.0
    pos, pend, st = 0.0, None, False
    short_days = 0
    short_pnl = 1.0
    for i in range(i0, i1 + 1):
        if i > i0:
            r = day_ret(pos, i)
            eq *= 1 + r
            if pos < 0:
                short_days += 1
                short_pnl *= 1 + r - bt.RC
        if pend is not None:
            eq *= 1 - bt.COST * abs(pend - pos)
            pos, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if m80[i] is None or not bt.WEEK_END[i]:
            continue
        if not st and PX[i] > m60[i] * 1.01:
            st = True
        elif st and PX[i] < m80[i] * 0.98:
            st = False
        if st:
            t = long_lev
        else:
            t = -short_lev if short_rule(i) else 0.0
        if t != pos:
            pend = t
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd, short_days / (i1 - i0 + 1), short_pnl - 1


def show(name, rule, **kw):
    cells = []
    for p, (a, b) in PER.items():
        c, m, sd, sp = run(a, b, rule, **kw)
        cells.append(f"{p} {c:5.1%}/{m:6.1%}")
    c, m, sd, sp = run(*PER["全期"], rule, **kw)
    return f"{name:34s} " + " | ".join(cells) + f" | 做空時間 {sd:4.0%}，做空部分累計 {sp:+.0%}"


always = lambda i: True  # noqa: E731
below240 = lambda i: m240[i] is not None and PX[i] < m240[i]  # noqa: E731
below240_down = lambda i: m240[i] is not None and PX[i] < m240[i] and m240[i - 20] is not None and m240[i] < m240[i - 20]  # noqa: E731
never = lambda i: False  # noqa: E731

out = ["格式：年化/最大回檔；做多全押 2x（週五 MA60+1% 進、MA80-2% 出）", ""]
out.append(show("不做空（現行）", never))
out.append(show("跌破就做空 -1x", always))
out.append(show("跌破就做空 -0.5x", always, short_lev=0.5))
out.append(show("跌破且在年線下才做空 -1x", below240))
out.append(show("跌破且在年線下才做空 -0.5x", below240, short_lev=0.5))
out.append(show("跌破、年線下且年線下彎才做空 -1x", below240_down))
out.append("")
# 各次空頭期間
crashes = [("2000 泡沫", "2000-02-01", "2001-10-31"), ("2008 海嘯", "2007-10-01", "2008-12-31"), ("2011 歐債", "2011-01-01", "2011-12-31"), ("2015 股災", "2015-04-01", "2015-09-30"), ("2018", "2018-09-01", "2019-01-31"), ("2022 升息", "2022-01-01", "2022-12-31"), ("2026 本次", "2026-10-01", "2026-11-23")]
for nm, a, b in crashes:
    r0 = run(a, b, never)
    r1 = run(a, b, always)
    r2 = run(a, b, below240)
    out.append(f"{nm:10s} 不做空 {r0[0]:+.0%}年化/{r0[1]:.0%} | 跌破就空 {r1[0]:+.0%}/{r1[1]:.0%} | 年線下才空 {r2[0]:+.0%}/{r2[1]:.0%}")
open(os.path.join(os.path.dirname(__file__), "short.txt"), "w", encoding="utf-8").write("\n".join(out))
