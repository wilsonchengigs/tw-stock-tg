"""
週頻趨勢策略回測（加權指數 1997～）

資產（日報酬）：
- 1x：加權指數漲跌 + 每年 3% 配息（≈0050）
- 2x：2 ×（加權漲跌 + 配息）− 每年 1% 內扣（≈00631L，用 00631L 實際走勢校正，略保守）
- 現金：每年 1%

規則：每週最後一個交易日收盤看訊號，下一個交易日收盤成交（保守：中間那天的漲跌不吃到）
交易成本：每換手 1 單位曝險 0.25%（手續費＋ETF 證交稅）
"""
import math
import sys
from datetime import date

sys.path.insert(0, __import__("os").path.dirname(__file__))
import data  # noqa: E402

DIV, DRAG, CASH, COST = 0.03, 0.01, 0.01, 0.0025
TD = 245

tw, _, _ = data.series()
DAYS = sorted(tw)
PX = [tw[d][0] for d in DAYS]
R1 = [0.0] + [PX[i] / PX[i - 1] - 1 + DIV / TD for i in range(1, len(PX))]
R2 = [0.0] + [2 * R1[i] - DRAG / TD for i in range(1, len(PX))]
RC = CASH / TD


def week_end_flags():
    flags = []
    for i, d in enumerate(DAYS):
        if i == len(DAYS) - 1:
            flags.append(True)
            continue
        y1, w1, _ = date.fromisoformat(d).isocalendar()
        y2, w2, _ = date.fromisoformat(DAYS[i + 1]).isocalendar()
        flags.append((y1, w1) != (y2, w2))
    return flags


WEEK_END = week_end_flags()


def sma(n):
    out, s = [None] * len(PX), 0.0
    for i, p in enumerate(PX):
        s += p
        if i >= n:
            s -= PX[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


_SMA = {}


def get_sma(n):
    if n not in _SMA:
        _SMA[n] = sma(n)
    return _SMA[n]


def daily_ret(w):
    """w = (2x 權重, 1x 權重)，剩下是現金"""
    w2, w1 = w
    wc = 1 - w2 - w1
    return lambda i: w2 * R2[i] + w1 * R1[i] + wc * RC


def run(signal, on, off, start, end):
    """signal(i) -> True/False/None(維持)；on/off = (2x 權重, 1x 權重)"""
    i0 = next(i for i, d in enumerate(DAYS) if d >= start)
    i1 = max(i for i, d in enumerate(DAYS) if d <= end)
    eq, peak, mdd = 1.0, 1.0, 0.0
    state = None
    pos = off
    pending = None
    trades = 0
    for i in range(i0, i1 + 1):
        # 今天的報酬用昨天收盤後的持倉
        r = pos[0] * R2[i] + pos[1] * R1[i] + (1 - pos[0] - pos[1]) * RC if i > i0 else 0.0
        eq *= 1 + r
        # 執行上週末決定、今天收盤成交的單
        if pending is not None:
            turnover = abs(pending[0] - pos[0]) * 2 + abs(pending[1] - pos[1])
            if turnover > 0:
                eq *= 1 - COST * turnover
                trades += 1
            pos = pending
            pending = None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if WEEK_END[i]:
            s = signal(i, state)
            if s is not None:
                state = s
            target = on if state else off
            if target != pos:
                pending = target
    yrs = (i1 - i0) / TD
    cagr = eq ** (1 / yrs) - 1
    return {"cagr": cagr, "mdd": mdd, "mult": eq, "trades_py": trades / yrs}


def ma_signal(n, band=0.0, slope=0):
    m = get_sma(n)

    def f(i, state):
        if m[i] is None:
            return False
        up = PX[i] > m[i] * (1 + band)
        dn = PX[i] < m[i] * (1 - band)
        if slope:
            j = i - slope
            rising = j >= 0 and m[j] is not None and m[i] > m[j]
            up = up and rising
        if up:
            return True
        if dn:
            return False
        return None if state is not None else False
    return f


def buyhold():
    return lambda i, s: True


POS = {
    "2x": (1.0, 0.0),
    "1.5x": (0.5, 0.5),
    "1x": (0.0, 1.0),
    "cash": (0.0, 0.0),
    "0.5x": (0.0, 0.5),
}


def fmt(r):
    return f"年化 {r['cagr']:6.1%}  最大回檔 {r['mdd']:6.1%}  倍數 {r['mult']:7.2f}  年交易 {r['trades_py']:4.1f} 次"


PERIODS = {
    "全期 1998-2026": ("1998-01-01", "2026-12-31"),
    "前段 1998-2012": ("1998-01-01", "2012-12-31"),
    "後段 2013-2026": ("2013-01-01", "2026-12-31"),
}

if __name__ == "__main__":
    out = []
    out.append("== 基準：買進持有 ==")
    for nm, w in (("1x(≈0050)", "1x"), ("2x(≈00631L)", "2x")):
        for pn, (a, b) in PERIODS.items():
            out.append(f"{nm:12s} {pn}: {fmt(run(buyhold(), POS[w], POS[w], a, b))}")

    out.append("\n== 參數掃描（前段選參數）==")
    rows = []
    for n in (20, 40, 60, 80, 100, 120, 150, 200, 240):
        for band in (0.0, 0.01, 0.02, 0.03):
            for slope in (0, 20):
                for on in ("2x", "1.5x", "1x"):
                    for off in ("cash", "0.5x", "1x"):
                        if POS[off][0] * 2 + POS[off][1] >= POS[on][0] * 2 + POS[on][1]:
                            continue
                        sig = ma_signal(n, band, slope)
                        res = {pn: run(sig, POS[on], POS[off], a, b) for pn, (a, b) in PERIODS.items()}
                        rows.append(((n, band, slope, on, off), res))
    import pickle
    pickle.dump(rows, open(__import__("os").path.join(__import__("os").path.dirname(__file__), "grid.pkl"), "wb"))
    out.append(f"共 {len(rows)} 組")
    open(__import__("os").path.join(__import__("os").path.dirname(__file__), "out_base.txt"), "w", encoding="utf-8").write("\n".join(out))
