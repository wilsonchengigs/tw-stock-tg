"""研究 298：加權 vs 等權背離（漲勢集中在權值股）→ 之後的加權

等權指數：每天所有 4 碼普通股（`stock_closes`，2012-12～）日報酬的平均（單日報酬 >±11% 視為除權息／錯價剔除）。
背離 G＝加權 20 日報酬 − 等權 20 日報酬（百分點）。G 大＝窄幅上漲（權值股撐盤）、G 小＝中小型股強。
做法：G 五分位 → 之後加權 20／60 日報酬；以 20 日不重疊取樣（每 20 個交易日取一次）算 t；分 2013–2019／2020～
用法：python -X utf8 backtest/research_298_加權等權背離.py
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


def ew_returns():
    px = defaultdict(dict)
    for f in sorted(glob.glob(os.path.join(HERE, "stock_closes", "*.csv.gz"))):
        for r in csv.DictReader(gzip.open(f, "rt", encoding="utf-8")):
            c = r["code"]
            if len(c) == 4 and not c.startswith("00"):
                try:
                    px[c][r["date"]] = float(r["close"])
                except ValueError:
                    pass
    dates = sorted({d for m in px.values() for d in m})
    pos = {d: i for i, d in enumerate(dates)}
    acc = defaultdict(list)
    for m in px.values():
        ds = sorted(m)
        for a, b in zip(ds, ds[1:]):
            if pos[b] - pos[a] == 1 and m[a] > 0:
                r = m[b] / m[a] - 1
                if abs(r) <= 0.11:
                    acc[b].append(r)
    return {d: statistics.mean(v) for d, v in acc.items() if len(v) >= 300}


def main():
    EW = ew_returns()
    D, P = s.DAYS, s.PX
    days = [d for d in D if d in EW]
    idx = {d: i for i, d in enumerate(D)}
    # 等權累積指數
    ew_lv = {}
    v = 1.0
    for d in days:
        v *= 1 + EW[d]
        ew_lv[d] = v
    rows = []
    for k in range(20, len(days)):
        d, d0 = days[k], days[k - 20]
        i, i0 = idx[d], idx[d0]
        if i - i0 > 25:  # 中間缺資料
            continue
        g = ((P[i] / P[i0] - 1) - (ew_lv[d] / ew_lv[d0] - 1)) * 100
        f20 = (P[i + 20] / P[i] - 1) * 100 if i + 20 < len(P) else None
        f60 = (P[i + 60] / P[i] - 1) * 100 if i + 60 < len(P) else None
        rows.append((d, g, f20, f60, k))
    out = [f"研究 298：加權 − 等權 20 日報酬背離 G（{rows[0][0]}～{rows[-1][0]}，{len(rows)} 天）\n"]
    out.append(f"G 分布：中位 {statistics.median(x[1] for x in rows):+.1f}pp、5% {sorted(x[1] for x in rows)[len(rows) // 20]:+.1f}、95% {sorted(x[1] for x in rows)[len(rows) * 19 // 20]:+.1f}；最新 {rows[-1][0]} G {rows[-1][1]:+.1f}pp")
    for lab, lo, hi in (("全期", "2013", "2027"), ("2013–2019", "2013", "2020"), ("2020～", "2020", "2027")):
        sel = [x for x in rows if lo <= x[0] < hi]
        gs = sorted(x[1] for x in sel)
        cuts = [gs[int(len(gs) * q / 5)] for q in range(1, 5)]
        q = lambda g: sum(g > c for c in cuts)  # noqa: E731
        out.append(f"\n【{lab}】五分位（Q1＝等權強、Q5＝權值股撐盤）")
        for h, col in ((20, 2), (60, 3)):
            cells = []
            for qq in range(5):
                v = [x[col] for x in sel if q(x[1]) == qq and x[col] is not None]
                cells.append(f"Q{qq + 1} {statistics.mean(v):+5.2f}%")
            # 不重疊取樣：每 20 個交易日取一次，Q5 − Q1 差與 t
            samp = [x for x in sel if x[4] % 20 == 0 and x[col] is not None]
            a = [x[col] for x in samp if q(x[1]) == 4]
            b = [x[col] for x in samp if q(x[1]) == 0]
            if len(a) > 2 and len(b) > 2:
                diff = statistics.mean(a) - statistics.mean(b)
                se = (statistics.variance(a) / len(a) + statistics.variance(b) / len(b)) ** 0.5
                tail = f"｜不重疊 Q5−Q1 {diff:+.2f}%（t {diff / se:+.2f}，{len(a)}／{len(b)} 筆）"
            else:
                tail = ""
            out.append(f"  {h} 日：" + "  ".join(cells) + tail)
    text = "\n".join(out)
    print(text)
    open(os.path.join(HERE, "結果_研究298_加權等權背離.txt"), "w", encoding="utf-8").write(text + "\n")


if __name__ == "__main__":
    main()
