"""研究 567：5 年資產情境（比照研究 410）——現行配置 vs 加兩候選（日內順勢 1x、在場高 VIX 隔夜 1x 限合計 1.5x 近似為 1x）
日報酬序列 2010～（研究 551）；區塊拔靴（區塊 60 天）10,000 條、5 年；期初 100 萬、每年年底存 100 萬
用法：python -X utf8 backtest/research_567_five_year_with_candidates.py
"""
import io, contextlib, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
with contextlib.redirect_stdout(io.StringIO()):

    import research_411_實際配置含V as A
import research_522_intraday_trend_robust as M
from research_514_pattern_regime import yahoo
import research_138_金字塔加碼與分段停損 as S138
from research_531_intraday_by_main_state import trade
from research_544_overnight_vs_day import load


def series():
    R = A.R
    base = R.main + R.padd + R.dadd + A.vadd
    D = [str(x)[:10] for x in R.D]; idx = {d: i for i, d in enumerate(D)}
    vix = yahoo("VIX.json"); vk = np.array(sorted(vix))
    dd = [str(x)[:10] for x in S138.DAYS]; st = dict(zip(dd, S138.ST)); keys = np.array(sorted(st))
    state = lambda d: st[keys[np.searchsorted(keys, d) - 1]]; vprev = lambda d: vix[vk[np.searchsorted(vk, d) - 1]]
    days = M.load_idx(); intr = np.zeros(len(D))
    for d, i in idx.items():
        if d in days and state(d) == 0 and vprev(d) >= 18:
            t = trade(days[d])
            if t:
                intr[i] = t[1] / 100
    b = load(); ds = sorted(b); night = np.zeros(len(D))
    for p, d in zip(ds, ds[1:]):
        if b[p][1] == b[d][1] and d in idx and state(p) == 1 and vprev(p) >= 28:
            night[idx[d]] += 0.79 * (b[d][2] / b[p][3] - 1 - 3 / b[p][3])  # 研究 554 限名目後平均 0.79x
    m = np.array([d >= "2010-01-04" for d in D])
    return base[m], (base + intr + night)[m]


def sim(r, rng, N=10000, years=5, L=60):
    TD = 245; n = len(r); res = np.zeros(N); dds = np.zeros(N)
    for k in range(N):
        path = []
        while len(path) < years * TD:
            s = rng.integers(0, n - L); path.extend(r[s:s + L])
        path = np.array(path[:years * TD]); w = 100.0; peak = w; mdd = 0
        for y in range(years):
            seg = path[y * TD:(y + 1) * TD]
            eq = w * np.cumprod(1 + seg); run = np.maximum.accumulate(np.concatenate([[max(peak, w)], eq]))[1:]; mdd = min(mdd, (eq / run - 1).min()); peak = run[-1]
            w = eq[-1] + 100
        res[k] = w - 100; dds[k] = mdd
    return res, dds


def main():
    a, b = series(); rng = np.random.default_rng(567)
    out = [__doc__]
    for lab, r in (("現行", a), ("加兩候選", b)):
        res, dds = sim(r, rng)
        q = np.percentile(res, [10, 25, 50, 75, 90])
        out.append(f"  {lab}：5 年後（萬）10／25／50／75／90 分位 {q[0]:.0f}／{q[1]:.0f}／{q[2]:.0f}／{q[3]:.0f}／{q[4]:.0f}｜投入 500 萬以下 {np.mean(res<500)*100:.1f}%｜期間回檔中位 {np.median(dds)*100:.0f}%、最差 10% {np.percentile(dds,10)*100:.0f}%")
    out.append("  ⚠️ 用 2010～ 的報酬抽樣（含 2026 +239% 這種極端年），偏樂觀；研究 410 的 2002～ 版本中位約 1,300 萬可當保守參考")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究567_五年情境加候選.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
