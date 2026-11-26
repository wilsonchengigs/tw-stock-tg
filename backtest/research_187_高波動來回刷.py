"""研究 187：如果未來是「高波動、大幅來回刷」，主策略要不要調整？（使用者 2026-11-26）

研究 05／82／98 測過「看近 20～120 日波動調槓桿／緩衝」，都比現行差（短期波動高峰常是 V 轉起點）。這裡換三個角度：
A. 量化：加權每年實現波動（1990～）、核心策略每年交易次數與虧損筆數（被刷幾次）、2026 在歷史的位置
B. 正2 的波動耗損：每年「2×加權報酬 − 正2 報酬」與當年波動的關係（理論 ≈ σ²）
C. 長期波動規則（新）：近 250／500 日年化波動 > th 才降槓桿（只對「持續」的高波動反應，不對短暫恐慌反應）
   在 1990～2026 核心策略（無融資濾網，1990 年代沒有融資資料）與 v3（2002～、真實價）上測
D. 壓力模擬：把 1998～2026 每日報酬的「波動」放大 k＝1.5／2 倍（r' = μ + k(r − μ)，漂移不變），
   重建價格路徑、重算均線訊號，看核心策略在不同槓桿、規則下的表現；再看真實的 1990～1997（高波動盤整）樣本外
用法：python -X utf8 backtest/research_187_高波動來回刷.py
"""
import csv
import importlib.util
import math
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402

old = [(r["date"], float(r["close"])) for r in csv.DictReader(open(os.path.join(HERE, "taiex_1990_1997.csv"), encoding="utf-8"))]
new = [(d, p) for d, p in zip(bt.DAYS, bt.PX) if d >= "1998-01-01"]
SER = old + new
D = [d for d, _ in SER]
P0 = [p for _, p in SER]
TD = 245
DIV, DRAG, RC, COST = 0.03, 0.01, 0.01 / TD, 0.0025


def weekend(days):
    return [i == len(days) - 1 or date.fromisoformat(days[i]).isocalendar()[:2] != date.fromisoformat(days[i + 1]).isocalendar()[:2]
            for i in range(len(days))]


WE0 = weekend(D)


def sma(p, n):
    out, s = [None] * len(p), 0.0
    for i, x in enumerate(p):
        s += x
        if i >= n:
            s -= p[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def rvol(p, n):
    r = [0.0] + [p[i] / p[i - 1] - 1 for i in range(1, len(p))]
    out = [None] * len(p)
    s = q = 0.0
    for i in range(1, len(p)):
        s += r[i]
        q += r[i] * r[i]
        if i > n:
            s -= r[i - n]
            q -= r[i - n] ** 2
        if i >= n:
            m = s / n
            out[i] = math.sqrt(max(q / n - m * m, 0) * TD)
    return out


def core(p, days, we, start, end, lev_fn=lambda i: 2.0, trades=None):
    """核心均線策略（MA60×1.01 進、MA80×0.975 出，週五判斷、隔天收盤成交）；槓桿 1～2 倍＝正2 與 1x 混合"""
    m60, m80 = sma(p, 60), sma(p, 80)
    r1 = [0.0] + [p[i] / p[i - 1] - 1 + DIV / TD for i in range(1, len(p))]
    r2 = [0.0] + [2 * r1[i] - DRAG / TD for i in range(1, len(p))]
    i0 = next(i for i, d in enumerate(days) if d >= start)
    i1 = max(i for i, d in enumerate(days) if d <= end)
    eq = peak = 1.0
    mdd, st, cur, pend, entry = 0.0, False, 0.0, None, None
    for i in range(i0, i1 + 1):
        if i > i0:
            L = cur
            eq *= 1 + (RC if L <= 0 else (L * r1[i] + (1 - L) * RC if L <= 1 else (L - 1) * r2[i] + (2 - L) * r1[i]))
        if pend is not None:
            eq *= 1 - COST * abs(pend - cur)
            if trades is not None:
                if cur == 0 and pend > 0:
                    entry = (days[i], eq)
                elif pend == 0 and cur > 0 and entry:
                    trades.append((entry[0], days[i], eq / entry[1] - 1))
            cur, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if we[i] and i >= 260:
            st = (not p[i] < m80[i] * 0.975) if st else (p[i] > m60[i] * 1.01)
            t = lev_fn(i) if st else 0.0
            if t != cur:
                pend = t
    yrs = (i1 - i0) / TD
    return eq ** (1 / yrs) - 1, mdd


def part_a(L):
    L.append("【A】加權每年實現波動、核心策略（2x）交易次數與虧損筆數")
    tr = []
    core(P0, D, WE0, "1991-01-01", "2026-12-31", trades=tr)
    years = sorted({d[:4] for d in D})
    vols = []
    for y in years:
        idx = [i for i, d in enumerate(D) if d[:4] == y and i > 0]
        r = [P0[i] / P0[i - 1] - 1 for i in idx]
        m = sum(r) / len(r)
        v = math.sqrt(sum((x - m) ** 2 for x in r) / len(r) * TD)
        a = P0[idx[-1]] / P0[idx[0] - 1] - 1
        t = [x for x in tr if x[1][:4] == y]
        vols.append((y, v, a, len(t), sum(x[2] < 0 for x in t), sum(x[2] for x in t if x[2] < 0)))
    L.append("  年份 波動 加權漲跌 出場筆數 虧損筆數 虧損合計")
    for y, v, a, n, k, s in vols:
        L.append(f"  {y} {v:5.0%} {a:+6.0%}  {n}  {k}  {s:+.0%}")
    sv = sorted(v for _, v, *_ in vols)
    v26 = dict((y, v) for y, v, *_ in vols)["2026"]
    L.append(f"  2026 波動 {v26:.0%}：1990～2026 共 {len(vols)} 年中第 {sum(v <= v26 for v in sv)} 低（越大越高）；中位 {sv[len(sv) // 2]:.0%}")
    return vols


def part_b(L, vols):
    L.append("\n【B】正2 波動耗損：每年 2×(加權+配息) − 正2 模擬報酬（理論約 σ² − 1%）")
    r1 = [0.0] + [P0[i] / P0[i - 1] - 1 + DIV / TD for i in range(1, len(P0))]
    rows = []
    for y, v, *_ in vols:
        idx = [i for i, d in enumerate(D) if d[:4] == y and i > 0]
        e1 = e2 = 1.0
        for i in idx:
            e1 *= 1 + r1[i]
            e2 *= 1 + 2 * r1[i] - DRAG / TD
        rows.append((v, 2 * (e1 - 1) - (e2 - 1)))
    for lo, hi in ((0, 0.15), (0.15, 0.2), (0.2, 0.25), (0.25, 0.3), (0.3, 0.4), (0.4, 1)):
        g = [d for v, d in rows if lo <= v < hi]
        if g:
            L.append(f"  波動 {lo:.0%}～{hi:.0%}：{len(g):>2} 年，平均耗損 {sum(g) / len(g):+.1%}（理論 σ² 約 {((lo + min(hi, 0.6)) / 2) ** 2:.1%}）")


def lev_rule(p, n, th, low):
    v = rvol(p, n)
    return lambda i: low if (v[i] is not None and v[i] > th) else 2.0


SEGS = [("1991-01-01", "1997-12-31"), ("1998-01-01", "2012-12-31"), ("2013-01-01", "2026-12-31"), ("1991-01-01", "2026-12-31")]


def part_c(L):
    L.append("\n【C】長期波動降槓桿（核心策略，1990 年代｜1998–2012｜2013–2026｜1991–2026 全期；年化/最大回檔）")
    variants = [("固定 2x", lambda i: 2.0), ("固定 1.5x", lambda i: 1.5), ("固定 1x", lambda i: 1.0)]
    for n in (250, 500):
        for th in (0.25, 0.30, 0.35):
            for low in (1.0, 1.5):
                variants.append((f"{n} 日波動 >{th:.0%} → {low}x", lev_rule(P0, n, th, low)))
    for name, fn in variants:
        rs = [core(P0, D, WE0, a, b, lev_fn=fn) for a, b in SEGS]
        L.append(f"  {name:<22}" + " | ".join(f"{c:6.1%}/{m:6.1%}" for c, m in rs))
    # v3（含融資濾網，2002～、真實價）
    spec = importlib.util.spec_from_file_location("r186", os.path.join(HERE, "research_186_主策略全面健檢.py"))
    R186 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(R186)
    v = {n: rvol(R186.PX, n) for n in (250, 500)}
    L.append("  v3（含融資濾網）：全期 2002–｜前段｜後段｜真實 2015-09–")
    L.append("    現行 2x               " + R186.fmt()[2])
    for n in (250, 500):
        for th in (0.25, 0.30):
            for low in (1.0, 1.5):
                fn = (lambda i, line, n=n, th=th, low=low: low if (v[n][i] is not None and v[n][i] > th) else 2.0)
                L.append(f"    {n} 日 >{th:.0%} → {low}x  " + R186.fmt(lev_fn=fn)[2])


def scaled_path(k, seed_start="1998-01-01"):
    i0 = D.index(next(d for d in D if d >= seed_start))
    r = [P0[i] / P0[i - 1] - 1 for i in range(i0 + 1, len(P0))]
    mu = sum(r) / len(r)
    p = [P0[i0]]
    for x in r:
        y = mu + k * (x - mu)
        p.append(p[-1] * max(1 + y, 0.5))
    return p, D[i0:]


def part_d(L):
    L.append("\n【D】壓力模擬：1998～2026 波動放大 k 倍（漂移不變），核心策略（年化/最大回檔；加權本身年化）")
    for k in (1.0, 1.25, 1.5, 2.0):
        p, days = scaled_path(k)
        we = weekend(days)
        bh = (p[-1] / p[0]) ** (TD / (len(p) - 1)) - 1
        vol = rvol(p, len(p) - 2)[-1]
        L.append(f"  k={k}（加權波動約 {vol:.0%}、加權年化 {bh:+.1%}）")
        tr = []
        core(p, days, we, "1999-01-01", "2026-12-31", trades=tr)
        L.append(f"    交易 {len(tr)} 筆、虧損 {sum(t[2] < 0 for t in tr)} 筆")
        for name, fn in (("固定 2x", lambda i: 2.0), ("固定 1.5x", lambda i: 1.5), ("固定 1x", lambda i: 1.0),
                         ("250 日 >30% → 1.5x", lev_rule(p, 250, 0.30, 1.5)), ("250 日 >30% → 1x", lev_rule(p, 250, 0.30, 1.0)),
                         ("500 日 >30% → 1x", lev_rule(p, 500, 0.30, 1.0))):
            c, m = core(p, days, we, "1999-01-01", "2026-12-31", lev_fn=fn)
            L.append(f"    {name:<20}{c:6.1%}/{m:6.1%}")


def main():
    L = ["研究 187：高波動、大幅來回刷時主策略要不要調整"]
    vols = part_a(L)
    part_b(L, vols)
    part_c(L)
    part_d(L)
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究187_高波動來回刷.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
