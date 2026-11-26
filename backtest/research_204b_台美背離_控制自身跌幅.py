"""研究 204b：台美背離補漲——控制台股自身跌幅後，美股背離還有沒有額外資訊？逐筆、晚一天進場、成本

研究 204 發現：加權 20 日報酬 − S&P 20 日報酬 ≤ -10% 後 5 日相對報酬 +1.7%（家族 p 0.007）。
但背離大的日子通常台股自己也大跌，可能只是「大跌後反彈」（研究 182：不顯著）。
(A) 同跌幅對照：每個事件 k，對照＝所有 |tw20[j] − tw20[k]| ≤ 2% 且 背離 > −5% 的日子（台股跌一樣多、但美股也跌）
    超額＝事件 5／20 日報酬 − 對照平均；家族（3 門檻 × 5／20 日 × 絕對）環狀平移 1,000 次
(B) 逐筆：日期、tw20、us20、背離、5 日絕對、主策略（v3 在不在場用 MA80×0.975 出／MA60×1.01 進近似）
(C) 執行：訊號日收盤進 vs 隔天收盤進，抱 5 日；成本每筆來回 0.1%（台指期約 20 點＋稅）／0.3%（00631L）
用法：python -X utf8 backtest/research_204b_台美背離_控制自身跌幅.py
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_204_台美背離補漲 as r  # noqa: E402

TW, US, DAYS, N = r.TW, r.US, r.DAYS, r.N


def ret(a, k, h):
    return a[k + h] / a[k] - 1 if 0 <= k and k + h < N else np.nan


tw20 = np.array([TW[k] / TW[k - 20] - 1 if k >= 20 else np.nan for k in range(N)])
us20 = np.array([US[k] / US[k - 20] - 1 if k >= 20 else np.nan for k in range(N)])
gap = tw20 - us20
f5 = np.array([ret(TW, k, 5) for k in range(N)])
f20 = np.array([ret(TW, k, 20) for k in range(N)])
f5d = np.array([ret(TW, k + 1, 5) for k in range(N)])  # 隔天收盤進
ok = ~np.isnan(tw20)

# 主策略在不在場（近似：MA60×1.01 上穿進、MA80×0.975 下穿出，日頻）
ma60 = np.array([TW[max(0, k - 59):k + 1].mean() for k in range(N)])
ma80 = np.array([TW[max(0, k - 79):k + 1].mean() for k in range(N)])
inmkt = np.zeros(N, bool)
for k in range(1, N):
    inmkt[k] = (TW[k] > ma60[k] * 1.01) if not inmkt[k - 1] else (TW[k] >= ma80[k] * 0.975)


def events(th, flag=None):
    out, last = [], -99
    for k in range(20, N):
        if gap[k] <= -th and k - last > 20:
            out.append(k)
            last = k
    return out


def ctrl_mean(f, k, band=0.02):
    m = ok & (np.abs(tw20 - tw20[k]) <= band) & (gap > -0.05) & ~np.isnan(f)
    return f[m].mean() if m.sum() >= 20 else np.nan, int(m.sum())


L = ["研究 204b：台美背離補漲——控制台股自身跌幅（對照＝tw20 相差 ≤2% 且背離 > −5% 的日子）"]
ALL = {}
for th in (0.10, 0.15, 0.20):
    ev = events(th)
    L.append(f"\n【背離 ≤ −{th:.0%}】{len(ev)} 次")
    for name, f in (("5 日", f5), ("20 日", f20), ("5 日（隔天收盤進）", f5d)):
        ex, raw, cm = [], [], []
        for k in ev:
            if np.isnan(f[k]):
                continue
            c, n = ctrl_mean(f, k)
            if np.isnan(c):
                continue
            ex.append(f[k] - c)
            raw.append(f[k])
            cm.append(c)
        ex = np.array(ex)
        L.append(f"  {name}：{len(ex)} 次 原始 {np.mean(raw):+.2%}、同跌幅對照 {np.mean(cm):+.2%}、超額 {ex.mean():+.2%}（中位 {np.median(ex):+.2%}、正的比例 {np.mean(ex > 0):.0%}）")
        for seg, lo, hi in (("1998–2012", "1998", "2013"), ("2013–2026", "2013", "2099")):
            sel = [i for i, k in enumerate([k for k in ev if not np.isnan(f[k]) and not np.isnan(ctrl_mean(f, k)[0])]) if lo <= DAYS[k] < hi]
            if sel:
                L.append(f"    {seg}：{len(sel)} 次 超額 {ex[sel].mean():+.2%}")
        ALL[(th, name)] = ex

# (A) 家族：環狀平移事件旗標，統計量＝事件超額平均 的 t
idx = np.where(ok & ~np.isnan(f20))[0]
# 預先算每天的「同跌幅對照」超額（對照不依賴事件旗標）
exd5 = np.full(N, np.nan)
exd20 = np.full(N, np.nan)
for k in idx:
    c5, _ = ctrl_mean(f5, k)
    c20, _ = ctrl_mean(f20, k)
    exd5[k] = f5[k] - c5
    exd20[k] = f20[k] - c20
flags = {}
for th in (0.10, 0.15, 0.20):
    fl = np.zeros(N, bool)
    fl[events(th)] = True
    flags[th] = fl[idx]
series = {"5 日": exd5[idx], "20 日": exd20[idx]}


def tstat(x, fl):
    v = x[fl & ~np.isnan(x)]
    if len(v) < 3:
        return -9
    allv = x[~np.isnan(x)]
    return (v.mean() - allv.mean()) / (allv.std() / np.sqrt(len(v)))


real = {(th, h): tstat(series[h], flags[th]) for th in flags for h in series}
rng = np.random.default_rng(2042)
null = []
for _ in range(1000):
    s = int(rng.integers(100, len(idx) - 100))
    null.append(max(tstat(series[h], np.roll(flags[th], s)) for th in flags for h in series))
null = np.array(null)
L.append("\n【家族檢定：同跌幅超額】（3 門檻 × 5／20 日＝6 檢定，環狀平移 1,000 次，單尾）")
for key, z in sorted(real.items(), key=lambda kv: -kv[1]):
    L.append(f"  背離 ≤−{key[0]:.0%} {key[1]}：z {z:+.2f}、家族 p {np.mean(null >= z):.3f}")

# (B) 逐筆
L.append("\n【逐筆】背離 ≤ −10%（日期｜加權 20 日｜S&P 20 日｜背離｜5 日｜同跌幅超額｜20 日｜主策略）")
for k in events(0.10):
    L.append(f"  {DAYS[k]}｜{tw20[k]:+.1%}｜{us20[k]:+.1%}｜{gap[k]:+.1%}｜{f5[k]:+.1%}｜{exd5[k]:+.1%}｜{f20[k]:+.1%}｜{'在場' if inmkt[k] else '空手'}")

# (C) 執行：成本、在場／空手
L.append("\n【執行】背離 ≤ −10%，抱 5 日，每筆淨報酬（1 倍）")
ev = [k for k in events(0.10) if not np.isnan(f5d[k])]
for lab, f in (("訊號日收盤進", f5), ("隔天收盤進", f5d)):
    v = np.array([f[k] for k in ev])
    for cost in (0.001, 0.003):
        L.append(f"  {lab} 成本 {cost:.1%}：平均 {v.mean() - cost:+.2%}、勝率 {np.mean(v - cost > 0):.0%}、最差 {v.min() - cost:+.1%}")
for lab, cond in (("主策略在場", True), ("主策略空手", False)):
    v = np.array([f5[k] for k in ev if inmkt[k] == cond])
    if len(v):
        L.append(f"  {lab}：{len(v)} 次 5 日 {v.mean():+.2%}、勝率 {np.mean(v > 0):.0%}")

L.append(f"\n現況 {DAYS[-1]}：加權 20 日 {tw20[-1]:+.1%}、S&P 20 日 {us20[-1]:+.1%}、背離 {gap[-1]:+.1%}；主策略 {'在場' if inmkt[-1] else '空手'}")
out = "\n".join(L) + "\n"
print(out)
open(os.path.join(HERE, "結果_研究204b_台美背離_控制自身跌幅.txt"), "w", encoding="utf-8").write(out)
