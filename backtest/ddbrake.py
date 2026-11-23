import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import bt  # noqa: E402

PER = {"全期": ("1998-01-01", "2026-12-31"), "前段": ("1998-01-01", "2012-12-31"), "後段": ("2013-01-01", "2026-12-31")}
PX = bt.PX
m60, m80 = bt.get_sma(60), bt.get_sma(80)


def run(start, end, hi_lev=2.0, lo_lev=1.0, dd_cut=None, dd_back=None, drag=bt.DRAG, cost=bt.COST):
    """趨勢進出場（週五）；進場時用 hi_lev，帳戶從最高點回落超過 dd_cut 改用 lo_lev，回升到 dd_back 以內再回 hi_lev"""
    i0 = next(i for i, d in enumerate(bt.DAYS) if d >= start)
    i1 = max(i for i, d in enumerate(bt.DAYS) if d <= end)
    eq = peak = 1.0
    mdd = 0.0
    pos, pending, state, braked = 0.0, None, False, False
    switches = 0
    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + pos * bt.R1[i] - max(pos - 1, 0) * drag / bt.TD + (bt.RC if pos == 0 else 0)
        if pending is not None:
            eq *= 1 - cost * abs(pending - pos)
            pos, pending = pending, None
            switches += 1
        peak = max(peak, eq)
        dd = eq / peak - 1
        mdd = min(mdd, dd)
        if not bt.WEEK_END[i] or m80[i] is None:
            continue
        if not state and PX[i] > m60[i] * 1.01:
            state = True
        elif state and PX[i] < m80[i] * 0.98:
            state = False
        if dd_cut is not None:
            if not braked and dd < -dd_cut:
                braked = True
            elif braked and dd > -dd_back:
                braked = False
        target = (lo_lev if braked else hi_lev) if state else 0.0
        if target != pos:
            pending = target
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd, switches / yrs


def show(name, **kw):
    cells = []
    for p, (a, b) in PER.items():
        c, m, t = run(a, b, **kw)
        cells.append(f"{p} {c:5.1%}/{m:6.1%}")
    c, m, t = run(*PER["全期"], **kw)
    return f"{name:34s} " + " | ".join(cells) + f" | 年調整 {t:.1f}"


out = ["格式：年化/最大回檔；進出場同現行（週五 MA60+1% 進、MA80-2% 出）", ""]
out.append(show("1.5x 現行", hi_lev=1.5))
out.append(show("2x 無保護", hi_lev=2.0))
for cut in (0.15, 0.20, 0.25, 0.30):
    for back in (0.05, 0.10):
        for lo in (1.0, 1.5):
            if back >= cut:
                continue
            out.append(show(f"2x，回落>{cut:.0%} 降 {lo}x，回到-{back:.0%} 內恢復", hi_lev=2.0, lo_lev=lo, dd_cut=cut, dd_back=back))
open(os.path.join(os.path.dirname(__file__), "dd.txt"), "w", encoding="utf-8").write("\n".join(out))
