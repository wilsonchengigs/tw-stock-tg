"""研究 04：外資台指期淨未平倉當現行策略的額外濾網

資料：期交所三大法人台指期（TX 大台）未平倉，外資多方未平倉口數 − 空方未平倉口數＝淨未平倉。
取自公開倉庫 Mason0416/taifex-cta-momentum 的 TXF_institutional_OI.csv（FinMind TaiwanFuturesInstitutionalInvestors 匯出，
2018-06-05～2026-07-22）。雲端環境擋期交所／FinMind，找不到更長的公開歷史，所以只能測約 8 年；只含大台、未含小台。

外資淨部位有很強的結構漂移（2018～2020 約淨多 3～5 萬口，2021 後多半淨空 1～6 萬口，常被解讀為避險／套利），
所以除了絕對門檻，也測「相對近 n 日均值偏離」「n 日變化」「z-score」。

期交所每天 15:00 後公布，週五收盤後判斷、下一交易日收盤成交，不偷看。
期間：2019-01-01～2026-07-22（z-score 要約半年暖身），切成 2019–2022、2023–2026 兩段；另做 00631L 真實價格。

用法：python backtest/research_04_外資期貨濾網.py [TXF_institutional_OI.csv 路徑]
"""
import csv
import io
import math
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402
import data  # noqa: E402

URL = "https://raw.githubusercontent.com/Mason0416/taifex-cta-momentum/HEAD/TXF_institutional_OI.csv"
END = "2026-07-22"
PER = {"全期 2019-2026/07": ("2019-01-01", END), "前段 2019-2022": ("2019-01-01", "2022-12-31"),
       "後段 2023-2026/07": ("2023-01-01", END)}
PX = bt.PX


def load_oi():
    if len(sys.argv) > 1:
        txt = open(sys.argv[1], encoding="utf-8-sig").read()
    else:
        txt = urllib.request.urlopen(URL, timeout=60).read().decode("utf-8-sig")
    m = {r["date"]: int(r["long_open_interest_balance_volume"]) - int(r["short_open_interest_balance_volume"])
         for r in csv.DictReader(io.StringIO(txt)) if r["institutional_investors"] == "外資"}
    out, last = [], None
    for d in bt.DAYS:
        last = m.get(d, last) if d <= END else None
        out.append(last)
    return out, min(m), max(m)


OI, OI0, OI1 = load_oi()


def chg(i, n):
    j = i - n
    if j < 0 or OI[i] is None or OI[j] is None:
        return None
    return OI[i] - OI[j]


def zs(i, n):
    if i < n or OI[i - n + 1] is None or OI[i] is None:
        return None
    xs = OI[i - n + 1:i + 1]
    mu = sum(xs) / n
    sd = math.sqrt(sum((x - mu) ** 2 for x in xs) / n)
    return (OI[i] - mu) / sd if sd else 0.0


def run(start, end, entry_ok=None, force_exit=None, early_entry=None, ein=60, eout=80, bin_=0.01, bout=0.02,
        r2=None, yearly=False):
    r2 = r2 or bt.R2
    mi, mo = bt.get_sma(ein), bt.get_sma(eout)
    i0 = next(i for i, d in enumerate(bt.DAYS) if d >= start)
    i1 = max(i for i, d in enumerate(bt.DAYS) if d <= end)
    eq = peak = 1.0
    mdd, on, pos, pend, trades, days_on = 0.0, False, False, None, 0, 0
    ys = {}
    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + (r2[i] if pos else bt.RC)
        if pend is not None:
            if pend != pos:
                eq *= 1 - bt.COST * 2
                trades += 1
            pos, pend = pend, None
        days_on += pos
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        ys[bt.DAYS[i][:4]] = eq
        if bt.WEEK_END[i] and mi[i] and mo[i]:
            p = PX[i]
            if not on:
                go = p > mi[i] * (1 + bin_)
                if go and entry_ok and not entry_ok(i):
                    go = False
                if not go and early_entry and early_entry(i):
                    go = True
                on = go
            else:
                out = p < mo[i] * (1 - bout)
                if not out and force_exit and force_exit(i):
                    out = True
                on = not out
            if on != pos:
                pend = on
    yrs = (i1 - i0) / bt.TD
    res = {"cagr": eq ** (1 / yrs) - 1, "mdd": mdd, "tpy": trades / yrs, "on": days_on / (i1 - i0 + 1)}
    if yearly:
        prev, yr = 1.0, {}
        for y in sorted(ys):
            yr[y] = ys[y] / prev - 1
            prev = ys[y]
        res["yearly"] = yr
    return res


def f(r):
    return f"{r['cagr']:6.1%}/{r['mdd']:6.1%}"


# 真實價格（00631L 調整後收盤）
_, _, L2 = data.series()
_px = [L2.get(d, (None, None))[1] for d in bt.DAYS]
R2R, _lp = [0.0], None
for _i in range(1, len(_px)):
    if _px[_i]:
        R2R.append(_px[_i] / _lp - 1 if _lp else 0.0)
        _lp = _px[_i]
    else:
        R2R.append(bt.R2[_i])


def row(name, **kw):
    rs = [run(a, b, **kw) for a, b in PER.values()]
    rr = run(*PER["全期 2019-2026/07"], r2=R2R, **kw)
    return (f"{name:30s} " + "  ".join(f(r) for r in rs) + f"  真實 {f(rr)}  {rs[0]['tpy']:4.1f}次/年 在場{rs[0]['on']:4.0%}",
            rs + [rr])


# 濾網：條件成立＝「危險」
def lvl(x):  # 淨空單超過 x 口
    return lambda i: OI[i] is not None and OI[i] < -x


def drop(n, x):  # n 日內淨部位減少超過 x 口（外資加空）
    return lambda i: (c := chg(i, n)) is not None and c < -x


def zlow(n, z):  # 淨部位相對近 n 日 z-score 低於 -z
    return lambda i: (v := zs(i, n)) is not None and v < -z


def rise(n, x, ma=20):  # n 日內淨部位增加超過 x 口（外資回補）且指數站上 MA(ma) → 提早進場
    m = bt.get_sma(ma)
    return lambda i: (c := chg(i, n)) is not None and c > x and m[i] is not None and PX[i] > m[i]


def notf(g):
    return lambda i: not g(i)


if __name__ == "__main__":
    out = ["研究 04：外資台指期淨未平倉濾網（格式：年化/最大回檔；三段＝2019-01～2026-07、2019–2022、2023～2026-07；",
           "「真實」＝同全期用 00631L 真實價格；在場＝持有 00631L 的時間比例）",
           f"外資 TX 淨未平倉資料 {OI0}～{OI1}（來源：Mason0416/taifex-cta-momentum，FinMind 匯出）", ""]
    base_t, base = row("現行（MA60×1.01 進／MA80×0.98 出）")
    out.append(base_t)
    allrows = []

    def grp(title, key, items):
        out.append(f"\n== {title} ==")
        for name, kw in items:
            t, rs = row(name, **kw)
            out.append(t)
            allrows.append((key, name, kw, rs))

    grp("A. 外資淨空單超過 x 口就不進場（絕對門檻）", "A",
        [(f"x={x}", dict(entry_ok=notf(lvl(x)))) for x in (10000, 20000, 30000, 40000, 50000)])
    grp("B. 淨空單超過 x 口：不進，且在場也出場", "B",
        [(f"x={x}", dict(entry_ok=notf(lvl(x)), force_exit=lvl(x))) for x in (20000, 30000, 40000, 50000)])
    grp("C. 近 n 日外資淨部位減少超過 x 口（加空）就不進場", "C",
        [(f"n={n} x={x}", dict(entry_ok=notf(drop(n, x)))) for n in (5, 10, 20) for x in (5000, 10000, 15000, 20000)])
    grp("D. 近 n 日加空超過 x 口：不進，且在場也出場", "D",
        [(f"n={n} x={x}", dict(entry_ok=notf(drop(n, x)), force_exit=drop(n, x)))
         for n in (5, 10, 20) for x in (10000, 15000, 20000)])
    grp("E. 淨部位相對近 n 日 z-score < -z：不進", "E",
        [(f"n={n} z={z}", dict(entry_ok=notf(zlow(n, z)))) for n in (60, 120, 250) for z in (1.0, 1.5, 2.0)])
    grp("F. z-score < -z：不進，且在場也出場", "F",
        [(f"n={n} z={z}", dict(entry_ok=notf(zlow(n, z)), force_exit=zlow(n, z)))
         for n in (60, 120, 250) for z in (1.0, 1.5, 2.0)])
    grp("G. 近 n 日外資回補超過 x 口、且指數站上 20 日線 → 提早進場", "G",
        [(f"n={n} x={x}", dict(early_entry=rise(n, x))) for n in (5, 10, 20) for x in (10000, 15000, 20000)])

    out.append("\n== 各類：全期年化勝過現行的組數／三段＋真實都勝過的組數 ==")
    for k in "ABCDEFG":
        rs = [r for r in allrows if r[0] == k]
        w1 = sum(r[3][0]["cagr"] > base[0]["cagr"] + 1e-9 for r in rs)
        w4 = sum(all(r[3][j]["cagr"] > base[j]["cagr"] + 1e-9 for j in range(4)) for r in rs)
        out.append(f"{k}: 全期勝 {w1}/{len(rs)}　三段＋真實都勝 {w4}/{len(rs)}")

    out.append("\n== 全期年化較高且回檔不更深的組合 ==")
    good = [r for r in allrows if r[3][0]["cagr"] > base[0]["cagr"] + 1e-9 and r[3][0]["mdd"] >= base[0]["mdd"] - 1e-9]
    for g in good:
        out.append(f"{g[0]} {g[1]}: " + "  ".join(f(r) for r in g[3]))
    if not good:
        out.append("（無）")

    if good:
        best = max(good, key=lambda r: r[3][0]["cagr"])
        out.append(f"\n== 最好一組 {best[0]} {best[1]} 搭配鄰近進出場均線（全期，現行 vs 加濾網）==")
        for ein in (50, 60, 70):
            for eout in (70, 80, 100):
                a = run(*PER["全期 2019-2026/07"], ein=ein, eout=eout)
                b = run(*PER["全期 2019-2026/07"], ein=ein, eout=eout, **best[2])
                out.append(f"MA{ein}/MA{eout}: 現行 {f(a)}  加濾網 {f(b)}")
        ya = run(*PER["全期 2019-2026/07"], yearly=True)["yearly"]
        yb = run(*PER["全期 2019-2026/07"], yearly=True, **best[2])["yearly"]
        out.append("逐年差異（加濾網 − 現行）：" + "  ".join(f"{y}:{yb[y] - ya[y]:+.1%}" for y in sorted(ya)))

    out.append("\n== 參考：大盤（1x≈0050）買進持有 ==")
    out.append("  ".join(f(bt.run(bt.buyhold(), bt.POS['1x'], bt.POS['1x'], a, b) | {"tpy": 0}) for a, b in PER.values()))
    out.append("\n== 參考：外資淨未平倉每半年取樣 ==")
    out.append("  ".join(f"{bt.DAYS[i][:7]}:{OI[i]:+d}" for i in range(len(bt.DAYS))
                         if OI[i] is not None and bt.DAYS[i][5:7] in ("01", "07") and bt.DAYS[i - 1][5:7] != bt.DAYS[i][5:7]))

    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究04_外資期貨濾網.txt"), "w", encoding="utf-8").write(txt + "\n")
