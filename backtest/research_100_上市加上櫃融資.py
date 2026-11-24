"""研究 100（待研究 12 的最後一項）：融資過熱改用「上市＋上櫃」融資，或只用上櫃
資料：上市融資（margin_tw.csv，日）取每週最後交易日；上櫃融資（otc_margin_weekly.csv，櫃買中心，2007～，週）
定義（都用週資料，52 週 ≈ 250 日）：比值＝融資 ÷ 加權指數；偏離＝比值 ÷ 近 52 週均 − 1；z＝(比值−均)÷標準差
過熱：偏離 > th 或 z > 2（同 v3）；週五判斷（上櫃只有週資料，三種定義都改週頻才公平）
規則：MA60×1.01 進、MA80×0.975 出、過熱出場不進、過熱解除（偏離 < 12.5% 且 z ≤ 2）且在出場線上就回補
期間：2008-2026（上櫃資料要先累積 52 週）、2008-2012、2013-2026、真實 2015-09～
用法：python -X utf8 backtest/research_100_上市加上櫃融資.py
"""
import bisect
import csv
import importlib.util
import itertools
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("v3", os.path.join(HERE, "strategy_v3.py"))
V = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V)
bt, DAYS, PX, N, WE = V.bt, V.DAYS, V.PX, V.N, V.WE

LIST = {r["date"]: float(r["balance"]) for r in csv.DictReader(open(os.path.join(HERE, "margin_tw.csv"), encoding="utf-8")) if r["balance"]}
OTC = {r["date"]: float(r["amount"]) for r in csv.DictReader(open(os.path.join(HERE, "otc_margin_weekly.csv"), encoding="utf-8")) if r["amount"]}
WK = [i for i in range(N) if WE[i] and DAYS[i] >= "2007-01-01" and DAYS[i] in OTC and DAYS[i] in LIST]


def weekly_heat(kind):
    """回傳 {台股日索引: (偏離, z)}，只在週資料點"""
    vals = []
    for i in WK:
        d = DAYS[i]
        m = LIST[d] if kind == "上市" else OTC[d] if kind == "上櫃" else LIST[d] + OTC[d]
        vals.append((i, m / PX[i]))
    out = {}
    for k in range(51, len(vals)):
        w = [v for _, v in vals[k - 51:k + 1]]
        avg = sum(w) / 52
        sd = math.sqrt(sum((x - avg) ** 2 for x in w) / 52)
        i, v = vals[k]
        out[i] = (v / avg - 1, (v - avg) / sd if sd else 0.0)
    return out


def run(heat, start, end, th=0.175, zth=2.0, real=False):
    r2 = V.R2R if real else bt.R2
    i0 = next(i for i, x in enumerate(DAYS) if x >= start)
    i1 = max(i for i, x in enumerate(DAYS) if x <= end)
    eq = peak = 1.0
    mdd, st, heat_out, pos, pend, last = 0.0, 0, False, False, None, None
    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + (r2[i] if pos else bt.RC)
        if pend is not None:
            eq *= 1 - bt.COST * 2
            pos, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if heat and i in heat:
            last = heat[i]
        if WE[i] and i >= 260:
            hot = heat is not None and last is not None and (last[0] > th or last[1] > zth)
            p = PX[i]
            above = p >= V.M80[i] * 0.975
            if st == 0:
                if heat_out and not above:
                    heat_out = False
                cooled = last is None or (last[0] < 0.125 and last[1] <= zth)
                if (p > V.M60[i] * 1.01 and not hot) or (heat_out and cooled and above):
                    st, heat_out = 1, False
            elif hot:
                st, heat_out = 0, True
            elif not above:
                st, heat_out = 0, False
            if (st == 1) != pos:
                pend = st == 1
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd


def main():
    pers = (("2008-01-01", "2026-12-31"), ("2008-01-01", "2012-12-31"), ("2013-01-01", "2026-12-31"))
    L = [f"研究 100：上市／上櫃／合計融資過熱（週資料 52 週；2008- | 2008-2012 | 2013- | 真實）；上櫃資料 {len(OTC)} 週（{min(OTC)}～{max(OTC)}）",
         f"上櫃占合計融資比例：{min(OTC)} {OTC[min(OTC)] / (OTC[min(OTC)] + LIST.get(min(OTC), 1)):.0%}、{max(OTC)} {OTC[max(OTC)] / (OTC[max(OTC)] + LIST.get(max(OTC), 1)):.0%}"]
    heats = {"無濾網": {}, "上市（週）": weekly_heat("上市"), "上市＋上櫃（週）": weekly_heat("合計"), "只有上櫃（週）": weekly_heat("上櫃")}
    for nm, h in heats.items():
        for th, zt in ((0.175, 2.0),) if nm == "無濾網" else itertools.product((0.15, 0.175, 0.20), (1.75, 2.0, 2.25)):
            rs = [run(h if h else None, a, b, th, zt) for a, b in pers]
            rr = run(h if h else None, "2015-09-01", "2026-12-31", th, zt, real=True)
            tag = nm if nm == "無濾網" else f"{nm} 偏離{th:.1%} z{zt}"
            L.append(f"{tag:28s} " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in rs) + f" | 真實 {rr[0]:.1%}/{rr[1]:.1%}")
            print(L[-1], flush=True)
    for nm in ("上市（週）", "上市＋上櫃（週）"):
        h = heats[nm]
        k = max(h)
        L.append(f"最新（{DAYS[k]}）{nm}：偏離 {h[k][0]:+.1%}、z {h[k][1]:+.2f}")
    out = "\n".join(L) + "\n"
    open(os.path.join(HERE, "結果_研究100_上市加上櫃融資.txt"), "w", encoding="utf-8").write(out)
    print("\n".join(L[-2:]))


if __name__ == "__main__":
    main()
