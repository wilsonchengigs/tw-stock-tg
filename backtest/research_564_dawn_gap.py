"""研究 564：夜盤收盤（05:00）→ 日盤開盤（08:45）這段報酬，2017-05～
全部、依主策略狀態、依台指 VIX（前一交易日）、依夜盤本身漲跌（15:00→05:00 方向）；成本 3 點後
用法：python -X utf8 backtest/research_564_dawn_gap.py
"""
import os, sys, csv
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_138_金字塔加碼與分段停損 as S138


def main():
    best = {}
    for r in csv.DictReader(open(os.path.join(HERE, "tx_daily_ohlc.csv"), encoding="utf-8")):
        if r["open"] in ("-", "") or r["close"] in ("-", ""):
            continue
        k = (r["date"], r["session"]); v = int(r["volume"] or 0)
        if k not in best or v > best[k][0]:
            best[k] = (v, r["month"], float(r["open"]), float(r["close"]))
    tw = {r["date"]: float(r["vix"]) for r in csv.DictReader(open(os.path.join(HERE, "vixtwn.csv"), encoding="utf-8")) if r["vix"] not in ("", "-")}
    tk = np.array(sorted(tw))
    dd = [str(x)[:10] for x in S138.DAYS]; st = dict(zip(dd, S138.ST)); keys = np.array(sorted(st))
    R = []
    for (d, s) in sorted(best):
        if s != "night" or (d, "day") not in best or best[(d, "night")][1] != best[(d, "day")][1]:
            continue
        n = best[(d, "night")]; dy = best[(d, "day")]
        g = dy[2] / n[3] - 1; nr = n[3] / n[2] - 1
        k = np.searchsorted(tk, d) - 1; i = np.searchsorted(keys, d) - 1
        R.append((d, g * 100, (g - 3 / n[3]) * 100, nr, st[keys[i]], tw[tk[k]] if k >= 0 else 0))
    g = np.array([r[1] for r in R]); gn = np.array([r[2] for r in R]); nr = np.array([r[3] for r in R]); s = np.array([r[4] for r in R]); v = np.array([r[5] for r in R])
    t = lambda y: y.mean() / (y.std(ddof=1) / np.sqrt(len(y)))
    out = [__doc__, f"{R[0][0]}～{R[-1][0]} {len(R)} 天"]
    for lab, m in (("全部", np.ones(len(R), bool)), ("主策略在場", s == 1), ("主策略空手", s == 0), ("台 VIX<20", v < 20), ("台 VIX 20～28", (v >= 20) & (v < 28)), ("台 VIX≥28", v >= 28),
                   ("夜盤漲 >0.5%", nr > 0.005), ("夜盤 ±0.5%", np.abs(nr) <= 0.005), ("夜盤跌 >0.5%", nr < -0.005)):
        out.append(f"  {lab:12s} {m.sum():4d} 天 05:00→08:45 平均 {g[m].mean():+.3f}% t {t(g[m]):+.2f}｜扣 3 點 {gn[m].mean():+.3f}%｜上漲比例 {(g[m]>0).mean()*100:.0f}%")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究564_清晨跳空.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
