"""研究 515：研究 514 的「VIX ≥18 才做」盤中型態，門檻穩健度與是否只是波動放大
- 型態：|跳空|>0.3% 日「第 2 頭較低＋破頸線」做空、開高日「第 2 底較高＋站上頸線」做多（同 513／514）
- (a) VIX 門檻 14～26 每 2 點：門檻以上／以下的超額（扣同分鐘基準）與兩段
- (b) 以風險正規化：超額 ÷ 當天 ADR20，看 VIX 高時是否「每單位波動」也比較好（不是的話，只是點數放大）
- (c) 家族檢定：VIX 序列對交易日環狀平移 1000 次，看「門檻以上 − 以下」差距（最大 t over 門檻）的 p 值
- (d) 逐年：VIX≥18 版本每年筆數、超額
用法：python -X utf8 backtest/research_515_pattern_vix_gate.py
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_511_higher_low as R
from research_514_pattern_regime import yahoo


def tstat(x):
    x = np.asarray(x)
    return x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 else np.nan


def main():
    gaps = R.tx_gaps(); days = R.load_days(); adr = R.adr20(days); drift = R.drift_table(days)
    vix = yahoo("VIX.json"); vk = np.array(sorted(vix))
    alld = sorted(d for d in days if d in gaps and d in adr)
    vprev = {}
    for d in alld:
        i = np.searchsorted(vk, d) - 1
        if i >= 0:
            vprev[d] = vix[vk[i]]
    out = [__doc__]
    TH = list(range(14, 28, 2))
    for side, name, gf in ((-1, "開低＋開高做空", lambda g: abs(g) > 0.003), (1, "開高做多", lambda g: g > 0.003)):
        S = [s for s in R.setups(days, gaps, adr, side, "相對", 0.25, "E2") if s["minute"] <= 180 and gf(s["gap"]) and s["day"] in vprev]
        day = np.array([s["day"] for s in S])
        p = np.array([s["pnl"][("無", None)] for s in S])
        ex = p - np.array([side * drift[s["minute"]] for s in S])
        a = np.array([adr[s["day"]] * 100 for s in S])
        v = np.array([vprev[s["day"]] for s in S])
        ins = day < R.SPLIT
        out.append(f"\n===== {name}：{len(S)} 筆 =====")
        out.append("(a)(b) 門檻｜以上：筆數 超額% t 內/外｜以下：筆數 超額% t｜每單位 ADR 超額 以上/以下")
        for th in TH:
            hi = v >= th; lo = ~hi
            out.append(f"  VIX {th:2d}｜上 {hi.sum():3d} {ex[hi].mean():+.3f}% t {tstat(ex[hi]):+.2f} 內 {ex[hi&ins].mean():+.3f} 外 {ex[hi&~ins].mean():+.3f}｜下 {lo.sum():3d} {ex[lo].mean():+.3f}% t {tstat(ex[lo]):+.2f}｜/ADR {np.mean(ex[hi]/a[hi]):+.3f} / {np.mean(ex[lo]/a[lo]):+.3f}")
        # ADR 本身當門檻做對照：取與 VIX18 同樣筆數的高 ADR
        k = (v >= 18).sum()
        order = np.argsort(-a); topa = np.zeros(len(a), bool); topa[order[:k]] = True
        out.append(f"  對照：ADR 最高 {k} 筆 超額 {ex[topa].mean():+.3f}% t {tstat(ex[topa]):+.2f}｜其餘 {ex[~topa].mean():+.3f}%；兩者重疊 {(topa & (v>=18)).sum()} 筆")
        both = (v >= 18) & topa; vonly = (v >= 18) & ~topa; aonly = topa & ~(v >= 18)
        for lab, m in (("VIX≥18 且高 ADR", both), ("只有 VIX≥18", vonly), ("只有高 ADR", aonly)):
            if m.sum() > 5:
                out.append(f"    {lab}：{m.sum()} 筆 超額 {ex[m].mean():+.3f}% t {tstat(ex[m]):+.2f}")
        # (c) 家族檢定：VIX 序列在交易日上環狀平移
        vs = np.array([vprev[d] for d in alld]); idx = {d: i for i, d in enumerate(alld)}
        pos = np.array([idx[d] for d in day])

        def stat(vv):
            best = -9
            for th in TH:
                hi = vv >= th
                if hi.sum() < 20 or (~hi).sum() < 20:
                    continue
                diff = ex[hi].mean() - ex[~hi].mean()
                se = np.sqrt(ex[hi].var(ddof=1) / hi.sum() + ex[~hi].var(ddof=1) / (~hi).sum())
                best = max(best, diff / se)
            return best
        obs = stat(vs[pos])
        rng = np.random.default_rng(514)
        n = len(vs); cnt = 0; B = 1000
        for _ in range(B):
            sh = rng.integers(250, n - 250)
            if stat(np.roll(vs, sh)[pos]) >= obs:
                cnt += 1
        out.append(f"(c) 上−下 差距最大 t {obs:+.2f}，環狀平移 {B} 次 p = {(cnt+1)/(B+1):.3f}")
        # (d) 逐年
        out.append("(d) 逐年（VIX≥18）：")
        yrs = sorted(set(d[:4] for d in day))
        line = []
        for y in yrs:
            m = (v >= 18) & np.array([d[:4] == y for d in day])
            if m.sum():
                line.append(f"{y}:{m.sum()}筆{ex[m].mean()*390:+.0f}點")
        out.append("  " + "  ".join(line))
        m = v >= 18
        out.append(f"  正的年數 {sum(1 for y in yrs if ((v>=18)&np.array([d[:4]==y for d in day])).sum() and ex[(v>=18)&np.array([d[:4]==y for d in day])].mean()>0)}／{sum(1 for y in yrs if ((v>=18)&np.array([d[:4]==y for d in day])).sum())}；未扣基準平均 {p[m].mean():+.3f}%（≈{p[m].mean()*390:+.0f} 點）勝率 {(p[m]>0).mean()*100:.1f}%")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究515_型態VIX門檻.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
