"""研究 18：急跌緊急出場（只在極端情況才破例，平常仍週五判斷）

A 任一天收盤跌破 MA80 x (1-x)（比週五出場線再低很多）就隔天出場
B 近 5 日跌幅超過 y 就隔天出場
C 單日跌幅超過 z 就隔天出場
緊急出場後要等週五重新符合進場線才再進
用法：python -X utf8 backtest/research_18_急跌緊急出場.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402
import data  # noqa: E402

PX, DAYS, WE = bt.PX, bt.DAYS, bt.WEEK_END
N = len(PX)
PER = [("1998-01-01", "2026-12-31"), ("1998-01-01", "2012-12-31"), ("2013-01-01", "2026-12-31")]
REAL = ("2015-09-01", "2026-12-31")
M60, M80 = bt.get_sma(60), bt.get_sma(80)
_, _, l2 = data.series()
_px = [l2.get(d, (None, None))[1] for d in DAYS]
R2R, _lp = [0.0], None
for _i in range(1, N):
    R2R.append(_px[_i] / _lp - 1 if (_px[_i] and _lp) else bt.R2[_i])
    if _px[_i]:
        _lp = _px[_i]


def run(emerg, start, end, real=False):
    r2 = R2R if real else bt.R2
    i0 = next(i for i, d in enumerate(DAYS) if d >= start)
    i1 = max(i for i, d in enumerate(DAYS) if d <= end)
    eq = peak = 1.0
    mdd, on, pos, pend, n_em = 0.0, False, False, None, 0
    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + (r2[i] if pos else bt.RC)
        if pend is not None:
            if pend != pos:
                eq *= 1 - bt.COST * 2
            pos, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if i < 260:
            continue
        if on and emerg and emerg(i):
            on = False
            n_em += 1
        elif WE[i]:
            on = (not PX[i] < M80[i] * 0.98) if on else (PX[i] > M60[i] * 1.01)
        if on != pos:
            pend = on
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd, n_em


def fmt(e):
    cs = [run(e, a, b) for a, b in PER]
    rr = run(e, *REAL, real=True)
    return " | ".join(f"{c * 100:5.1f}%/{m * 100:6.1f}%" for c, m, _ in cs) + f" | 真實 {rr[0] * 100:5.1f}%/{rr[1] * 100:6.1f}% | 觸發 {cs[0][2]} 次"


def main():
    L = ["研究 18：急跌緊急出場（全期 | 前段 | 後段 | 真實；年化/最大回檔）"]

    def add(nm, e):
        L.append(f"{nm:28s} {fmt(e)}")
        print(L[-1], flush=True)

    add("現行", None)
    for x in (0.04, 0.06, 0.08, 0.10):
        add(f"A 任一天 < MA80x{1 - x:.2f}", (lambda x: lambda i: PX[i] < M80[i] * (1 - x))(x))
    for y in (0.06, 0.08, 0.10, 0.12, 0.15):
        add(f"B 5 日跌 > {y:.0%}", (lambda y: lambda i: PX[i] / PX[i - 5] - 1 < -y)(y))
    for z in (0.04, 0.05, 0.06, 0.07):
        add(f"C 單日跌 > {z:.0%}", (lambda z: lambda i: PX[i] / PX[i - 1] - 1 < -z)(z))
    out = "\n".join(L) + "\n"
    open(os.path.join(HERE, "結果_研究18_急跌緊急出場.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
