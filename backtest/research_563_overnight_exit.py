"""研究 563：在場高 VIX 隔夜（13:45 進）出場時點：夜盤 05:00 收盤 vs 隔天 08:45 開盤 vs 隔天 13:45 收盤
tx_daily_ohlc 夜盤列的日期＝該夜盤之後那個交易日（d 列＝d 前一天 15:00 開始的夜盤，與 tx_1min 的 trade_day 一致）
2017-05～（有夜盤）；門檻台指 VIX（前一交易日）≥25／28 與美國 VIX≥28；成本 3 點
用法：python -X utf8 backtest/research_563_overnight_exit.py
"""
import os, sys, csv
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from research_514_pattern_regime import yahoo
import research_138_金字塔加碼與分段停損 as S138


def main():
    best = {}
    for r in csv.DictReader(open(os.path.join(HERE, "tx_daily_ohlc.csv"), encoding="utf-8")):
        if r["open"] in ("-", "") or r["close"] in ("-", ""):
            continue
        k = (r["date"], r["session"]); v = int(r["volume"] or 0)
        if k not in best or v > best[k][0]:
            best[k] = (v, r["month"], float(r["open"]), float(r["close"]))
    ds = sorted(d for d, s in best if s == "day")
    us = yahoo("VIX.json"); uk = np.array(sorted(us))
    tw = {r["date"]: float(r["vix"]) for r in csv.DictReader(open(os.path.join(HERE, "vixtwn.csv"), encoding="utf-8")) if r["vix"] not in ("", "-")}
    tk = np.array(sorted(tw))
    dd = [str(x)[:10] for x in S138.DAYS]; st = dict(zip(dd, S138.ST)); keys = np.array(sorted(st))
    out = [__doc__]
    for lab, cond in (("美 VIX≥28", lambda p: us[uk[np.searchsorted(uk, p) - 1]] >= 28), ("台 VIX≥28", lambda p: tw[tk[np.searchsorted(tk, p) - 1]] >= 28), ("台 VIX≥25", lambda p: tw[tk[np.searchsorted(tk, p) - 1]] >= 25)):
        a = []; b = []; c = []
        for p, d in zip(ds, ds[1:]):
            if p < "2017-05-16" or (d, "night") not in best:
                continue
            day_p = best[(p, "day")]; nt = best[(d, "night")]; day_d = best[(d, "day")]
            if not (day_p[1] == nt[1] == day_d[1]):
                continue
            if st[keys[np.searchsorted(keys, p) - 1]] != 1 or not cond(p):
                continue
            a.append(day_d[2] / day_p[3] - 1 - 3 / day_p[3]); b.append(nt[3] / day_p[3] - 1 - 3 / day_p[3]); c.append(day_d[3] / day_p[3] - 1 - 3 / day_p[3])
        a = np.array(a) * 100; b = np.array(b) * 100; c = np.array(c) * 100
        t = lambda y: y.mean() / (y.std(ddof=1) / np.sqrt(len(y)))
        out.append(f"  在場＋{lab}：{len(a)} 夜｜05:00 夜盤收出 {b.mean():+.3f}% t {t(b):+.2f}（標準差 {b.std():.2f}）｜08:45 開盤出 {a.mean():+.3f}% t {t(a):+.2f}（{a.std():.2f}）｜隔天 13:45 出 {c.mean():+.3f}% t {t(c):+.2f}（{c.std():.2f}）")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究563_隔夜出場時點.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
