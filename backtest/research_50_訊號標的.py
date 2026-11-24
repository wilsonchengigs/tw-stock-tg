"""研究 50：訊號用哪個標的的均線？加權指數（現行）vs 台積電 2330 vs 0050（調整後價格，2014 前有錯價只用來做 2015 後）
以及「加權與台積電都站上才進／任一跌破就出」與「任一站上就進／都跌破才出」
規則：進場 MA60×1.01、出場 MA80×0.975，新版融資濾網；持有 00631L
資料：Yahoo 2330.TW 調整後價格（2000～；檢查錯價：單日 |報酬| > 11% 視為錯價改用前值）
用法：python -X utf8 backtest/research_50_訊號標的.py
"""
import importlib.util
import json
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r41", os.path.join(HERE, "research_41_總經濾網.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
bt, DAYS, PX, N, WE, HOT = R.bt, R.DAYS, R.PX, R.N, R.WE, R.HOT
RR = R.R40.R32.R
TW = timezone(timedelta(hours=8))


def load_tw(name):
    r = json.load(open(os.path.join(HERE, name + ".json")))
    a = r["indicators"].get("adjclose", [{}])[0].get("adjclose") or r["indicators"]["quote"][0]["close"]
    m = {datetime.fromtimestamp(t, TW).strftime("%Y-%m-%d"): v for t, v in zip(r["timestamp"], a) if v}
    out, last, bad = [], None, 0
    for d in DAYS:
        v = m.get(d)
        if v and last and abs(v / last - 1) > 0.11:
            bad += 1
            v = None
        if v:
            last = v
        out.append(last)
    return out, bad


TSMC, BAD = load_tw("2330")
_, L1, _ = R.R40.R32.R.data.series() if hasattr(R.R40.R32.R, "data") else __import__("data").series()


def sma(x, n):
    out = [None] * len(x)
    s, q = 0.0, []
    for i, v in enumerate(x):
        if v is None:
            q, s = [], 0.0
            continue
        q.append(v)
        s += v
        if len(q) > n:
            s -= q.pop(0)
        if len(q) == n:
            out[i] = s / n
    return out


def sig_of(x):
    mi, mo = sma(x, 60), sma(x, 80)
    up = [mi[i] is not None and x[i] > mi[i] * 1.01 for i in range(N)]
    dn = [mo[i] is not None and x[i] < mo[i] * 0.975 for i in range(N)]
    return up, dn


def run(up, dn, start, end, real=False):
    r2 = RR.R2R if real else bt.R2
    i0 = next(i for i, x in enumerate(DAYS) if x >= start)
    i1 = max(i for i, x in enumerate(DAYS) if x <= end)
    eq = peak = 1.0
    mdd, on, pos, pend = 0.0, False, False, None
    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + (r2[i] if pos else bt.RC)
        if pend is not None:
            eq *= 1 - bt.COST * 2
            pos, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if WE[i] and i >= 260:
            on = (not (dn[i] or HOT[i])) if on else (up[i] and not HOT[i])
            if on != pos:
                pend = on
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd


def main():
    L = [f"研究 50：訊號標的（全期 2002- | 前段 | 後段 | 真實；台積電錯價修正 {BAD} 天）"]
    ui, di = sig_of(PX)
    ut, dt = sig_of(TSMC)
    combos = [("加權指數（現行）", ui, di), ("台積電", ut, dt),
              ("兩者都站上才進／任一跌破就出", [a and b for a, b in zip(ui, ut)], [a or b for a, b in zip(di, dt)]),
              ("任一站上就進／兩者都跌破才出", [a or b for a, b in zip(ui, ut)], [a and b for a, b in zip(di, dt)]),
              ("加權進場＋台積電出場", ui, dt), ("台積電進場＋加權出場", ut, di)]
    for nm, up, dn in combos:
        rs = [run(up, dn, a, b) for a, b in R.PER]
        rr = run(up, dn, *R.REAL, real=True)
        L.append(f"{nm:26s} " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in rs) + f" | 真實 {rr[0]:.1%}/{rr[1]:.1%}")
        print(L[-1], flush=True)
    open(os.path.join(HERE, "結果_研究50_訊號標的.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
