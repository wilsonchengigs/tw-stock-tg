import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import bt  # noqa: E402

PER = {"全期": ("1998-01-01", "2026-12-31"), "前段": ("1998-01-01", "2012-12-31"), "後段": ("2013-01-01", "2026-12-31")}
PX = bt.PX
m60, m80 = bt.get_sma(60), bt.get_sma(80)


def run(start, end, lev=2.0, daily_exit=False, trail=None, cooldown_weeks=0, drag=bt.DRAG, cost=bt.COST):
    i0 = next(i for i, d in enumerate(bt.DAYS) if d >= start)
    i1 = max(i for i, d in enumerate(bt.DAYS) if d <= end)
    eq = peak = 1.0
    mdd = 0.0
    pos, pending, trades = 0.0, None, 0
    state = False
    hi = None          # 進場後指數最高點（停損用）
    cool = 0           # 停損後要等幾個週末才能再進場
    worst_trade = 0.0
    entry_eq = None
    for i in range(i0, i1 + 1):
        if i > i0:
            r = pos * bt.R1[i] - max(pos - 1, 0) * drag / bt.TD + (bt.RC if pos == 0 else 0)
            eq *= 1 + r
        if pending is not None:
            eq *= 1 - cost * abs(pending - pos) * (2 if pending > 1 or pos > 1 else 1) / 2
            if pending > 0 and pos == 0:
                entry_eq = eq
            if pending == 0 and pos > 0 and entry_eq:
                worst_trade = min(worst_trade, eq / entry_eq - 1)
            pos, pending = pending, None
            trades += 1
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if m80[i] is None:
            continue
        if state:
            hi = max(hi, PX[i]) if hi else PX[i]
            stop = trail is not None and PX[i] < hi * (1 - trail)
            below = PX[i] < m80[i] * 0.98
            if (daily_exit and (below or stop)) or (bt.WEEK_END[i] and (below or stop)) or (stop and daily_exit):
                state = False
                pending = 0.0
                if stop and not below:
                    cool = cooldown_weeks
                continue
        if bt.WEEK_END[i]:
            if not state:
                if cool > 0:
                    cool -= 1
                elif PX[i] > m60[i] * 1.01:
                    state, hi = True, PX[i]
                    pending = lev
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd, trades / yrs / 2, worst_trade


def show(name, **kw):
    cells = []
    for p, (a, b) in PER.items():
        c, m, t, w = run(a, b, **kw)
        cells.append(f"{p} {c:5.1%}/{m:6.1%}")
    c, m, t, w = run(*PER["全期"], **kw)
    return f"{name:30s} " + " | ".join(cells) + f" | 年交易 {t:.1f} 單筆最差 {w:.1%}"


out = ["格式：年化/最大回檔；全押 2x，進場 MA60+1%（週五）", ""]
out.append(show("1.5x 現行（參考）", lev=1.5))
out.append(show("2x 週五出場", lev=2.0))
out.append(show("2x 每天檢查出場", lev=2.0, daily_exit=True))
for tr in (0.08, 0.10, 0.12, 0.15, 0.20):
    out.append(show(f"2x 週五出場＋停損 {tr:.0%}", lev=2.0, trail=tr))
for tr in (0.08, 0.10, 0.12, 0.15, 0.20):
    out.append(show(f"2x 每天出場＋停損 {tr:.0%}", lev=2.0, daily_exit=True, trail=tr))
for tr in (0.10, 0.15):
    out.append(show(f"2x 每天出場＋停損 {tr:.0%}＋冷卻 4 週", lev=2.0, daily_exit=True, trail=tr, cooldown_weeks=4))
open(os.path.join(os.path.dirname(__file__), "lev2.txt"), "w", encoding="utf-8").write("\n".join(out))
