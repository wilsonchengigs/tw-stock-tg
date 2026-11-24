"""研究 56：出場時持黃金（GC=F 換台幣）代替現金；以及「黃金在自身 MA200 之上才持」
新版基準（出場 2.5%＋融資過熱）；黃金用前一晚美國收盤、匯率清洗版
用法：python -X utf8 backtest/research_56_出場持黃金.py
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r41", os.path.join(HERE, "research_41_總經濾網.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
spec = importlib.util.spec_from_file_location("r09", os.path.join(HERE, "research_09_多市場分散.py"))
R09 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R09)
bt, DAYS, PX, N, WE, HOT = R.bt, R.DAYS, R.PX, R.N, R.WE, R.HOT
RR = R.R40.R32.R
GOLD = R.us("GOLD")
GR = [0.0]
for i in range(1, N):
    a, b = GOLD[i - 1], GOLD[i]
    fa, fb = R09.fx_at(DAYS[i - 1]), R09.fx_at(DAYS[i])
    if a and b:
        r = b / a - 1
        if fa and fb:
            r = (1 + r) * fb / fa - 1
        GR.append(r if abs(r) < 0.15 else 0.0)
    else:
        GR.append(bt.RC)
GMA = R.sma_arr([g for g in GOLD], 200)


def run(mode, start, end, real=False):
    r2 = RR.R2R if real else bt.R2
    i0 = next(i for i, x in enumerate(DAYS) if x >= start)
    i1 = max(i for i, x in enumerate(DAYS) if x <= end)
    eq = peak = 1.0
    mdd, on, pos, pend, gold_on = 0.0, False, False, None, False
    for i in range(i0, i1 + 1):
        if i > i0:
            if pos:
                eq *= 1 + r2[i]
            else:
                eq *= 1 + (GR[i] if (mode == "gold" or (mode == "gold_trend" and gold_on)) else bt.RC)
        if pend is not None:
            eq *= 1 - bt.COST * 2.5
            pos, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if WE[i] and i >= 260:
            gold_on = GMA[i] is not None and GOLD[i] is not None and GOLD[i] > GMA[i]
            on = (not (PX[i] < R.M80[i] * 0.975 or HOT[i])) if on else (PX[i] > R.M60[i] * 1.01 and not HOT[i])
            if on != pos:
                pend = on
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd


def main():
    L = ["研究 56：出場持黃金（全期 2002- | 前段 | 後段 | 真實）"]
    for nm, mode in (("現金（新版）", "cash"), ("一律黃金", "gold"), ("黃金在 MA200 上才持", "gold_trend")):
        rs = [run(mode, a, b) for a, b in R.PER]
        rr = run(mode, *R.REAL, real=True)
        L.append(f"{nm:18s} " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in rs) + f" | 真實 {rr[0]:.1%}/{rr[1]:.1%}")
        print(L[-1], flush=True)
    open(os.path.join(HERE, "結果_研究56_出場持黃金.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
