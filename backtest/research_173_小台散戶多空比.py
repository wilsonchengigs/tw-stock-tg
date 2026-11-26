"""研究 173：小台散戶多空比（反向指標？）→ 台指期之後 1／5／10 天

資料：backtest/mtx_retail.csv（build_mtx_retail.py；2018-06～）。散戶多空比＝−三大法人小台淨未平倉 ÷ 小台全市場未平倉
訊號（日 d 收盤後可知，法人資料 15:00 公布）：
  L 水位：過去 250 日百分位 ≥90／≤10
  C 變化：單日變化相對過去 250 日 z ≥ +2／≤ −2（散戶急加多／急加空）
報酬：台指期近月 d+1 08:45 開盤做多 → 抱 1／5／10 個交易日收盤出，扣 3 點×2；負＝做空較好
對照：同波動度（前 20 日實現波動同十分位）非訊號日 2000 次抽樣，雙尾 p；家族 Bonferroni；分段 2018-06～2021／2022～2026
另看 v3 在場時（加碼用）的子樣本
用法：python -X utf8 backtest/research_173_小台散戶多空比.py
"""
import csv
import importlib.util
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r141", os.path.join(HERE, "research_141_加碼總曝險上限.py"))
R141 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R141)
R139, R138 = R141.R139, R141.R138
COST = 3.0
HS = (1, 5, 10)


def main():
    rr = {r["date"]: float(r["retail_ratio"]) for r in csv.DictReader(open(os.path.join(HERE, "mtx_retail.csv"), encoding="utf-8"))}
    dates, day, night, near = R139.load_tx()
    bi = {d: k for k, d in enumerate(R138.DAYS)}
    ds = [d for d in dates if d in rr]
    n = len(ds)
    x = np.array([rr[d] for d in ds])
    dx = np.r_[np.nan, np.diff(x)]
    pct = np.full(n, np.nan)
    zc = np.full(n, np.nan)
    for i in range(250, n):
        w = x[i - 250:i]
        pct[i] = np.mean(w < x[i])
        dw = dx[i - 249:i]
        zc[i] = (dx[i] - dw.mean()) / dw.std()
    # 報酬：d+1 開盤進（d 的近月）、d+1+H−1 收盤出
    R = {H: np.full(n, np.nan) for H in HS}
    cl = []
    for i in range(n):
        m = near[ds[i]]
        cl.append(day[ds[i]][m][3])
        if i + 1 >= n:
            continue
        b = day[ds[i + 1]].get(m)
        if not b:
            continue
        for H in HS:
            j = i + H
            if j < n and day[ds[j]].get(m):
                R[H][i] = (day[ds[j]][m][3] - b[0] - 2 * COST) / b[0]
    cl = np.array(cl)
    cc = np.r_[0.0, cl[1:] / cl[:-1] - 1]
    vol = np.array([np.std(cc[max(1, i - 20):i]) if i > 5 else np.nan for i in range(n)])
    ok = ~np.isnan(vol) & ~np.isnan(pct)
    dec = np.digitize(np.nan_to_num(vol), np.nanpercentile(vol[ok], np.arange(10, 100, 10)))
    st = np.array([R138.ST[bi[d]] if d in bi else 0 for d in ds])
    rng = np.random.default_rng(173)
    rules = [("L 散戶偏多 ≥90 分位", pct >= 0.9), ("L 散戶偏空 ≤10 分位", pct <= 0.1),
             ("C 散戶急加多 z≥2", zc >= 2), ("C 散戶急加空 z≤−2", zc <= -2)]
    out = [f"研究 173：小台散戶多空比（{ds[250]}～{ds[-1]}，{ok.sum()} 天；散戶多空比 目前 {x[-1]:+.1%}、250 日第 {pct[-1]:.0%} 分位）",
           "（報酬＝隔天開盤做多抱 H 天；負＝做空較好；比同波動＝扣掉同波動度日子的平均）", ""]
    fam = []
    for nm, sig in rules:
        out.append(f"== {nm} ==")
        for H in HS:
            r = R[H]
            g = ok & ~np.isnan(r)
            msk = sig & g
            idx = np.where(msk)[0]
            if len(idx) < 10:
                out.append(f"  抱 {H:2d} 天：{len(idx)} 次（太少）")
                continue
            ctrl = g & ~sig
            pools = {i: np.where(ctrl & (dec == dec[i]))[0] for i in idx}
            base = np.array([r[pools[i]].mean() for i in idx])
            diff = np.mean(r[idx] - base)
            null = np.array([np.mean([r[rng.choice(pools[i])] for i in idx] - base) for _ in range(1000)])
            p = (1 + np.sum(np.abs(null) >= abs(diff))) / 1001
            fam.append((f"{nm} H{H}", p, diff))
            seg = "  ".join(f"{lab} {r[msk & np.array([a <= d < z for d in ds])].mean():+.2%}（{(msk & np.array([a <= d < z for d in ds])).sum()}）"
                            for lab, a, z in (("18–21", "2018", "2022"), ("22–26", "2022", "2027")))
            inm = msk & (st == 1)
            out.append(f"  抱 {H:2d} 天：{len(idx):4d} 次  每筆 {r[msk].mean():+.2%}  勝率 {np.mean(r[msk] > 0):.0%}  比同波動 {diff:+.2%}（p {p:.3f}）｜{seg}"
                       f"｜v3 在場 {inm.sum()} 次 {r[inm].mean() if inm.sum() else 0:+.2%}")
        out.append("")
    K = len(fam)
    out.append(f"== 家族 Bonferroni（{K} 個檢定）==")
    for nm, p, d in sorted(fam, key=lambda z: z[1])[:6]:
        out.append(f"{nm:28s} 比同波動 {d:+.2%}  p {p:.3f} → 校正 {min(1, p * K):.3f}")
    # 相關：散戶多空比水位 vs 之後 10 天
    g = ok & ~np.isnan(R[10])
    out.append("")
    out.append(f"散戶多空比水位與之後 10 天報酬的相關係數 {np.corrcoef(x[g], R[10][g])[0, 1]:+.3f}；百分位 vs 10 天 {np.corrcoef(pct[g], R[10][g])[0, 1]:+.3f}（重疊樣本，只供參考）")
    # 去叢集：同方向訊號 10 個交易日內只算第一次（避免重疊樣本誇大顯著性）；sign-flip 對「比同波動」差
    out.append("")
    out.append("== 去叢集（距上次訊號 ≥10 天才算新事件）抱 5／10 天 ==")
    for nm, sig in rules[:2]:
        for H in (5, 10):
            r = R[H]
            g = ok & ~np.isnan(r)
            idx, last = [], -99
            for i in np.where(sig & g)[0]:
                if i - last >= 10:
                    idx.append(i)
                last = i
            idx = np.array(idx)
            ctrl = g & ~sig
            d_ = np.array([r[i] - r[np.where(ctrl & (dec == dec[i]))[0]].mean() for i in idx])
            sims = np.array([(d_ * rng.choice((-1, 1), len(d_))).mean() for _ in range(2000)])
            p = (1 + np.sum(np.abs(sims) >= abs(d_.mean()))) / 2001
            out.append(f"{nm} 抱 {H} 天：{len(idx)} 個獨立事件  每筆 {r[idx].mean():+.2%}  勝率 {np.mean(r[idx] > 0):.0%}  比同波動 {d_.mean():+.2%}（sign-flip p {p:.3f}）")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究173_小台散戶多空比.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
