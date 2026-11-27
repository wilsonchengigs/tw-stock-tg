"""研究 556：在場高 VIX 隔夜（研究 546）改用台指 VIX
台指 VIX 用前一交易日收盤（保守；當天 13:45 前的值盤中才有）；門檻 25～40；對照美國 VIX ≥28
2002～（台指 VIX 起點）；每夜、t、兩段、家族檢定（台指 VIX 平移）
用法：python -X utf8 backtest/research_556_overnight_twvix.py
"""
import os, sys, csv
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from research_514_pattern_regime import yahoo
import research_138_金字塔加碼與分段停損 as S138
from research_544_overnight_vs_day import load


def main():
    b = load(); ds = sorted(b)
    us = yahoo("VIX.json"); uk = np.array(sorted(us))
    tw = {r["date"]: float(r["vix"]) for r in csv.DictReader(open(os.path.join(HERE, "vixtwn.csv"), encoding="utf-8")) if r["vix"] not in ("", "-")}
    tk = np.array(sorted(tw))
    dd = [str(x)[:10] for x in S138.DAYS]; st = dict(zip(dd, S138.ST)); keys = np.array(sorted(st))
    R = []
    for p, d in zip(ds, ds[1:]):
        if b[p][1] != b[d][1] or p < "2002-01-02":
            continue
        i = np.searchsorted(keys, p) - 1; j = np.searchsorted(uk, p) - 1; k = np.searchsorted(tk, p) - 1
        if i < 0 or k < 0:
            continue
        R.append((d, (b[d][2] / b[p][3] - 1 - 3 / b[p][3]) * 100, st[keys[i]], us[uk[j]], tw[tk[k]]))
    d_ = np.array([r[0] for r in R]); x = np.array([r[1] for r in R]); s = np.array([r[2] for r in R]); u = np.array([r[3] for r in R]); w = np.array([r[4] for r in R])
    t = lambda y: y.mean() / (y.std(ddof=1) / np.sqrt(len(y)))
    out = [__doc__]
    for lab, m in [("美 VIX≥28", (s == 1) & (u >= 28))] + [(f"台 VIX≥{th}", (s == 1) & (w >= th)) for th in (25, 28, 30, 33, 36, 40)]:
        a = m & (d_ < "2013"); c = m & (d_ >= "2013")
        out.append(f"  在場＋{lab:9s}：{m.sum():4d} 夜 每夜 {x[m].mean():+.3f}% t {t(x[m]):+.2f}｜2002–12 {x[a].mean():+.3f}%（{a.sum()}）2013～ {x[c].mean():+.3f}%（{c.sum()}）")
    def stat(vv):
        best = -9
        for th in (25, 28, 30, 33, 36, 40):
            a = x[(s == 1) & (vv >= th)]; c = x[(s == 1) & (vv < th)]
            if len(a) > 20:
                best = max(best, (a.mean() - c.mean()) / np.sqrt(a.var(ddof=1) / len(a) + c.var(ddof=1) / len(c)))
        return best
    obs = stat(w); rng = np.random.default_rng(556); cnt = 0
    for _ in range(1000):
        if stat(np.roll(w, rng.integers(250, len(w) - 250))) >= obs:
            cnt += 1
    out.append(f"  家族檢定（台指 VIX 平移）：t {obs:+.2f}，p = {(cnt+1)/1001:.3f}")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究556_隔夜台指VIX.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
