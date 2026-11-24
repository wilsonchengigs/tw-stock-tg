"""研究 27：Hedgefundie's Excellent Adventure（HFEA）台灣版：正2＋美國長債（1x／2x）固定比例、每季再平衡

原版：UPRO 55%＋TMF 45%（3x 股＋3x 長債），靠股債負相關；2022 股債雙殺時回檔約 -80%。
https://www.bogleheads.org/forum/viewtopic.php?t=272007
台灣版：00631L（模擬 2x）＋VUSTX 長債（台幣，1x 或模擬 2x＝2×長債−1%），股 40～70%，每季再平衡
另加「現行趨勢訊號」版：股票腿出場時股票那部分改持長債
用法：python -X utf8 backtest/research_27_HFEA股債.py
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r02b", os.path.join(HERE, "research_02b_出場持債.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
bt = R.bt
DAYS, N, PX, WE = bt.DAYS, len(bt.DAYS), bt.PX, bt.WEEK_END
QE = [i == N - 1 or (DAYS[i][5:7] in ("03", "06", "09", "12") and DAYS[i][:7] != DAYS[i + 1][:7]) for i in range(N)]
LT = R.A["lt"]
LT2 = [2 * x - 0.01 / bt.TD for x in LT]
M60, M80 = bt.get_sma(60), bt.get_sma(80)
PER = [("1998-01-01", "2026-12-31"), ("1998-01-01", "2012-12-31"), ("2013-01-01", "2026-12-31"), ("2015-09-01", "2026-12-31")]


def run(ws, bond, start, end, trend=False):
    i0 = next(i for i, d in enumerate(DAYS) if d >= start)
    i1 = max(i for i, d in enumerate(DAYS) if d <= end)
    s, b = ws, 1 - ws
    peak, mdd, on, pos, pend = 1.0, 0.0, True, True, None
    for i in range(i0 + 1, i1 + 1):
        s *= 1 + (bt.R2[i] if pos else bond[i])
        b *= 1 + bond[i]
        if pend is not None:
            s *= 1 - bt.COST * 2
            pos, pend = pend, None
        eq = s + b
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if QE[i]:
            s, b = eq * ws, eq * (1 - ws)
            s *= 1 - bt.COST * 0.1
        if trend and WE[i] and i >= 260:
            on = (not PX[i] < M80[i] * 0.98) if on else (PX[i] > M60[i] * 1.01)
            if on != pos:
                pend = on
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd


def main():
    L = ["研究 27：HFEA 台灣版（全期 | 前段 | 後段 | 2015-09～ 模擬；年化/最大回檔）；現行 18.3%/-43.8% | 13.0%/-43.8% | 24.2%/-36.8%"]
    for nm, bond in (("長債 1x", LT), ("長債 2x", LT2)):
        for ws in (0.4, 0.55, 0.7):
            for tr in (False, True):
                cs = [run(ws, bond, a, b, tr) for a, b in PER]
                L.append(f"正2 {ws:.0%}＋{nm} {'＋趨勢' if tr else '      '} " + " | ".join(f"{c * 100:5.1f}%/{m * 100:6.1f}%" for c, m in cs))
                print(L[-1], flush=True)
    open(os.path.join(HERE, "結果_研究27_HFEA股債.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
