import math
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import us  # noqa: E402
from us_bt import CASH, COST, DRAG, PER  # noqa: E402

PX = us.PX
VOL = [None] * len(PX)
for i in range(21, len(PX)):
    rs = [PX[k] / PX[k - 1] - 1 for k in range(i - 19, i + 1)]
    mu = sum(rs) / 20
    VOL[i] = math.sqrt(sum((x - mu) ** 2 for x in rs) / 19) * math.sqrt(us.TD)


def run(start, end, target, max_lev=3.0, trend=True, n_in=60, n_out=80, daily=False):
    mi, mo = us.sma(n_in), us.sma(n_out)
    i0 = next(i for i, d in enumerate(us.DAYS) if d >= start)
    i1 = max(i for i, d in enumerate(us.DAYS) if d <= end)
    eq = peak = 1.0
    mdd = 0.0
    pos, pend, st = 0.0, None, False
    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + (pos * us.R1[i] - max(pos - 1, 0) * DRAG / us.TD + (1 - min(pos, 1)) * CASH / us.TD)
        if pend is not None:
            eq *= 1 - COST * abs(pend - pos)
            pos, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        check = us.WEEK_END[i] or daily
        if not check or mo[i] is None or VOL[i] is None:
            continue
        if us.WEEK_END[i]:
            if not st and PX[i] > mi[i] * 1.01:
                st = True
            elif st and PX[i] < mo[i] * 0.98:
                st = False
        on = st if trend else True
        t = min(max_lev, target / VOL[i]) if on else 0.0
        if abs(t - pos) > 0.2 or (t == 0) != (pos == 0):
            pend = round(t, 2)
    yrs = (i1 - i0) / us.TD
    return eq ** (1 / yrs) - 1, mdd


out = ["格式：年化/最大回檔；部位＝目標波動 ÷ SOX 近 20 日波動（上限 3x，用 SOXL＋現金組合）"]
for trend in (True, False):
    out.append(f"\n== {'加趨勢濾網（同台股規則）' if trend else '不加趨勢濾網'}，每週調整 ==")
    for tgt in (0.15, 0.20, 0.25, 0.30, 0.40):
        cells = []
        for p, (a, b) in PER.items():
            c, m = run(a, b, tgt, trend=trend)
            cells.append(f"{p} {c:6.1%}/{m:6.1%}")
        out.append(f"目標波動 {tgt:.0%}  " + " | ".join(cells))
out.append("\n== 加趨勢濾網，每天依波動調整（出場仍週五）==")
for tgt in (0.15, 0.20, 0.25, 0.30):
    cells = []
    for p, (a, b) in PER.items():
        c, m = run(a, b, tgt, daily=True)
        cells.append(f"{p} {c:6.1%}/{m:6.1%}")
    out.append(f"目標波動 {tgt:.0%}  " + " | ".join(cells))
open(os.path.join(os.path.dirname(__file__), "us_vol.txt"), "w", encoding="utf-8").write("\n".join(out))
