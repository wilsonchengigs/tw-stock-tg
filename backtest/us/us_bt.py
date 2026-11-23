import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import us  # noqa: E402

DRAG, CASH, COST = 0.03, 0.02, 0.0005
PER = {"全期": ("1995-06-01", "2026-12-31"), "前段": ("1995-06-01", "2010-12-31"), "後段": ("2011-01-01", "2026-12-31")}


def run(start, end, lev, n_in=60, b_in=0.01, n_out=80, b_out=0.02, hold=False):
    mi, mo = us.sma(n_in), us.sma(n_out)
    i0 = next(i for i, d in enumerate(us.DAYS) if d >= start)
    i1 = max(i for i, d in enumerate(us.DAYS) if d <= end)
    eq = peak = 1.0
    mdd = 0.0
    pos, pend, st, n = 0.0, None, False, 0
    if hold:
        pos = lev
    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + (pos * us.R1[i] - max(pos - 1, 0) * DRAG / us.TD if pos else CASH / us.TD)
        if pend is not None:
            eq *= 1 - COST * abs(pend - pos)
            pos, pend = pend, None
            n += 1
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if hold or mo[i] is None or mi[i] is None or not us.WEEK_END[i]:
            continue
        if not st and us.PX[i] > mi[i] * (1 + b_in):
            st = True
        elif st and us.PX[i] < mo[i] * (1 - b_out):
            st = False
        t = lev if st else 0.0
        if t != pos:
            pend = t
    yrs = (i1 - i0) / us.TD
    return eq ** (1 / yrs) - 1, mdd, n / yrs


def row(name, **kw):
    cells = []
    for p, (a, b) in PER.items():
        c, m, t = run(a, b, **kw)
        cells.append(f"{p} {c:6.1%}/{m:6.1%}")
    return f"{name:30s} " + " | ".join(cells) + f" | 年交易 {run(*PER['全期'], **kw)[2]:.1f}"


out = ["格式：年化/最大回檔；訊號看 SOX 指數本身", "", "== 買進持有 =="]
for lev in (1.0, 2.0, 3.0):
    out.append(row(f"{lev:.0f}x 買進持有", lev=lev, hold=True))
out.append("\n== 台股同一套（進 MA60+1%、出 MA80-2%，週五）==")
for lev in (1.0, 1.5, 2.0, 3.0):
    out.append(row(f"{lev}x", lev=lev))
out.append("\n== 參數穩定度：3x，全期 年化/最大回檔（列＝出場均線-2%，欄＝進場均線+1%）==")
ins = (20, 40, 60, 100, 150)
out.append("出\進     " + "".join(f"{n:>16d}" for n in ins))
for no in (40, 60, 80, 100, 150, 200):
    cells = []
    for ni in ins:
        c, m, _ = run(*PER["全期"], lev=3.0, n_in=ni, n_out=no)
        cells.append(f"{c:6.1%}/{m:6.1%}".rjust(16))
    out.append(f"{no:<10d}" + "".join(cells))
out.append("\n== 同上，2x ==")
out.append("出\進     " + "".join(f"{n:>16d}" for n in ins))
for no in (40, 60, 80, 100, 150, 200):
    cells = []
    for ni in ins:
        c, m, _ = run(*PER["全期"], lev=2.0, n_in=ni, n_out=no)
        cells.append(f"{c:6.1%}/{m:6.1%}".rjust(16))
    out.append(f"{no:<10d}" + "".join(cells))
open(os.path.join(os.path.dirname(__file__), "us_bt.txt"), "w", encoding="utf-8").write("\n".join(out))
