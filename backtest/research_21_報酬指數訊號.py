"""研究 21：用「含息報酬指數」而不是價格指數產生訊號

加權指數（價格指數）每年除息季（6～9 月）會因除息掉約 2～4%，可能讓均線訊號在除息季誤判出場、或延後進場。
這裡用近似的報酬指數：每年 div（2.5%／3%／3.5%）平均分攤在 6/15～9/15 的交易日加回去，訊號用它算，報酬計算不變。
（證交所有官方「發行量加權股價報酬指數」2003 起，之後可用真實資料再驗證）
用法：python -X utf8 backtest/research_21_報酬指數訊號.py
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
_, _, l2 = data.series()
_px = [l2.get(d, (None, None))[1] for d in DAYS]
R2R, _lp = [0.0], None
for _i in range(1, N):
    R2R.append(_px[_i] / _lp - 1 if (_px[_i] and _lp) else bt.R2[_i])
    if _px[_i]:
        _lp = _px[_i]


def tr_index(div, window=("06-15", "09-15")):
    ys = {}
    for d in DAYS:
        if window[0] <= d[5:] <= window[1]:
            ys[d[:4]] = ys.get(d[:4], 0) + 1
    out, f = [], 1.0
    for i, d in enumerate(DAYS):
        if window[0] <= d[5:] <= window[1]:
            f *= (1 + div) ** (1 / ys[d[:4]])
        out.append(PX[i] * f)
    return out


def sma(x, n):
    out, s = [None] * len(x), 0.0
    for i, v in enumerate(x):
        s += v
        if i >= n:
            s -= x[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def signal(x, ein=60, bi=1.01, eo=80, bo=0.98):
    mi, mo = sma(x, ein), sma(x, eo)
    st, out = False, []
    for i in range(N):
        if WE[i] and i >= 260:
            st = (not x[i] < mo[i] * bo) if st else (x[i] > mi[i] * bi)
        out.append(st)
    return out


def run(sig, start, end, real=False):
    r2 = R2R if real else bt.R2
    i0 = next(i for i, d in enumerate(DAYS) if d >= start)
    i1 = max(i for i, d in enumerate(DAYS) if d <= end)
    eq = peak = 1.0
    mdd, pos, pend, tr = 0.0, False, None, 0
    exits_q3 = 0
    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + (r2[i] if pos else bt.RC)
        if pend is not None:
            eq *= 1 - bt.COST * 2
            if pos and not pend and "07-01" <= DAYS[i][5:] <= "09-30":
                exits_q3 += 1
            pos, pend = pend, None
            tr += 1
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if WE[i] and sig[i] != pos:
            pend = sig[i]
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd, tr / yrs, exits_q3


def fmt(sig):
    cs = [run(sig, a, b) for a, b in PER]
    rr = run(sig, *REAL, real=True)
    return " | ".join(f"{c * 100:5.1f}%/{m * 100:6.1f}%" for c, m, _, _ in cs) + \
        f" | 真實 {rr[0] * 100:5.1f}%/{rr[1] * 100:6.1f}% | 年交易 {cs[0][2]:3.1f} | 7～9 月出場 {cs[0][3]} 次"


def main():
    L = ["研究 21：訊號用含息報酬指數（近似）（全期 | 前段 | 後段 | 真實；年化/最大回檔）"]

    def add(nm, sig):
        L.append(f"{nm:34s} {fmt(sig)}")
        print(L[-1], flush=True)

    add("價格指數（現行）", signal(PX))
    for div in (0.025, 0.03, 0.035):
        add(f"報酬指數 配息 {div:.1%}", signal(tr_index(div)))
    L.append("\n鄰近參數（報酬指數 3%）：")
    tr = tr_index(0.03)
    for p in ((60, 1.0, 80, 0.98), (60, 1.01, 80, 0.975), (60, 1.01, 90, 0.98), (55, 1.01, 80, 0.98), (65, 1.01, 80, 0.98), (60, 1.02, 80, 0.98), (60, 1.01, 70, 0.98), (60, 1.01, 80, 0.99)):
        a = fmt(signal(PX, *p))
        b = fmt(signal(tr, *p))
        L.append(f"  MA{p[0]}x{p[1]}/MA{p[2]}x{p[3]}\n    價格 {a}\n    報酬 {b}")
    out = "\n".join(L) + "\n"
    print("\n".join(L[5:]))
    open(os.path.join(HERE, "結果_研究21_報酬指數訊號.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
