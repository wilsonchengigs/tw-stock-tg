"""研究 92：通縮夏普比率（Deflated Sharpe Ratio，Bailey & López de Prado 2014）——扣掉「試了很多組」的運氣後，策略是否仍顯著

DSR＝Φ( (SR − SR0) × √(T−1) ÷ √(1 − γ3·SR + (γ4−1)/4·SR²) )
SR0＝√V[SR] × ((1−γ)·Φ⁻¹(1−1/K) + γ·Φ⁻¹(1−1/(K·e)))，γ≈0.5772（Euler–Mascheroni），K＝試驗次數
- SR：週報酬（扣現金利率）的夏普比率（週頻，未年化），γ3 偏態、γ4 峰態
- K：研究 01～91 累計測過的策略設定數，保守估 2,000、3,000、5,000
- V[SR]：用研究 60／88 的格點與本研究重算的大量變形的 SR 變異數估計
比較：v3、加 z 前、融資濾網前、舊版、0050 長抱、正2 長抱（都看 2002～2026 週報酬）
參考：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551
用法：python -X utf8 backtest/research_92_通縮夏普.py
"""
import importlib.util
import itertools
import math
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("v3", os.path.join(HERE, "strategy_v3.py"))
V = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V)
bt, DAYS, N, WE = V.bt, V.DAYS, V.N, V.WE


def norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def norm_ppf(p):
    lo, hi = -10.0, 10.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if norm_cdf(mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def weekly_excess(curve, i0):
    days = DAYS[i0:i0 + len(curve)]
    out, last = [], curve[0]
    for k in range(1, len(curve)):
        if WE[i0 + k]:
            r = curve[k] / last - 1
            out.append(r - bt.RC * 5)
            last = curve[k]
    return out


def sr_stats(r):
    m = statistics.mean(r)
    sd = statistics.pstdev(r)
    sr = m / sd
    g3 = sum((x - m) ** 3 for x in r) / len(r) / sd ** 3
    g4 = sum((x - m) ** 4 for x in r) / len(r) / sd ** 4
    return sr, g3, g4, len(r)


def curve_of(**kw):
    i0 = next(i for i, d in enumerate(DAYS) if d >= "2002-01-01")
    _, _, c = V.run("2002-01-01", "2026-12-31", curve=True, **kw)
    return weekly_excess(c, i0)


def hold_curve(r):
    i0 = next(i for i, d in enumerate(DAYS) if d >= "2002-01-01")
    eq, c = 1.0, [1.0]
    for i in range(i0 + 1, N):
        eq *= 1 + r[i]
        c.append(eq)
    return weekly_excess(c, i0)


def dsr(sr, g3, g4, T, var_sr, K):
    g = 0.5772156649
    sr0 = math.sqrt(var_sr) * ((1 - g) * norm_ppf(1 - 1 / K) + g * norm_ppf(1 - 1 / (K * math.e)))
    z = (sr - sr0) * math.sqrt(T - 1) / math.sqrt(1 - g3 * sr + (g4 - 1) / 4 * sr ** 2)
    return norm_cdf(z), sr0


def main():
    L = ["研究 92：通縮夏普比率（週報酬扣現金，2002～2026）"]
    cands = {
        "v3（現行：過熱每天、z、回補）": curve_of(),
        "過熱只週五": curve_of(daily_heat=False),
        "無 z 分數": curve_of(zth=None),
        "無融資濾網（出場 2.5%）": curve_of(use_heat=False),
        "0050 長抱": hold_curve(bt.R1),
        "正2 長抱": hold_curve(bt.R2),
    }
    # 估計 SR 的試驗間變異：v3 引擎的大量變形（門檻、z、回補、槓桿、日／週）
    srs = []
    for th, zt, re_, lev, dh in itertools.product((0.15, 0.175, 0.2, 0.25), (1.5, 2.0, 2.5, None), (0.10, 0.125, 0.15), (1.5, 2.0), (True, False)):
        r = curve_of(th=th, zth=zt, reentry=re_, lev=lev, daily_heat=dh)
        srs.append(sr_stats(r)[0])
    for r_ in (curve_of(use_heat=False, lev=l) for l in (1.0, 1.5, 2.0)):
        srs.append(sr_stats(r_)[0])
    var_sr = statistics.pvariance(srs)
    L.append(f"變形 {len(srs)} 組的週夏普：平均 {statistics.mean(srs):.3f}、標準差 {math.sqrt(var_sr):.4f}（年化約 ×√52）")
    L.append("\n策略 | 週夏普（年化） | 偏態 | 峰態 | 週數 | DSR（K＝2000／3000／5000）")
    for nm, r in cands.items():
        sr, g3, g4, T = sr_stats(r)
        ds = [dsr(sr, g3, g4, T, var_sr, K) for K in (2000, 3000, 5000)]
        L.append(f"{nm:26s} | {sr:.3f}（{sr * math.sqrt(52):.2f}） | {g3:+.2f} | {g4:.1f} | {T} | " + "／".join(f"{d:.3f}" for d, _ in ds))
    _, sr0 = dsr(0.1, 0, 3, 1000, var_sr, 3000)
    L.append(f"\nK＝3000 時，純運氣下最好的週夏普門檻 SR0 ≈ {sr0:.3f}（年化 {sr0 * math.sqrt(52):.2f}）；DSR > 0.95 才算扣掉試驗次數後仍顯著")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究92_通縮夏普.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()


def incremental():
    """增量檢定：v3 每週報酬 − 比較對象 的差，算夏普與 DSR（K＝試過的規則變形數）"""
    import itertools as it
    base = curve_of(use_heat=False)
    v3 = curve_of()
    others = {"過熱只週五": curve_of(daily_heat=False), "無 z 分數": curve_of(zth=None), "無融資濾網": base}
    # 規則變形相對「無融資濾網」的差的夏普分布（代表研究中試過的各種濾網設定）
    diffs = []
    for th, zt, re_, dh in it.product((0.15, 0.175, 0.2, 0.25), (1.5, 2.0, 2.5, None), (0.10, 0.125, 0.15), (True, False)):
        r = curve_of(th=th, zth=zt, reentry=re_, daily_heat=dh)
        d = [a - b for a, b in zip(r, base)]
        diffs.append(sr_stats(d)[0])
    var_d = statistics.pvariance(diffs)
    L = ["\n== 增量檢定：v3 每週報酬 − 比較對象（差的夏普；K＝試過的規則數）==",
         f"濾網變形 {len(diffs)} 組相對「無融資濾網」的差夏普：平均 {statistics.mean(diffs):.3f}、標準差 {math.sqrt(var_d):.4f}"]
    for nm, o in others.items():
        d = [a - b for a, b in zip(v3, o)]
        sr, g3, g4, T = sr_stats(d)
        res = [dsr(sr, g3, g4, T, var_d, K) for K in (100, 500, 2000)]
        t = sr * math.sqrt(T)
        L.append(f"v3 − {nm:8s}：差的週夏普 {sr:.3f}（t≈{t:.2f}）、平均每週 {statistics.mean(d):+.3%} | DSR（K＝100／500／2000）"
                 + "／".join(f"{x:.3f}" for x, _ in res))
    print("\n".join(L))
    open(os.path.join(HERE, "結果_研究92_通縮夏普.txt"), "a", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    incremental()
