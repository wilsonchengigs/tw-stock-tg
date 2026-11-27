"""研究 545：只抱隔夜台指期（13:45 買 → 隔天 08:45 賣）加 VIX 開關，2017～（有夜盤）與全期
- 開關：不設／當天可知的最後美國 VIX（台灣日期之前的收盤）<18／<20／<25；另加「主策略在場」
- 成本每次 3／4／5 點；逐年；平日 vs 週末（相隔 ≥3 天）
- 家族檢定：VIX 序列環狀平移 1000 次，統計量＝開關內每天平均 − 開關外
用法：python -X utf8 backtest/research_545_overnight_filter.py
"""
import os, sys, datetime as dt
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from research_514_pattern_regime import yahoo
import research_138_金字塔加碼與分段停損 as S138
from research_544_overnight_vs_day import load


def main():
    b = load(); ds = sorted(b)
    vix = yahoo("VIX.json"); vk = np.array(sorted(vix))
    dd = [str(x)[:10] for x in S138.DAYS]; st = dict(zip(dd, S138.ST)); keys = np.array(sorted(st))
    R = []
    for p, d in zip(ds, ds[1:]):
        if b[p][1] != b[d][1]:
            continue
        # 13:45 下單時可知：今天（p）之前最後一個美國收盤 VIX；主策略狀態用 p 前一天收盤（p 當天收盤後才更新，保守）
        j = np.searchsorted(vk, p) - 1; i = np.searchsorted(keys, p) - 1
        wk = (dt.date.fromisoformat(d) - dt.date.fromisoformat(p)).days >= 3
        R.append((d, b[d][2] / b[p][3] - 1, b[p][3], vix[vk[j]] if j >= 0 else 99, st[keys[i]] if i >= 0 else 0, wk))
    d_ = np.array([r[0] for r in R]); on = np.array([r[1] for r in R]); px = np.array([r[2] for r in R])
    v = np.array([r[3] for r in R]); s = np.array([r[4] for r in R]); wk = np.array([r[5] for r in R])
    out = [__doc__]
    for start in ("1998", "2017"):
        m0 = d_ >= start
        out.append(f"\n===== {start}～ =====")
        for lab, g in (("不設", np.ones(len(R), bool)), ("VIX<18", v < 18), ("VIX<20", v < 20), ("VIX<25", v < 25), ("主策略在場", s == 1), ("在場且 VIX<25", (s == 1) & (v < 25))):
            for cost in (3, 5):
                x = np.where(g, on - cost / px, 0.0)[m0]
                eq = np.cumprod(1 + x); yrs = m0.sum() / 252
                mdd = (eq / np.maximum.accumulate(eq) - 1).min()
                ys = {}
                for dd_, xx in zip(d_[m0], x):
                    ys[dd_[:4]] = ys.get(dd_[:4], 1) * (1 + xx)
                out.append(f"  {lab:12s} 成本 {cost}：持有 {g[m0].mean()*100:3.0f}% 的夜｜年化 {eq[-1]**(1/yrs)-1:+.1%} 回檔 {mdd:.1%}｜正的年 {sum(1 for q in ys.values() if q>1)}/{len(ys)}")
        m = m0 & (v < 25)
        for lab, w in (("平日", ~wk), ("週末", wk)):
            x = on[m & w] * 100
            out.append(f"  VIX<25 {lab}：{len(x)} 夜 每夜 {x.mean():+.3f}% t {x.mean()/(x.std(ddof=1)/np.sqrt(len(x))):+.1f}")
    # 逐年（2017～ VIX<25、成本 4 點）
    m = d_ >= "2017"
    ys = {}
    for dd_, xx, g in zip(d_[m], (on - 4 / px)[m], (v < 25)[m]):
        if g:
            ys[dd_[:4]] = ys.get(dd_[:4], 0) + xx
    out.append("\n逐年（2017～、VIX<25、成本 4 點，加總%）：" + "  ".join(f"{y}:{q*100:+.0f}%" for y, q in sorted(ys.items())))
    # 家族檢定
    def stat(vv):
        best = -9
        for th in (18, 20, 25):
            a = on[vv < th]; c = on[vv >= th]
            best = max(best, (a.mean() - c.mean()) / np.sqrt(a.var(ddof=1) / len(a) + c.var(ddof=1) / len(c)))
        return best
    obs = stat(v); rng = np.random.default_rng(545); cnt = 0
    for _ in range(1000):
        if stat(np.roll(v, rng.integers(250, len(v) - 250))) >= obs:
            cnt += 1
    out.append(f"VIX 開關家族檢定（全期，門檻 18／20／25 取最大 t）：t {obs:+.2f}，p = {(cnt+1)/1001:.3f}")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究545_隔夜加開關.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
