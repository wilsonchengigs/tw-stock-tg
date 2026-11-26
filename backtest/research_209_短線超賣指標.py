"""研究 209：短線超賣指標之後台股會不會反彈（Connors 類均值回歸，台股 1998～2026）
訊號（D 收盤成立）：
  RSI2 < 5／10；RSI14 < 25／30；收盤 < 布林下緣（20 日 −2σ／−2.5σ）；連跌 ≥4／5 天；
  Connors 版：RSI2 < 10 且 收盤 > MA200（多頭中的回檔）
結果：D 收→D+1 收、D 收→D+5 收 的加權報酬；對照＝前 20 日實現波動同十分位的所有日子（波動高時報酬本來就大）
家族：9 訊號 × 2 天期＝18，訊號旗標環狀平移 1,000 次、最大 z；兩段 1998–2012／2013–2026；
增量：排除 P（夜盤或 S&P 跌 ≥2%，1998 起用 S&P 代理）與 D（台美背離 ≤-10%）觸發 ±1 天的日子
用法：python -X utf8 backtest/research_209_短線超賣指標.py
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_206_台美背離延伸 as R  # noqa: E402

TW, DAYS, N = R.TW, R.DAYS, R.N
r1 = np.r_[0.0, TW[1:] / TW[:-1] - 1]
F = {1: np.array([TW[k + 1] / TW[k] - 1 if k + 1 < N else np.nan for k in range(N)]), 5: R.F[5]}


def rsi(n):
    up, dn = np.maximum(r1, 0), np.maximum(-r1, 0)
    au, ad = np.zeros(N), np.zeros(N)
    au[n], ad[n] = up[1:n + 1].mean(), dn[1:n + 1].mean()
    for k in range(n + 1, N):
        au[k] = (au[k - 1] * (n - 1) + up[k]) / n
        ad[k] = (ad[k - 1] * (n - 1) + dn[k]) / n
    out = 100 - 100 / (1 + au / np.where(ad == 0, 1e-12, ad))
    out[:n + 1] = np.nan
    return out


R2, R14 = rsi(2), rsi(14)
ma20 = np.array([TW[max(0, k - 19):k + 1].mean() for k in range(N)])
sd20 = np.array([TW[max(0, k - 19):k + 1].std() for k in range(N)])
ma200 = np.array([TW[max(0, k - 199):k + 1].mean() if k >= 199 else np.nan for k in range(N)])
streak = np.zeros(N, int)
for k in range(1, N):
    streak[k] = streak[k - 1] + 1 if r1[k] < 0 else 0
vol = np.array([r1[max(1, k - 19):k + 1].std() if k >= 20 else np.nan for k in range(N)])
dec = np.full(N, -1)
okv = ~np.isnan(vol)
qs = np.nanpercentile(vol, np.arange(10, 100, 10))
dec[okv] = np.searchsorted(qs, vol[okv])

SIG = {
    "RSI2<5": R2 < 5, "RSI2<10": R2 < 10, "RSI14<25": R14 < 25, "RSI14<30": R14 < 30,
    "布林-2σ": TW < ma20 - 2 * sd20, "布林-2.5σ": TW < ma20 - 2.5 * sd20,
    "連跌≥4": streak >= 4, "連跌≥5": streak >= 5, "Connors RSI2<10＋MA200上": (R2 < 10) & (TW > ma200),
}
for k in SIG:
    SIG[k] = np.nan_to_num(SIG[k], nan=0).astype(bool) & (np.arange(N) >= 220)

# P 代理（S&P 前一晚跌 ≥2%）、D（台美背離 ≤-10%）
US = R.BENCH["GSPC"]
spr = np.r_[np.nan, US[1:] / US[:-1] - 1]
near = np.zeros(N, bool)
for k in np.where((spr <= -0.02) | (R.GAP["GSPC"] <= -0.10))[0]:
    near[max(0, k - 1):k + 2] = True


def excess(h):
    f = F[h]
    out = np.full(N, np.nan)
    for d in range(10):
        m = (dec == d) & ~np.isnan(f)
        out[m] = f[m] - f[m].mean()
    return out


EX = {h: excess(h) for h in (1, 5)}
valid = np.where(~np.isnan(EX[5]) & (np.arange(N) >= 220))[0]


def z(x, fl):
    m = fl & ~np.isnan(x)
    if m.sum() < 5:
        return np.nan
    a = x[~np.isnan(x)]
    return (x[m].mean() - a.mean()) / (a.std() / np.sqrt(m.sum()))


pre = [(name, h, EX[h][valid], SIG[name][valid]) for name in SIG for h in (1, 5)]
real = [z(x, fl) for _, _, x, fl in pre]
rng = np.random.default_rng(209)
null = np.array([np.nanmax([z(x, np.roll(fl, s)) for _, _, x, fl in pre]) for s in rng.integers(250, len(valid) - 250, 1000)])
L = ["研究 209：短線超賣指標（加權 1998～2026；超額＝減去同波動十分位平均；天數＝訊號日數，未去叢集）",
     f"現況 {DAYS[-1]}：RSI2 {R2[-1]:.0f}、RSI14 {R14[-1]:.0f}、布林 z {(TW[-1] - ma20[-1]) / sd20[-1]:+.2f}、連跌 {streak[-1]} 天、MA200 {'上' if TW[-1] > ma200[-1] else '下'}", ""]
for (name, h, x, fl), zz in zip(pre, real):
    m = SIG[name] & ~np.isnan(EX[h])
    seg = [np.nanmean(EX[h][m & (np.array(DAYS) < "2013")]), np.nanmean(EX[h][m & (np.array(DAYS) >= "2013")])]
    inc = m & ~near
    p = np.mean(null >= zz) if not np.isnan(zz) else np.nan
    L.append(f"  {name:22s} {h} 日：{m.sum():4d} 天 原始 {np.nanmean(F[h][m]):+.2%} 超額 {np.nanmean(EX[h][m]):+.2%}  z {zz:+.2f} 家族 p {p:.3f}  兩段 {seg[0]:+.2%}／{seg[1]:+.2%}  排除 P／D {inc.sum()} 天 {np.nanmean(EX[h][inc]):+.2%}")
out = "\n".join(L) + "\n"
print(out)
open(os.path.join(HERE, "結果_研究209_短線超賣指標.txt"), "w", encoding="utf-8").write(out)


def incremental():
    """排除 P／D ±1 天後的增量：5 日、9 訊號家族，平移訊號旗標（near 固定）"""
    keep = ~near[valid]
    pre2 = [(name, EX[5][valid], SIG[name][valid]) for name in SIG]

    def z2(x, fl):
        return z(x, fl & keep)

    real2 = [z2(x, fl) for _, x, fl in pre2]
    rng2 = np.random.default_rng(2092)
    null2 = np.array([np.nanmax([z2(x, np.roll(fl, s)) for _, x, fl in pre2]) for s in rng2.integers(250, len(valid) - 250, 1000)])
    L2 = ["\n【增量：排除 P／D ±1 天，5 日，9 檢定家族】"]
    for (name, x, fl), zz in zip(pre2, real2):
        m = fl & keep & ~np.isnan(x)
        L2.append(f"  {name:22s}：{m.sum():4d} 天 超額 {x[m].mean():+.2%}  z {zz:+.2f} 家族 p {np.mean(null2 >= zz):.3f}")
    return L2


if __name__ == "__main__":
    add = incremental()
    print("\n".join(add))
    open(os.path.join(HERE, "結果_研究209_短線超賣指標.txt"), "a", encoding="utf-8").write("\n".join(add) + "\n")
