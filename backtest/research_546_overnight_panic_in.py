"""研究 546：主策略在場＋高 VIX 時「收盤買台指期、隔天開盤賣」（隔夜反彈）
- 訊號（13:45 可知）：主策略 v3 前一天收盤狀態＝在場；最後一個美國收盤 VIX ≥ 門檻（20／22／25／28／30）
- 報酬：台指期近月 13:45 收 → 隔天 08:45 開，成本 3 點；剔除換月
- 兩段（1998–2012／2013～）、逐年、門檻家族檢定（VIX 序列環狀平移 1000 次、門檻取最大 t）
- 與現有規則重疊：同一夜是否 P 前一晚觸發（S&P ≤-2%）、V 持有中（不精算，只看 P）
- 另：台股當天跌幅分組（當天日盤 <-1%、-1～0、>0）
用法：python -X utf8 backtest/research_546_overnight_panic_in.py
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from research_514_pattern_regime import yahoo
import research_138_金字塔加碼與分段停損 as S138
from research_544_overnight_vs_day import load


def main():
    b = load(); ds = sorted(b)
    vix = yahoo("VIX.json"); vk = np.array(sorted(vix))
    spx = yahoo("GSPC.json"); sk = np.array(sorted(spx))
    dd = [str(x)[:10] for x in S138.DAYS]; st = dict(zip(dd, S138.ST)); keys = np.array(sorted(st))
    R = []
    for p, d in zip(ds, ds[1:]):
        if b[p][1] != b[d][1]:
            continue
        j = np.searchsorted(vk, p) - 1; i = np.searchsorted(keys, p) - 1; k = np.searchsorted(sk, p) - 1
        if j < 0 or i < 0 or k < 1:
            continue
        on = b[d][2] / b[p][3] - 1 - 3 / b[p][3]
        dayret = b[p][3] / b[p][2] - 1
        R.append((d, on * 100, vix[vk[j]], st[keys[i]], spx[sk[k]] / spx[sk[k - 1]] - 1 <= -0.02, dayret))
    d_ = np.array([r[0] for r in R]); x = np.array([r[1] for r in R]); v = np.array([r[2] for r in R])
    s = np.array([r[3] for r in R]); pp = np.array([r[4] for r in R]); dr = np.array([r[5] for r in R])
    t = lambda y: y.mean() / (y.std(ddof=1) / np.sqrt(len(y)))
    out = [__doc__, f"{d_[0]}～{d_[-1]}，{len(R)} 夜"]
    for th in (20, 22, 25, 28, 30):
        m = (s == 1) & (v >= th)
        a = m & (d_ < "2013"); c = m & (d_ >= "2013")
        ys = {}
        for dd_, xx in zip(d_[m], x[m]):
            ys[dd_[:4]] = ys.get(dd_[:4], 0) + xx
        out.append(f"  在場＋VIX≥{th}：{m.sum():4d} 夜（{m.sum()/28:.0f}/年）每夜 {x[m].mean():+.3f}% t {t(x[m]):+.2f} 勝率 {(x[m]>0).mean()*100:.0f}%｜1998–2012 {x[a].mean():+.3f}%（{a.sum()}）2013～ {x[c].mean():+.3f}%（{c.sum()}）｜正的年 {sum(1 for q in ys.values() if q>0)}/{len(ys)}")
    m = (s == 1) & (v >= 25)
    out.append(f"  對照 空手＋VIX≥25：{((s==0)&(v>=25)).sum()} 夜 每夜 {x[(s==0)&(v>=25)].mean():+.3f}%；在場＋VIX<25：{x[(s==1)&(v<25)].mean():+.3f}%")
    out.append(f"  在場＋VIX≥25 與 P 前晚觸發同夜：{(m & pp).sum()} 夜 每夜 {x[m & pp].mean():+.3f}%｜非 P 夜 {(m & ~pp).sum()} 夜 每夜 {x[m & ~pp].mean():+.3f}% t {t(x[m & ~pp]):+.2f}")
    for lab, g in (("當天日盤跌 >1%", dr < -0.01), ("跌 0～1%", (dr >= -0.01) & (dr < 0)), ("當天漲", dr >= 0)):
        q = m & g
        out.append(f"  在場＋VIX≥25 {lab}：{q.sum()} 夜 每夜 {x[q].mean():+.3f}% t {t(x[q]):+.2f}")
    ys = {}
    for dd_, xx in zip(d_[m], x[m]):
        ys[dd_[:4]] = ys.get(dd_[:4], 0) + xx
    out.append("  逐年（≥25，加總%）：" + "  ".join(f"{y}:{q:+.1f}({sum(1 for z in d_[m] if z[:4]==y)})" for y, q in sorted(ys.items())))
    def stat(vv):
        best = -9
        for th in (20, 22, 25, 28, 30):
            a = x[(s == 1) & (vv >= th)]; c = x[(s == 1) & (vv < th)]
            best = max(best, (a.mean() - c.mean()) / np.sqrt(a.var(ddof=1) / len(a) + c.var(ddof=1) / len(c)))
        return best
    obs = stat(v); rng = np.random.default_rng(546); cnt = 0
    for _ in range(1000):
        if stat(np.roll(v, rng.integers(250, len(v) - 250))) >= obs:
            cnt += 1
    out.append(f"  家族檢定（VIX 平移、門檻 20～30 取最大 t）：t {obs:+.2f}，p = {(cnt+1)/1001:.3f}")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究546_在場高VIX隔夜.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
