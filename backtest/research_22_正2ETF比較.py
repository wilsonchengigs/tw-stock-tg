"""研究 22：同一套訊號下，各檔台股正2 ETF 的實際表現（2016-10 起）
00631L 元大台灣50正2、00675L 富邦臺灣加權正2、00663L 國泰臺灣加權正2（2025-06 有未調整分割，當天改用模擬報酬）
用法：python -X utf8 backtest/research_22_正2ETF比較.py
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402

TW = timezone(timedelta(hours=8))
DAYS, PX, WE = bt.DAYS, bt.PX, bt.WEEK_END
N = len(DAYS)
M60, M80 = bt.get_sma(60), bt.get_sma(80)


def etf(name):
    r = json.load(open(os.path.join(HERE, name + ".json")))
    a = r["indicators"].get("adjclose", [{}])[0].get("adjclose") or r["indicators"]["quote"][0]["close"]
    m = {datetime.fromtimestamp(t, TW).strftime("%Y-%m-%d"): v for t, v in zip(r["timestamp"], a) if v}
    px = [m.get(d) for d in DAYS]
    out, lp = [0.0], None
    for i in range(1, N):
        x = px[i] / lp - 1 if (px[i] and lp) else bt.R2[i]
        if abs(x) > 0.25:  # 未調整分割
            x = bt.R2[i]
        out.append(x)
        if px[i]:
            lp = px[i]
    return out


SIG, st = [], False
for i in range(N):
    if WE[i] and i >= 260:
        st = (not PX[i] < M80[i] * 0.98) if st else (PX[i] > M60[i] * 1.01)
    SIG.append(st)


def run(r, start, end, strat=True):
    i0 = next(i for i, d in enumerate(DAYS) if d >= start)
    i1 = max(i for i, d in enumerate(DAYS) if d <= end)
    eq = peak = 1.0
    mdd, pos, pend = 0.0, False, None
    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + ((r[i] if pos else bt.RC) if strat else r[i])
        if pend is not None:
            eq *= 1 - bt.COST * 2
            pos, pend = pend, None
        if i == i0 and strat:
            pos = SIG[i]
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if WE[i] and SIG[i] != pos:
            pend = SIG[i]
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd


def main():
    L = ["研究 22：各檔正2 ETF 實際表現（2016-10-03～2026-11-21；年化/最大回檔）"]
    end = "2026-11-21"
    for nm, r in (("模擬 2x（bt.R2）", bt.R2), ("00631L 台灣50正2", etf("00631L.TW")), ("00675L 臺灣加權正2", etf("00675L")), ("00663L 國泰加權正2", etf("00663L"))):
        a = run(r, "2016-10-03", end)
        b = run(r, "2016-10-03", end, strat=False)
        L.append(f"{nm:20s} 策略 {a[0]:6.1%}/{a[1]:6.1%}   長抱 {b[0]:6.1%}/{b[1]:6.1%}")
        print(L[-1], flush=True)
    open(os.path.join(HERE, "結果_研究22_正2ETF比較.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
