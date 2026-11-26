"""研究 174b：接研究 174——「跟著大額交易人」可交易版與濾網

(1) 日盤多空：前十大交易人淨部位比（A10）在過去 250 日 ≥90 分位 → 隔天日盤（08:45 開→13:45 收）做多；≤10 分位 → 做空；其他不動
    每筆扣 6 點；逐年、三段；虛無：A10 序列環狀平移 1000 次（保留自相關）
(2) 急加多 z≥2 → 隔天開盤買抱 5 天（研究 174 p 0.008），環狀平移 1000 次
(3) 當濾網：恐慌隔天做多（P）與爆量收黑加碼（V）觸發時，A10 分位高／低 分組的每筆報酬
用法：python -X utf8 backtest/research_174b_跟著大戶.py
"""
import csv
import importlib.util
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


R141 = load("r141", "research_141_加碼總曝險上限.py")
R148 = load("r148", "research_148_恐慌連續觸發.py")
R139, R138 = R141.R139, R141.R138
COST = 3.0


def main():
    lt = {}
    for r in csv.DictReader(open(os.path.join(HERE, "large_trader_tx.csv"), encoding="utf-8")):
        if r["cat"] == "0" and int(r["oi"]) > 0:
            lt[r["date"]] = (int(r["top10_buy"]) - int(r["top10_sell"])) / int(r["oi"])
    dates, day, night, near = R139.load_tx()
    ds = [d for d in dates if d in lt]
    n = len(ds)
    x = np.array([lt[d] for d in ds])
    # 隔天日盤（同契約：d 的近月）與抱 5 天
    id1 = np.full(n, np.nan)
    h5 = np.full(n, np.nan)
    for i in range(n - 1):
        m = near[ds[i]]
        b = day[ds[i + 1]].get(m)
        if b:
            id1[i] = (b[3] - b[0]) / b[0]
            j = i + 5
            if j < n and day[ds[j]].get(m):
                h5[i] = (day[ds[j]][m][3] - b[0] - 2 * COST) / b[0]
    px = np.array([day[ds[i]][near[ds[i]]][0] for i in range(n)])

    def pct_of(v):
        p = np.full(len(v), np.nan)
        for i in range(250, len(v)):
            p[i] = np.mean(v[i - 250:i] < v[i])
        return p

    def zc_of(v):
        dv = np.r_[np.nan, np.diff(v)]
        z = np.full(len(v), np.nan)
        for i in range(250, len(v)):
            w = dv[i - 249:i]
            z[i] = (dv[i] - w.mean()) / w.std()
        return z

    def ls_strategy(p):
        pos = np.where(p >= 0.9, 1.0, np.where(p <= 0.1, -1.0, 0.0))
        g = ~np.isnan(id1) & ~np.isnan(p)
        r = np.where(g & (pos != 0), pos * id1 - 2 * COST / px, 0.0)
        return r, pos, g

    pct = pct_of(x)
    r, pos, g = ls_strategy(pct)
    trades = r[pos != 0]
    out = [f"研究 174b：跟著大戶（前十大交易人淨部位，{ds[250]}～{ds[-1]}）", ""]
    out.append("== (1) 日盤多空（A10 ≥90 分位做多、≤10 分位做空，隔天 08:45→13:45，扣 6 點）==")
    out.append(f"{len(trades)} 筆  每筆 {trades.mean():+.3%}  勝率 {np.mean(trades > 0):.0%}  多單 {np.sum(pos == 1)} 筆 {r[pos == 1].mean():+.3%}  空單 {np.sum(pos == -1)} 筆 {r[pos == -1].mean():+.3%}")
    out.append(f"累積（1 倍名目）{np.prod(1 + r) - 1:+.0%}；每年交易約 {len(trades) / (n / 250):.0f} 次")
    # 平移安慰劑
    rng = np.random.default_rng(1742)
    obs = trades.mean()
    null = []
    for s in rng.integers(250, n - 250, 1000):
        rr, pp, _ = ls_strategy(pct_of(np.roll(x, s)))
        null.append(rr[pp != 0].mean())
    null = np.array(null)
    out.append(f"環狀平移安慰劑：平均 {null.mean():+.3%}、95 分位 {np.percentile(null, 95):+.3%} → 單尾 p {(1 + np.sum(null >= obs)) / 1001:.3f}")
    by = defaultdict(list)
    for i in np.where(pos != 0)[0]:
        by[ds[i][:4]].append(r[i])
    out.append(f"逐年：{sum(np.sum(v) > 0 for v in by.values())}/{len(by)} 年為正｜" + " ".join(f"{y[2:]}:{np.sum(v):+.1%}" for y, v in sorted(by.items())))
    out.append("")
    # (2) 急加多抱 5 天
    zc = zc_of(x)

    def burst(zz):
        idx, last = [], -99
        for i in np.where((zz >= 2) & ~np.isnan(h5))[0]:
            if i - last >= 5:
                idx.append(i)
            last = i
        return np.array(idx, int)

    idx = burst(zc)
    v = h5[idx]
    null2 = np.array([h5[burst(zc_of(np.roll(x, s)))].mean() for s in rng.integers(250, n - 250, 300)])
    out.append("== (2) 前十大單日急加多 z≥2 → 隔天開盤買抱 5 天（去叢集）==")
    out.append(f"{len(v)} 筆  每筆 {v.mean():+.2%}  勝率 {np.mean(v > 0):.0%}  最差 {v.min():+.1%}｜所有日子抱 5 天平均 {np.nanmean(h5):+.2%}")
    out.append(f"環狀平移安慰劑 300 次：平均 {null2.mean():+.2%}、95 分位 {np.percentile(null2, 95):+.2%} → 單尾 p {(1 + np.sum(null2 >= v.mean())) / 301:.3f}")
    for lab, a, z in (("05–12", "2005", "2013"), ("13–19", "2013", "2020"), ("20–26", "2020", "2027")):
        s_ = np.array([a <= ds[i] < z for i in idx])
        out.append(f"   {lab}：{s_.sum()} 筆 {v[s_].mean():+.2%} 勝率 {np.mean(v[s_] > 0):.0%}")
    out.append("")
    # (3) 濾網
    out.append("== (3) 當濾網：觸發當天（前一日收盤後）的 A10 分位 ==")
    k_of = {d: i for i, d in enumerate(ds)}
    prow = [p for p in R148.build() if p["sig"]]
    grp = defaultdict(list)
    for p in prow:
        i = k_of.get(p["d"])
        if i is None or i == 0 or np.isnan(pct[i - 1]):
            continue
        q = pct[i - 1]
        grp["高（≥70 分位）" if q >= 0.7 else "低（≤30 分位）" if q <= 0.3 else "中"].append(p["r"])
    for k in ("高（≥70 分位）", "中", "低（≤30 分位）"):
        a = np.array(grp[k])
        if len(a):
            out.append(f"恐慌做多 × 大戶{k}：{len(a)} 筆 每筆 {a.mean():+.2%} 勝率 {np.mean(a > 0):.0%}")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究174b_跟著大戶.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
