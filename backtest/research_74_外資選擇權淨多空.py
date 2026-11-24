"""研究 74：外資台指選擇權淨多空金額的單日變化 → 短線報酬（AI-1：法人；資料 FinMind TaiwanOptionInstitutionalInvestors，2018-06～）

外資選擇權淨多空金額 ＝（買權 多方未平倉金額 − 空方未平倉金額）−（賣權 多方 − 空方），單位千元；正＝偏多
另測口數版（買權淨口數 − 賣權淨口數）。單日變化 Δ 相對過去 250 日 z；事件 |z| > 1.5／2，去叢集 5 日
報酬：加權隔天開盤 → 1／5／10 日；拔靴 p；分 2018-2021／2022-2026；可交易版（多空，抱 1／5 天，台指期近月真實價，隨機對照）
用法：python -X utf8 backtest/research_74_外資選擇權淨多空.py
"""
import csv
import importlib.util
import os
import random
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("r73b", os.path.join(HERE, "research_73b_外資期貨變化_交易版.py"))
r73b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r73b)
r63d, fmean, fstd = r73b.r63d, r73b.fmean, r73b.fstd


def main():
    agg = defaultdict(lambda: defaultdict(float))
    for r in csv.DictReader(open(os.path.join(HERE, "txo_inst_oi.csv"), encoding="utf-8")):
        if r["investor"] != "外資":
            continue
        sgn = 1 if r["cp"] == "C" else -1
        agg["金額"][r["date"]] += sgn * (float(r["long_oi_amt"]) - float(r["short_oi_amt"]))
        agg["口數"][r["date"]] += sgn * (float(r["long_oi"]) - float(r["short_oi"]))
    dates, day, night, near = r63d.load()
    n = len(dates)
    fidx = {d: i for i, d in enumerate(dates)}
    R = [0.0] * n
    for i in range(1, n):
        m = near[dates[i]]
        prev = day[dates[i - 1]].get(m)
        R[i] = day[dates[i]][m][3] / prev[3] - 1 if prev else 0.0

    def trade(i, d_, H):
        e, x = i + 1, i + H
        if x >= n:
            return None
        m = near[dates[e]]
        px = day[dates[e]][m][0]
        g = day[dates[e]][m][3] / px
        for j in range(e + 1, x + 1):
            g *= 1 + R[j]
        return d_ * (g - 1) - 3 / px, x

    rng = random.Random(74)
    L = ["研究 74：外資台指選擇權淨多空（單日變化 z）→ 台指期隔天開盤跟著做（2018-06～2026-11；成本 3 點）"]
    for nm, s in agg.items():
        ds = [d for d in sorted(s) if d in fidx]
        Z, hist = {}, []
        for k in range(1, len(ds)):
            dl = s[ds[k]] - s[ds[k - 1]]
            if len(hist) >= 120:
                h = hist[-250:]
                sd = fstd(h)
                Z[ds[k]] = (dl - fmean(h)) / sd if sd > 0 else None
            hist.append(dl)
        L.append(f"\n== 外資選擇權淨多空（{nm}）：最新 {ds[-1]} 水準 {s[ds[-1]]:+,.0f}、單日變化 z {Z.get(ds[-1], 0):+.2f} ==")
        zi = sorted((fidx[d], z) for d, z in Z.items() if z is not None)
        pool = [i for i, _ in zi if i + 6 < n]
        for x in (1.5, 2.0):
            for H in (1, 5):
                cells = []
                for lab, lo, hi in (("全期", "2018", "2027"), ("2018-2021", "2018", "2022"), ("2022-2026", "2022", "2027")):
                    trs, dirs, busy = [], [], -1
                    for i, z in zi:
                        if not (lo <= dates[i] < hi) or i + 1 <= busy:
                            continue
                        d_ = 1 if z > x else (-1 if z < -x else 0)
                        if not d_:
                            continue
                        t = trade(i, d_, H)
                        if t:
                            trs.append(t[0])
                            dirs.append(d_)
                            busy = t[1]
                    if len(trs) < 6:
                        cells.append(f"{lab} {len(trs)}筆")
                        continue
                    ev = fmean(trs)
                    pp = [i for i in pool if lo <= dates[i] < hi]
                    sims = [fmean(trade(rng.choice(pp), dd, H)[0] for dd in dirs) for _ in range(1000)]
                    p = (sum(v >= ev for v in sims) + 1) / 1001
                    cells.append(f"{lab} {len(trs):3d}筆 勝{sum(t > 0 for t in trs) / len(trs):3.0%} {ev:+.2%} p{p:.2f}")
                L.append(f"  跟著做 x{x} 抱{H}天  " + " ｜ ".join(cells))
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究74_外資選擇權.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
