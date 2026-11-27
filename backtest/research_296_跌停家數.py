"""研究 296：跌停家數比例 → 之後的加權

資料：backtest/stock_closes/*.csv.gz（上市個股收盤，2012-12～），只用 4 碼普通股（排除 00 開頭 ETF）。
跌停判定：當日報酬 ≤ -9.5%（2015-06-01 起漲跌幅 10%）；之前 ≤ -6.5%（7%）。漲停同理。
指標：LD＝跌停家數 ÷ 有報價家數；同日加權報酬 r。
問題：同樣的指數跌幅下，跌停家數多（恐慌擴散）是否之後反彈更多？——P（恐慌做多）規則只看指數與波動，這可能是補充資訊。
做法：
(1) LD 分組（≥10%、5～10%、2～5%）→ 之後加權 1／5／20 日
(2) 指數跌 ≥2% 的日子裡，依 LD 中位數切高／低兩組比較（控制指數跌幅）；迴歸 fwd ~ r ＋ LD
用法：python -X utf8 backtest/research_296_跌停家數.py
"""
import csv
import glob
import gzip
import os
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import strategy_v3 as s  # noqa: E402

HS = (1, 5, 20)


def load_ld():
    px = defaultdict(dict)  # code -> date -> close
    for f in sorted(glob.glob(os.path.join(HERE, "stock_closes", "*.csv.gz"))):
        for r in csv.DictReader(gzip.open(f, "rt", encoding="utf-8")):
            c = r["code"]
            if len(c) != 4 or c.startswith("00"):
                continue
            try:
                px[c][r["date"]] = float(r["close"])
            except ValueError:
                pass
    dates = sorted({d for m in px.values() for d in m})
    pos = {d: i for i, d in enumerate(dates)}
    ld, lu, n = defaultdict(int), defaultdict(int), defaultdict(int)
    for c, m in px.items():
        ds = sorted(m)
        for a, b in zip(ds, ds[1:]):
            if pos[b] - pos[a] != 1 or m[a] <= 0:
                continue
            r = m[b] / m[a] - 1
            th = 0.095 if b >= "2015-06-01" else 0.065
            n[b] += 1
            if r <= -th:
                ld[b] += 1
            elif r >= th:
                lu[b] += 1
    return {d: (ld[d] / n[d], lu[d] / n[d], n[d]) for d in n if n[d] >= 300}


def main():
    LD = load_ld()
    D, P = s.DAYS, s.PX
    idx = {d: i for i, d in enumerate(D)}
    rows = []
    for d, (ld, lu, n) in LD.items():
        i = idx.get(d)
        if i is None or i < 1 or i + 20 >= len(P):
            continue
        r = P[i] / P[i - 1] - 1
        rows.append((d, ld, lu, r, {h: (P[i + h] / P[i] - 1) * 100 for h in HS}))
    rows.sort()
    out = [f"研究 296：跌停家數比例 → 之後加權（{rows[0][0]}～{rows[-1][0]}，{len(rows)} 天）\n"]
    base = {h: statistics.mean(x[4][h] for x in rows) for h in HS}
    out.append("全部日子平均：" + "  ".join(f"{h}日 {base[h]:+.2f}%" for h in HS))
    out.append("\nLD 分組      天數  同日加權   " + "   ".join(f"{h}日" for h in HS))
    for lab, lo, hi in (("≥10%", 0.10, 9), ("5～10%", 0.05, 0.10), ("2～5%", 0.02, 0.05), ("1～2%", 0.01, 0.02)):
        g = [x for x in rows if lo <= x[1] < hi]
        if g:
            out.append(f"{lab:<8}   {len(g):>4}  {statistics.mean(x[3] for x in g) * 100:+6.2f}%   " +
                       "  ".join(f"{statistics.mean(x[4][h] for x in g):+5.2f}%" for h in HS))
    for lab, g in (("LD≥10% 逐日", [x for x in rows if x[1] >= 0.10]),):
        out.append(f"\n{lab}：")
        for x in g:
            out.append(f"  {x[0]}  跌停 {x[1] * 100:4.1f}%  加權 {x[3] * 100:+5.1f}%  " + "  ".join(f"{h}日 {x[4][h]:+5.1f}%" for h in HS))
    # 控制指數跌幅：加權跌 ≥2% 的日子，依 LD 中位切
    dn = [x for x in rows if x[3] <= -0.02]
    med = statistics.median(x[1] for x in dn)
    hi_g = [x for x in dn if x[1] > med]
    lo_g = [x for x in dn if x[1] <= med]
    out.append(f"\n加權跌 ≥2% 的 {len(dn)} 天，跌停比例中位 {med * 100:.1f}%：")
    for lab, g in (("跌停多", hi_g), ("跌停少", lo_g)):
        out.append(f"  {lab} {len(g):>3} 天  同日 {statistics.mean(x[3] for x in g) * 100:+.2f}%  " +
                   "  ".join(f"{h}日 {statistics.mean(x[4][h] for x in g):+.2f}%（勝 {sum(x[4][h] > 0 for x in g) / len(g) * 100:.0f}%）" for h in HS))
    # 迴歸（加權跌 ≥2% 的日子）：fwd = a + b·r + c·LD
    import numpy as np
    for h in HS:
        X = np.array([[1, x[3] * 100, x[1] * 100] for x in dn])
        y = np.array([x[4][h] for x in dn])
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        res = y - X @ beta
        s2 = res @ res / (len(y) - 3)
        se = np.sqrt(np.diag(s2 * np.linalg.inv(X.T @ X)))
        out.append(f"  迴歸 {h:>2}日：同日報酬係數 {beta[1]:+.2f}（t {beta[1] / se[1]:+.2f}）、跌停比例係數 {beta[2]:+.3f}（t {beta[2] / se[2]:+.2f}）")
    # 加入前 20 日加權實現波動（研究 458 的 RV20，年化，不含當天）一起迴歸：跌停家數是否只是高波動的代理
    import math
    rv = {}
    for i in range(21, len(P)):
        rr = [math.log(P[k] / P[k - 1]) for k in range(i - 20, i)]
        rv[D[i]] = statistics.pstdev(rr) * math.sqrt(252) * 100
    dn2 = [x for x in dn if x[0] in rv]
    out.append(f"\n加 RV20 一起迴歸（{len(dn2)} 天）：")
    for h in HS:
        X = np.array([[1, x[3] * 100, x[1] * 100, rv[x[0]]] for x in dn2])
        y = np.array([x[4][h] for x in dn2])
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        res = y - X @ beta
        s2 = res @ res / (len(y) - 4)
        se = np.sqrt(np.diag(s2 * np.linalg.inv(X.T @ X)))
        out.append(f"  {h:>2}日：跌停比例 {beta[2]:+.3f}（t {beta[2] / se[2]:+.2f}）、RV20 {beta[3]:+.3f}（t {beta[3] / se[3]:+.2f}）")
    cor = np.corrcoef([x[1] for x in dn2], [rv[x[0]] for x in dn2])[0, 1]
    out.append(f"  跌停比例與 RV20 相關 {cor:+.2f}")
    # 去叢集：連續大跌日的 5 日窗格重疊會灌水 t 值，5 個交易日內只留第一天
    keep, last = [], -99
    for x in sorted(dn2, key=lambda x: idx[x[0]]):
        if idx[x[0]] - last > 5:
            keep.append(x)
            last = idx[x[0]]
    X = np.array([[1, x[3] * 100, x[1] * 100, rv[x[0]]] for x in keep])
    y = np.array([x[4][5] for x in keep])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    res = y - X @ beta
    se = np.sqrt(np.diag(res @ res / (len(y) - 4) * np.linalg.inv(X.T @ X)))
    out.append(f"  去叢集（5 日內只留第一天）{len(keep)} 天，5 日：跌停比例 t {beta[2] / se[2]:+.2f}、RV20 t {beta[3] / se[3]:+.2f}")
    text = "\n".join(out)
    print(text)
    open(os.path.join(HERE, "結果_研究296_跌停家數.txt"), "w", encoding="utf-8").write(text + "\n")


if __name__ == "__main__":
    main()
