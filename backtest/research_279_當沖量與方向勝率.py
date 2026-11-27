"""研究 279：台指期日盤當沖——「量 × 方向」的勝率（1998～2026 真實台指期）

使用者：繼續研究當沖期貨「量跟方向」的勝率。研究 62／62b 只有 29 天 1 分 K；這裡改用 28 年台指期日行情，
只用「開盤前已知」的量與方向，交易一律是當天日盤 08:45 開盤進、13:45 收盤出（不留倉），成本每筆 3 點。

條件（都在開盤前或開盤當下已知）：
- 量：前一日台指期日盤總口數（全部月份）÷ 前 20 日平均；或證交所成交金額 ÷ 前 20 日平均
- 方向：前一日 K 棒（日盤收 vs 開）、前一日漲跌（收 vs 前收，同契約）、今天開盤跳空（開 vs 前一日日盤收）
- 夜盤（2017-05～）：前一晚夜盤口數 ÷ 前 20 晚平均 × 整晚方向（夜收 vs 前日盤收）
做法：
(1) 二維表：量比分組 × 方向分組 → 今天「做多」當沖的勝率、每筆點數（扣成本）；順勢／逆勢只是正負號相反
(2) 規則家族：量比 ≥ k（1.2／1.5／2.0）× 量種類 × 方向種類 → 順勢當沖；環狀平移「條件序列」400 次（目標序列不動），
    單組 p 與最小 p 值法的家族 p；前段 1998–2012、後段 2013–2026 分開
用法：python -X utf8 backtest/research_279_當沖量與方向勝率.py
"""
import csv
import types
from collections import defaultdict
import os
import random
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
# 直接載入 63d 的 load()（不執行 63d 頂層對研究 61 的相依，tx_daily.csv 被 .gitignore 排除）
_src = open(os.path.join(HERE, "research_63d_爆量收黑_台指期真實價.py"), encoding="utf-8").read()
r63d = types.ModuleType("r63d")
r63d.__dict__.update({"csv": csv, "os": os, "defaultdict": defaultdict, "HERE": HERE})
exec(_src[_src.index("def num("):_src.index("def main(")], r63d.__dict__)
r63d.AMT = {r["date"]: float(r["amount"]) for r in csv.DictReader(open(os.path.join(HERE, "turnover_daily.csv"), encoding="utf-8"))}
COST = 3.0
NSHIFT = 400
random.seed(279)


def build():
    dates, day, night, near = r63d.load()
    n = len(dates)
    volf = [sum(v[4] for v in day[d].values()) for d in dates]
    voln = [sum(v[4] for v in night[d].values()) if d in night else 0 for d in dates]
    amt = [r63d.AMT.get(d) for d in dates]

    def ratio(series, i):
        xs = [series[k] for k in range(max(0, i - 20), i) if series[k]]
        return series[i] / statistics.mean(xs) if series[i] and len(xs) >= 16 else None

    rows = []
    for i in range(22, n):
        d, pd, ppd = dates[i], dates[i - 1], dates[i - 2]
        m = near[d]
        db, pb = day[d].get(m), day[pd].get(m)
        if not db or not pb or db[0] <= 0 or pb[0] <= 0:
            continue
        ppb = day[ppd].get(m)
        o, c = db[0], db[3]
        nb = night[d].get(m) if d in night else None
        r = {
            "d": d, "o": o,
            "pts": c - o,                         # 做多當沖點數（未扣成本）
            "ret": (c - o) / o,
            "vf": ratio(volf, i - 1),             # 前一日台指期口數比
            "va": ratio(amt, i - 1),              # 前一日成交金額比
            "kbar": pb[3] / pb[0] - 1,            # 前一日 K 棒
            "chg": (pb[3] / ppb[3] - 1) if ppb else None,  # 前一日漲跌（同契約）
            "gap": o / pb[3] - 1,                 # 今天開盤跳空
            "vn": ratio(voln, i) if nb and voln[i] else None,  # 前一晚夜盤量比（記在 D）
            "ndir": (nb[3] / pb[3] - 1) if nb else None,
        }
        rows.append(r)
    return rows


def pnl(r, side):
    return side * r["pts"] - COST


def fmt_cell(xs):
    if not xs:
        return "      -      "
    w = sum(1 for x in xs if x > 0) / len(xs)
    return f"{len(xs):4d} {w*100:3.0f}% {statistics.mean(xs):+6.1f}"


VB = [(0, 0.8, "<0.8"), (0.8, 1.2, "0.8-1.2"), (1.2, 1.5, "1.2-1.5"), (1.5, 2.0, "1.5-2"), (2.0, 99, ">=2")]
DB = [(-1, -0.02, "<=-2%"), (-0.02, -0.01, "-2~-1%"), (-0.01, 0, "-1~0%"), (0, 0.01, "0~1%"), (0.01, 0.02, "1~2%"), (0.02, 1, ">=2%")]
GB = [(-1, -0.01, "<=-1%"), (-0.01, -0.003, "-1~-0.3%"), (-0.003, 0.003, "±0.3%"), (0.003, 0.01, "0.3~1%"), (0.01, 1, ">=1%")]


def table(L, rows, vkey, dkey, dbins, title):
    L.append(f"\n【{title}】格子＝筆數 做多勝率 做多每筆點數（扣 3 點；做空＝點數取負再扣 6 點）")
    L.append(" " * 9 + "".join(f"{b[2]:>15}" for b in dbins) + "         合計")
    for lo, hi, name in VB:
        line = f"{name:>8} "
        allx = []
        for dlo, dhi, _ in dbins:
            xs = [pnl(r, 1) for r in rows if r[vkey] is not None and r[dkey] is not None
                  and lo <= r[vkey] < hi and dlo <= r[dkey] < dhi]
            allx += xs
            line += f"{fmt_cell(xs):>15}"
        line += f"  {fmt_cell(allx)}"
        L.append(line)
    line = f"{'合計':>7} "
    for dlo, dhi, _ in dbins:
        xs = [pnl(r, 1) for r in rows if r[vkey] is not None and r[dkey] is not None and dlo <= r[dkey] < dhi]
        line += f"{fmt_cell(xs):>15}"
    L.append(line)


def signal(rows, vkey, k, dkey, dth):
    """回傳每列的方向：+1 前一日方向漲、-1 跌、0 沒訊號"""
    s = []
    for r in rows:
        v, x = r[vkey], r[dkey]
        if v is None or x is None or v < k or abs(x) < dth:
            s.append(0)
        else:
            s.append(1 if x > 0 else -1)
    return s


def stat(rows, sig, sign):
    xs = [sign * s * r["pts"] - COST for r, s in zip(rows, sig) if s]
    if not xs:
        return 0, 0, 0, 0
    return len(xs), sum(1 for x in xs if x > 0) / len(xs), statistics.mean(xs), statistics.mean(
        [sign * s * r["ret"] * 100 for r, s in zip(rows, sig) if s])


def main():
    rows = build()
    L = ["研究 279：台指期日盤當沖 × 量與方向（近月真實價；08:45 開盤進、13:45 收盤出；每筆成本 3 點）",
         f"交易日 {len(rows)}（{rows[0]['d']}～{rows[-1]['d']}）"]
    allx = [pnl(r, 1) for r in rows]
    L.append(f"基準：每天都做多當沖 {fmt_cell(allx)}；每天做空 {fmt_cell([pnl(r, -1) for r in rows])}；"
             f"平均日盤振幅 |開→收| {statistics.mean(abs(r['pts']) for r in rows):.0f} 點")

    table(L, rows, "vf", "kbar", DB, "前一日台指期口數比 × 前一日 K 棒（收 vs 開）")
    table(L, rows, "vf", "chg", DB, "前一日台指期口數比 × 前一日漲跌")
    table(L, [r for r in rows if r["va"] is not None], "va", "chg", DB, "前一日成交金額比 × 前一日漲跌")
    table(L, rows, "vf", "gap", GB, "前一日台指期口數比 × 今天開盤跳空（開 vs 前日盤收）")
    nrows = [r for r in rows if r["vn"] is not None]
    if nrows:
        L.append(f"\n夜盤樣本 {len(nrows)} 天（{nrows[0]['d']}～）")
        table(L, nrows, "vn", "ndir", DB, "前一晚夜盤量比 × 整晚方向（夜收 vs 前日盤收）")

    # 規則家族
    L.append("\n【規則家族：量比 ≥ k 且 |方向| ≥ 門檻 → 今天順勢當沖（逆勢＝相反）】")
    L.append("每筆＝點數扣成本；p＝環狀平移條件序列 400 次，順勢每筆平均 ≥ 實際的比例（逆勢看 ≤）")
    specs = []
    for vkey, vname in (("vf", "期貨口數"), ("va", "成交金額")):
        for dkey, dname, dth in (("kbar", "K棒", 0.0), ("chg", "漲跌", 0.0), ("chg", "漲跌≥1%", 0.01),
                                 ("gap", "跳空≥0.3%", 0.003)):
            for k in (1.2, 1.5, 2.0):
                specs.append((vkey, vname, dkey, dname, dth, k))
    for nk in (1.5, 2.0):
        specs.append(("vn", "夜盤量", "ndir", "整晚", 0.0, nk))
        specs.append(("vn", "夜盤量", "ndir", "整晚≥1%", 0.01, nk))

    pts = [r["pts"] for r in rows]
    real, shifted = [], []
    for vkey, vname, dkey, dname, dth, k in specs:
        sig = signal(rows, vkey, k, dkey, dth)
        real.append(sum(s * p for s, p in zip(sig, pts)) / max(1, sum(1 for s in sig if s)))
    # 平移：只在該條件有資料的區段內平移（夜盤 2017 起）
    valid = {}
    for j, (vkey, _, dkey, _, _, _) in enumerate(specs):
        valid[j] = [i for i, r in enumerate(rows) if r[vkey] is not None and r[dkey] is not None]
    sigs = [signal(rows, *([s[0], s[5], s[2], s[4]])) for s in specs]
    perm_means = [[] for _ in specs]
    for t in range(NSHIFT):
        for j in range(len(specs)):
            ids = valid[j]
            sh = random.randint(20, len(ids) - 20)
            s_ids = ids[sh:] + ids[:sh]
            tot = cnt = 0
            for a, b in zip(ids, s_ids):
                s = sigs[j][b]
                if s:
                    tot += s * pts[a]
                    cnt += 1
            perm_means[j].append(tot / max(1, cnt))
    pf, pr = [], []
    L.append(f"{'量':<6}{'方向':<10}{'k':>4}{'筆數':>6}{'順勢勝率':>8}{'順勢點':>8}{'逆勢點':>8}{'順勢%':>8}{'p順':>6}{'p逆':>6}"
             f"{'前段順':>8}{'後段順':>8}")
    for j, (vkey, vname, dkey, dname, dth, k) in enumerate(specs):
        sig = sigs[j]
        nn, w, mf, rf = stat(rows, sig, 1)
        _, _, mr, _ = stat(rows, sig, -1)
        p_f = sum(1 for x in perm_means[j] if x >= real[j]) / NSHIFT
        p_r = sum(1 for x in perm_means[j] if x <= real[j]) / NSHIFT
        pf.append(p_f)
        pr.append(p_r)
        early = [s if r["d"] < "2013" else 0 for s, r in zip(sig, rows)]
        late = [s if r["d"] >= "2013" else 0 for s, r in zip(sig, rows)]
        e, lt = stat(rows, early, 1)[2], stat(rows, late, 1)[2]
        L.append(f"{vname:<6}{dname:<10}{k:>4}{nn:>6}{w*100:>7.0f}%{mf:>+8.1f}{mr:>+8.1f}{rf:>+8.3f}{p_f:>6.2f}{p_r:>6.2f}"
                 f"{e:>+8.1f}{lt:>+8.1f}")
    # 家族 p（最小 p 值法）：用平移分布自身的排名 p
    def fam(side):
        realp = min(pf if side > 0 else pr)
        mins = []
        for t in range(NSHIFT):
            mp = 1.0
            for j in range(len(specs)):
                x = perm_means[j][t]
                if side > 0:
                    p = sum(1 for y in perm_means[j] if y >= x) / NSHIFT
                else:
                    p = sum(1 for y in perm_means[j] if y <= x) / NSHIFT
                mp = min(mp, p)
            mins.append(mp)
        return realp, sum(1 for m in mins if m <= realp) / NSHIFT
    for side, nm in ((1, "順勢"), (-1, "逆勢")):
        rp, fp = fam(side)
        L.append(f"家族（{len(specs)} 組）{nm}：最小單組 p {rp:.3f} → 家族 p {fp:.3f}")

    # 逐年：最常被提到的兩條
    L.append("\n【逐年】(a) 期貨口數 ≥1.5 × 前日漲跌 逆勢當沖  (b) 期貨口數 ≥1.5 × 跳空≥0.3% 逆勢當沖（回補）  每筆點數／筆數")
    sa = signal(rows, "vf", 1.5, "chg", 0.0)
    sb = signal(rows, "vf", 1.5, "gap", 0.003)
    for y in sorted({r["d"][:4] for r in rows}):
        out = []
        for sig in (sa, sb):
            xs = [-s * r["pts"] - COST for r, s in zip(rows, sig) if s and r["d"][:4] == y]
            out.append(f"{statistics.mean(xs):+7.1f}／{len(xs):3d}" if xs else "     -     ")
        L.append(f"{y}  (a) {out[0]}   (b) {out[1]}")

    txt = "\n".join(L)
    print(txt)
    open(os.path.join(HERE, "結果_研究279_當沖量與方向勝率.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
