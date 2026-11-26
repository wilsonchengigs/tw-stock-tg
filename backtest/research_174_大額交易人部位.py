"""研究 174：期交所大額交易人未沖銷部位（前五大／前十大、特定法人）→ 台指期之後 1／5／10 天

資料：backtest/large_trader_tx.csv（build_large_trader.py；台指期 TX＋MTX/4＋TMF/20、所有月份合計）
指標（日 d 收盤後公布）：淨部位比＝（買方 − 賣方）÷ 全市場未沖銷
  A5／A10：全部交易人前五大／前十大；S10：特定法人前十大
訊號：水位 250 日 ≥90／≤10 分位（大戶極度偏多／偏空）；單日變化 z ≥+2／≤−2（大戶急加多／急加空）
報酬：台指期近月 d+1 08:45 開盤做多，抱 H＝1／5／10 個交易日收盤出，扣 3 點×2
主檢定（避免重疊樣本誇大）：去叢集（距上次同訊號 ≥H 天才算新事件），每事件「報酬 − 同波動度十分位非訊號日平均」，sign-flip 2000 次雙尾
家族：3 指標 × 4 訊號 × 3 H＝36 檢定 Bonferroni；分段 2004–2012／2013–2019／2020–2026；另列 v3 在場子樣本
用法：python -X utf8 backtest/research_174_大額交易人部位.py
"""
import csv
import importlib.util
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r141", os.path.join(HERE, "research_141_加碼總曝險上限.py"))
R141 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R141)
R139, R138 = R141.R139, R141.R138
COST = 3.0
HS = (1, 5, 10)
SEGS = (("04–12", "2004", "2013"), ("13–19", "2013", "2020"), ("20–26", "2020", "2027"))


def main():
    lt = defaultdict(dict)
    for r in csv.DictReader(open(os.path.join(HERE, "large_trader_tx.csv"), encoding="utf-8")):
        oi = int(r["oi"])
        if oi <= 0:
            continue
        lt[r["date"]][r["cat"]] = ((int(r["top5_buy"]) - int(r["top5_sell"])) / oi, (int(r["top10_buy"]) - int(r["top10_sell"])) / oi)
    dates, day, night, near = R139.load_tx()
    bi = {d: k for k, d in enumerate(R138.DAYS)}
    ds = [d for d in dates if d in lt and "0" in lt[d] and "1" in lt[d]]
    n = len(ds)
    IND = {"A5 前五大": np.array([lt[d]["0"][0] for d in ds]), "A10 前十大": np.array([lt[d]["0"][1] for d in ds]),
           "S10 特定法人前十大": np.array([lt[d]["1"][1] for d in ds])}
    R = {H: np.full(n, np.nan) for H in HS}
    cl = np.zeros(n)
    for i in range(n):
        m = near[ds[i]]
        cl[i] = day[ds[i]][m][3]
        if i + 1 >= n:
            continue
        b = day[ds[i + 1]].get(m)
        if not b:
            continue
        for H in HS:
            j = i + H
            if j < n and day[ds[j]].get(m):
                R[H][i] = (day[ds[j]][m][3] - b[0] - 2 * COST) / b[0]
    cc = np.r_[0.0, cl[1:] / cl[:-1] - 1]
    vol = np.array([np.std(cc[max(1, i - 20):i]) if i > 5 else np.nan for i in range(n)])
    dec = np.digitize(np.nan_to_num(vol), np.nanpercentile(vol, np.arange(10, 100, 10)))
    st = np.array([R138.ST[bi[d]] if d in bi else 0 for d in ds])
    dsa = np.array(ds)
    rng = np.random.default_rng(174)
    out = [f"研究 174：大額交易人淨部位 × 台指期（{ds[250]}～{ds[-1]}）", "（每筆＝隔天開盤做多抱 H 天；比同波動＝事件報酬 − 同波動度非訊號日平均；p＝去叢集 sign-flip）", ""]
    fam = []
    for nm, x in IND.items():
        dx = np.r_[np.nan, np.diff(x)]
        pct = np.full(n, np.nan)
        zc = np.full(n, np.nan)
        for i in range(250, n):
            pct[i] = np.mean(x[i - 250:i] < x[i])
            w = dx[i - 249:i]
            zc[i] = (dx[i] - w.mean()) / w.std() if w.std() > 0 else 0
        out.append(f"== {nm}：目前 {x[-1]:+.1%}（250 日第 {pct[-1]:.0%} 分位）；全期中位 {np.median(x):+.1%} ==")
        for snm, sig in (("極度偏多 ≥90 分位", pct >= 0.9), ("極度偏空 ≤10 分位", pct <= 0.1), ("急加多 z≥2", zc >= 2), ("急加空 z≤−2", zc <= -2)):
            cells = []
            for H in HS:
                r = R[H]
                g = ~np.isnan(r) & ~np.isnan(pct) & ~np.isnan(vol)
                idx, last = [], -99
                for i in np.where(sig & g)[0]:
                    if i - last >= max(H, 1):
                        idx.append(i)
                    last = i
                idx = np.array(idx, int)
                if len(idx) < 10:
                    cells.append(f"H{H} {len(idx)} 次（少）")
                    continue
                ctrl = g & ~sig
                d_ = np.array([r[i] - r[np.where(ctrl & (dec == dec[i]))[0]].mean() for i in idx])
                sims = np.array([(d_ * rng.choice((-1, 1), len(d_))).mean() for _ in range(2000)])
                p = (1 + np.sum(np.abs(sims) >= abs(d_.mean()))) / 2001
                fam.append((f"{nm[:3]} {snm} H{H}", p, d_.mean(), len(idx),
                            [d_[(dsa[idx] >= a) & (dsa[idx] < z)].mean() if ((dsa[idx] >= a) & (dsa[idx] < z)).sum() else np.nan for _, a, z in SEGS],
                            r[idx].mean(), np.mean(r[idx] > 0), (st[idx] == 1).sum()))
                cells.append(f"H{H} {len(idx)} 次 每筆 {r[idx].mean():+.2%} 勝率 {np.mean(r[idx] > 0):.0%} 差 {d_.mean():+.2%}（p {p:.3f}）")
            out.append(f"  {snm:12s}｜" + "｜".join(cells))
        out.append("")
    K = len(fam)
    out.append(f"== 家族 Bonferroni（{K} 個檢定；p < {0.05 / K:.4f} 才算）前 10 名 ==")
    for nm, p, d, m, seg, mean, win, ins in sorted(fam, key=lambda z: z[1])[:10]:
        out.append(f"{nm:28s} {m:3d} 次 每筆 {mean:+.2%} 勝率 {win:.0%} 差 {d:+.2%} p {p:.3f} → 校正 {min(1, p * K):.3f}｜分段差 " +
                   " ".join(f"{lab} {v:+.2%}" for (lab, _, _), v in zip(SEGS, seg)) + f"｜v3 在場 {ins} 次")
    out.append("")
    out.append("三段同方向且家族校正前 p < 0.05：" + ("、".join(nm for nm, p, d, m, seg, *_ in fam
                                                   if p < 0.05 and all(np.sign(v) == np.sign(d) for v in seg if not np.isnan(v))) or "沒有"))
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究174_大額交易人部位.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
