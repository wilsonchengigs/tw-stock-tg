"""研究 176：台指選擇權（TXO）大額交易人部位 → 台指期之後 1／5／10 天（研究 174 的選擇權版）

資料：backtest/large_trader_txo.csv（build_large_trader_txo.py；TXO 所有月份合計，買權／賣權分開）
指標（日 d 收盤後公布）：買權淨比 C＝（前十大買方 − 前十大賣方）÷ 買權未沖銷；賣權淨比 P 同理
  B10 大戶多空分數＝C − P（大戶買買權／賣賣權 → 偏多）；C10 只看買權；P10 只看賣權（大戶買賣權＝避險／看空）；S-B10 特定法人版
訊號：水位 250 日 ≥90／≤10 分位（大戶極度偏多／偏空）；單日變化 z ≥+2／≤−2（大戶急加多／急加空）
報酬：台指期近月 d+1 08:45 開盤做多，抱 H＝1／5／10 個交易日收盤出，扣 3 點×2
主檢定（避免重疊樣本誇大）：去叢集（距上次同訊號 ≥H 天才算新事件），每事件「報酬 − 同波動度十分位非訊號日平均」，sign-flip 2000 次雙尾
家族：4 指標 × 4 訊號 × 3 H＝48 檢定 Bonferroni；分段 2004–2012／2013–2019／2020–2026；另列 v3 在場子樣本
用法：python -X utf8 backtest/research_176_選擇權大額交易人.py
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
    for r in csv.DictReader(open(os.path.join(HERE, "large_trader_txo.csv"), encoding="utf-8")):
        oi = int(r["oi"])
        if oi <= 0:
            continue
        lt[r["date"]][r["cp"] + r["cat"]] = (int(r["top10_buy"]) - int(r["top10_sell"])) / oi
    dates, day, night, near = R139.load_tx()
    bi = {d: k for k, d in enumerate(R138.DAYS)}
    ds = [d for d in dates if d in lt and all(k in lt[d] for k in ("C0", "P0", "C1", "P1"))]
    n = len(ds)
    IND = {"B10 大戶多空分數": np.array([lt[d]["C0"] - lt[d]["P0"] for d in ds]), "C10 買權淨": np.array([lt[d]["C0"] for d in ds]),
           "P10 賣權淨": np.array([lt[d]["P0"] for d in ds]), "SB 特定法人分數": np.array([lt[d]["C1"] - lt[d]["P1"] for d in ds])}
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
    rng = np.random.default_rng(176)
    out = [f"研究 176：TXO 大額交易人 × 台指期（{ds[250]}～{ds[-1]}）", "（每筆＝隔天開盤做多抱 H 天；比同波動＝事件報酬 − 同波動度非訊號日平均；p＝去叢集 sign-flip）", ""]
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
                fam.append((f"{nm.split()[0]} {snm} H{H}", p, d_.mean(), len(idx),
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
    open(os.path.join(HERE, "結果_研究176_選擇權大額交易人.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
