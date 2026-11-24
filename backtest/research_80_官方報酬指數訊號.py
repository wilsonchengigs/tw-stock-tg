"""研究 80（待研究 22）：訊號改用證交所官方「發行量加權股價報酬指數」（含息，MFI94U，2003～）
研究 21 用近似報酬指數（配息平均攤在 6/15～9/15）發現：除息季誤出場減少，但近 10 年回檔加深。這裡用官方真實報酬指數驗證。
規則：新版（進場 MA60×1.01、出場 MA80×0.975、融資過熱濾網），只換「算均線與比較的指數」；報酬計算不變（00631L 模擬／真實）
比較期間 2004-01～（報酬指數要先累積 80 日均線）：全期 | 2004-2012 | 2013- | 真實 2015-09～；另做鄰近參數
用法：python -X utf8 backtest/research_80_官方報酬指數訊號.py
"""
import csv
import importlib.util
import itertools
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r41", os.path.join(HERE, "research_41_總經濾網.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
bt, DAYS, PX, N, WE, HOT = R.bt, R.DAYS, R.PX, R.N, R.WE, R.HOT
RR = R.R40.R32.R
PER = [("2004-01-01", "2026-12-31"), ("2004-01-01", "2012-12-31"), ("2013-01-01", "2026-12-31")]
REAL = ("2015-09-01", "2026-12-31")

tr = {r["date"]: float(r["tr"]) for r in csv.DictReader(open(os.path.join(HERE, "tr_index_daily.csv"), encoding="utf-8")) if r["tr"]}
# 對齊台股交易日：缺的用前值；2003 前沒有 → None
TR, last = [], None
for d in DAYS:
    last = tr.get(d, last if d >= "2003-01-02" else None)
    TR.append(last)
MISSING = sum(1 for d in DAYS if d >= "2003-01-02" and d not in tr)


def sma(x, n):
    out, s, q = [None] * len(x), 0.0, []
    for i, v in enumerate(x):
        if v is None:
            continue
        q.append(v)
        s += v
        if len(q) > n:
            s -= q.pop(0)
        if len(q) == n:
            out[i] = s / n
    return out


def run(src, ein, bi, eo, bo, start, end, real=False, log=None):
    r2 = RR.R2R if real else bt.R2
    mi, mo = sma(src, ein), sma(src, eo)
    i0 = next(i for i, x in enumerate(DAYS) if x >= start)
    i1 = max(i for i, x in enumerate(DAYS) if x <= end)
    eq = peak = 1.0
    mdd, on, pos, pend, n_q3 = 0.0, False, False, None, 0
    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + (r2[i] if pos else bt.RC)
        if pend is not None:
            eq *= 1 - bt.COST * 2
            if pos and not pend and "07-01" <= DAYS[i][5:] <= "09-30":
                n_q3 += 1
            pos, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if WE[i] and mi[i] is not None and mo[i] is not None:
            p = src[i]
            on = (not (p < mo[i] * bo or HOT[i])) if on else (p > mi[i] * bi and not HOT[i])
            if on != pos:
                pend = on
                if log is not None:
                    log.append((DAYS[i], "進" if on else "出"))
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd, n_q3


def fmt(rs, rr):
    return " | ".join(f"{c:.1%}/{m:.1%}" for c, m, _ in rs) + f" | 真實 {rr[0]:.1%}/{rr[1]:.1%} | 7～9 月出場 {rs[0][2]} 次"


def main():
    L = [f"研究 80：訊號用官方報酬指數 vs 價格指數（新版規則含融資濾網；全期 2004- | 2004-2012 | 2013- | 真實；官方資料缺 {MISSING} 天以前值補）"]
    for nm, src in (("價格指數（現行）", PX), ("官方報酬指數", TR)):
        rs = [run(src, 60, 1.01, 80, 0.975, a, b) for a, b in PER]
        rr = run(src, 60, 1.01, 80, 0.975, *REAL, real=True)
        L.append(f"{nm:14s} {fmt(rs, rr)}")
    L.append("\n鄰近參數（每行：價格指數 → 報酬指數）")
    wins = tot = 0
    for ein, bi, eo, bo in itertools.product((50, 60, 70), (1.0, 1.01), (70, 80, 90), (0.97, 0.975, 0.98)):
        a = [run(PX, ein, bi, eo, bo, s, e) for s, e in PER]
        b = [run(TR, ein, bi, eo, bo, s, e) for s, e in PER]
        ar = run(PX, ein, bi, eo, bo, *REAL, real=True)
        br = run(TR, ein, bi, eo, bo, *REAL, real=True)
        tot += 1
        wins += b[0][0] > a[0][0]
        L.append(f"  MA{ein}x{bi}/MA{eo}x{bo}: 全期 {a[0][0]:.1%}→{b[0][0]:.1%}（回檔 {a[0][1]:.1%}→{b[0][1]:.1%}）、後段 {a[2][0]:.1%}→{b[2][0]:.1%}、真實 {ar[0]:.1%}→{br[0]:.1%}（{ar[1]:.1%}→{br[1]:.1%}）")
    L.append(f"\n報酬指數全期勝價格指數：{wins}/{tot} 組")
    la, lb = [], []
    run(PX, 60, 1.01, 80, 0.975, "2004-01-01", "2026-12-31", log=la)
    run(TR, 60, 1.01, 80, 0.975, "2004-01-01", "2026-12-31", log=lb)
    sa, sb = set(la), set(lb)
    L.append("\n進出場日期差異（現行參數）：只出現在價格指數版 " + "、".join(f"{d}{x}" for d, x in sorted(sa - sb))
             + "；只出現在報酬指數版 " + "、".join(f"{d}{x}" for d, x in sorted(sb - sa)))
    out = "\n".join(L) + "\n"
    print("\n".join(x for x in L if not x.startswith("  MA")))
    open(os.path.join(HERE, "結果_研究80_官方報酬指數訊號.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
