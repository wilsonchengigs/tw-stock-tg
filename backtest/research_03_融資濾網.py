"""研究 03：融資餘額當現行策略的額外濾網

資料：上市融資金額（FinMind TaiwanStockTotalMarginPurchaseShortSale / MarginPurchaseMoney，2001-01-03～），
取自公開倉庫 salmonmisosoup/leverage-dashboard 的 data/margin_tw.csv（雲端環境擋 FinMind／證交所，只能用鏡像）。
融資維持率沒有長期公開歷史資料，所以改用融資餘額本身的變化當代理：
- 融資 N 日變化率（融資快速下降＝斷頭／去槓桿）
- 融資／加權指數 比值相對一年均值（散戶槓桿相對過熱）

證交所每天收盤後公布融資餘額，週五判斷、下一交易日收盤成交，不會偷看。
融資資料 2001 起、比值要一年均值，所以三段改為 2002–2026、2002–2012、2013–2026，現行策略也在同期間比較。

用法：python backtest/research_03_融資濾網.py [margin_tw.csv 路徑]
"""
import csv
import os
import sys
import urllib.request
import io

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402
import data  # noqa: E402

URL = "https://raw.githubusercontent.com/salmonmisosoup/leverage-dashboard/HEAD/data/margin_tw.csv"
PER = {"全期 2002-2026": ("2002-01-01", "2026-12-31"), "前段 2002-2012": ("2002-01-01", "2012-12-31"),
       "後段 2013-2026": ("2013-01-01", "2026-12-31")}


def load_margin():
    if len(sys.argv) > 1:
        txt = open(sys.argv[1], encoding="utf-8").read()
    else:
        txt = urllib.request.urlopen(URL, timeout=60).read().decode("utf-8")
    m = {r["date"]: float(r["balance"]) for r in csv.DictReader(io.StringIO(txt)) if r["balance"]}
    out, last = [], None
    for d in bt.DAYS:
        last = m.get(d, last)
        out.append(last)
    return out


M = load_margin()
PX = bt.PX


def chg(arr, i, n):
    j = i - n
    if j < 0 or arr[i] is None or arr[j] is None:
        return None
    return arr[i] / arr[j] - 1


RATIO = [m / p if m else None for m, p in zip(M, PX)]


def ratio_dev(i, n=250):
    if i < n or any(RATIO[k] is None for k in (i - n + 1, i)):
        return None
    xs = RATIO[i - n + 1:i + 1]
    return RATIO[i] / (sum(xs) / n) - 1


def run(start, end, entry_ok=None, force_exit=None, early_entry=None, ein=60, eout=80, bin_=0.01, bout=0.02,
        r2=None, yearly=False):
    """現行規則 + 濾網：
    entry_ok(i)   -> 一般進場訊號成立時，濾網要 True 才進（否則延後）
    force_exit(i) -> True 時即使沒跌破出場線也出場
    early_entry(i)-> True 時即使沒站上進場線也進場（洗盤後提早進）
    """
    r2 = r2 or bt.R2
    mi, mo = bt.get_sma(ein), bt.get_sma(eout)
    i0 = next(i for i, d in enumerate(bt.DAYS) if d >= start)
    i1 = max(i for i, d in enumerate(bt.DAYS) if d <= end)
    eq = peak = 1.0
    mdd, on, pos, pend, trades = 0.0, False, False, None, 0
    ys = {}
    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + (r2[i] if pos else bt.RC)
        if pend is not None:
            if pend != pos:
                eq *= 1 - bt.COST * 2
                trades += 1
            pos, pend = pend, None
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
    res = {"cagr": eq ** (1 / yrs) - 1, "mdd": mdd, "tpy": trades / yrs}
    if yearly:
        prev, yr = 1.0, {}
        for y in sorted(ys):
            yr[y] = ys[y] / prev - 1
            prev = ys[y]
        res["yearly"] = yr
    return res


def f(r):
    return f"{r['cagr']:6.1%}/{r['mdd']:6.1%}"


def row(name, **kw):
    rs = [run(a, b, **kw) for a, b in PER.values()]
    return f"{name:34s} " + "  ".join(f(r) for r in rs) + f"  {rs[0]['tpy']:4.1f}次/年", rs


def ok_drop(n, x):  # 融資 n 日跌超過 x → 延後進場
    return lambda i: (c := chg(M, i, n)) is None or c > -x


def ok_hot(y, n=250):  # 融資/指數比值 高於 n 日均值 y 以上 → 不進
    return lambda i: (d := ratio_dev(i, n)) is None or d < y


def exit_hot(y, n=250):
    return lambda i: (d := ratio_dev(i, n)) is not None and d > y


def exit_divergence(n, x):  # 指數 n 日跌超過 x 但融資反而增加（散戶攤平）→ 提早出
    return lambda i: (a := chg(PX, i, n)) is not None and (b := chg(M, i, n)) is not None and a < -x and b > 0


def early_washout(n, x, ma=20):  # 融資 n 日大減 x 以上、且指數重新站上 MA(ma) → 提早進場
    m = bt.get_sma(ma)

    def g(i):
        c = chg(M, i, n)
        return c is not None and c < -x and m[i] is not None and PX[i] > m[i]
    return g


if __name__ == "__main__":
    out = ["研究 03：融資餘額濾網（格式：年化/最大回檔；三段＝全期 2002-2026、前段 2002-2012、後段 2013-2026）",
           f"融資資料 {bt.DAYS[next(i for i, v in enumerate(M) if v)]}～{bt.DAYS[-1]}，大盤買進持有比較基準見最下方", ""]
    base_txt, base = row("現行（MA60×1.01 進／MA80×0.98 出）")
    out.append(base_txt)
    allrows = []

    out.append("\n== A. 融資快速下降時延後進場（融資 n 日跌幅 > x 就不進）==")
    for n in (10, 20, 40, 60):
        for x in (0.05, 0.10, 0.15, 0.20):
            t, rs = row(f"n={n} x={x:.0%}", entry_ok=ok_drop(n, x))
            out.append(t)
            allrows.append(("A", n, x, rs))

    out.append("\n== B. 融資／指數比值高於一年均值 y 以上就不進場 ==")
    for y in (0.05, 0.10, 0.15, 0.20, 0.30):
        t, rs = row(f"y={y:.0%}", entry_ok=ok_hot(y))
        out.append(t)
        allrows.append(("B", y, None, rs))

    out.append("\n== C. 融資／指數比值高於一年均值 y 以上，在場也出場（並且不進）==")
    for y in (0.10, 0.15, 0.20, 0.30):
        t, rs = row(f"y={y:.0%}", entry_ok=ok_hot(y), force_exit=exit_hot(y))
        out.append(t)
        allrows.append(("C", y, None, rs))

    out.append("\n== D. 指數 n 日跌 x 以上但融資增加（散戶接刀）→ 提早出場 ==")
    for n in (10, 20, 40):
        for x in (0.03, 0.05, 0.08):
            t, rs = row(f"n={n} x={x:.0%}", force_exit=exit_divergence(n, x))
            out.append(t)
            allrows.append(("D", n, x, rs))

    out.append("\n== E. 融資 n 日大減 x 以上且指數站上 20 日線 → 提早進場（洗盤後抄底）==")
    for n in (20, 40, 60):
        for x in (0.10, 0.15, 0.20, 0.25):
            t, rs = row(f"n={n} x={x:.0%}", early_entry=early_washout(n, x))
            out.append(t)
            allrows.append(("E", n, x, rs))

    out.append("\n== 勝過現行的組合（全期年化較高、且全期回檔不更深）==")
    good = [r for r in allrows if r[3][0]["cagr"] > base[0]["cagr"] and r[3][0]["mdd"] >= base[0]["mdd"]]
    for g in good:
        out.append(f"{g[0]} {g[1]} {g[2]}: " + "  ".join(f(r) for r in g[3]))
    if not good:
        out.append("（無）")

    # 各組相對現行：三段都勝的比例
    out.append("\n== 各類濾網：三段年化都勝過現行的組數 ==")
    for k in "ABCDE":
        rs = [r for r in allrows if r[0] == k]
        w = sum(all(r[3][j]["cagr"] > base[j]["cagr"] for j in range(3)) for r in rs)
        out.append(f"{k}: {w}/{len(rs)}")

    # 真實價格驗證：挑每類全期最好的一組
    out.append("\n== 真實價格 2015-09-01～（00631L 調整後收盤）：每類全期最好的一組 ==")
    _, _, l2 = data.series()
    px = [l2.get(d, (None, None))[1] for d in bt.DAYS]
    lp, r2r = None, [0.0]
    for i in range(1, len(px)):
        if px[i]:
            r2r.append(px[i] / lp - 1 if lp else 0.0)
            lp = px[i]
        else:
            r2r.append(bt.R2[i])
    s, e = "2015-09-01", "2026-12-31"
    out.append(f"{'現行':34s} {f(run(s, e, r2=r2r))}")
    mk = {"A": lambda a, b: dict(entry_ok=ok_drop(a, b)), "B": lambda a, b: dict(entry_ok=ok_hot(a)),
          "C": lambda a, b: dict(entry_ok=ok_hot(a), force_exit=exit_hot(a)),
          "D": lambda a, b: dict(force_exit=exit_divergence(a, b)), "E": lambda a, b: dict(early_entry=early_washout(a, b))}
    for k in "ABCDE":
        best = max((r for r in allrows if r[0] == k), key=lambda r: r[3][0]["cagr"])
        out.append(f"{k} {best[1]} {best[2]}: {f(run(s, e, r2=r2r, **mk[k](best[1], best[2])))}")

    out.append("\n== F. C 類（比值過熱就出場／不進）穩定度：均值天數 n × 門檻 y；最後一欄為 2015-09 後真實價格 ==")
    out.append(f"{'現行':14s} " + "  ".join(f(r) for r in base) + f"  真實 {f(run(s, e, r2=r2r))}")
    cw = ct = 0
    for n in (120, 250, 500):
        for y in (0.10, 0.125, 0.15, 0.175, 0.20, 0.25):
            kw = dict(entry_ok=ok_hot(y, n), force_exit=exit_hot(y, n))
            rs = [run(a, b, **kw) for a, b in PER.values()]
            rr = run(s, e, r2=r2r, **kw)
            ct += 1
            cw += rs[0]["cagr"] > base[0]["cagr"]
            out.append(f"n={n:3d} y={y:5.1%}   " + "  ".join(f(r) for r in rs) + f"  真實 {f(rr)}")
    out.append(f"全期年化勝過現行：{cw}/{ct}")

    out.append("\n== G. C 類 n=250 y=15% 搭配鄰近進出場均線（現行 vs 加濾網，全期）==")
    for ein in (50, 60, 70):
        for eout in (70, 80, 100):
            a = run(*PER["全期 2002-2026"], ein=ein, eout=eout)
            b = run(*PER["全期 2002-2026"], ein=ein, eout=eout, entry_ok=ok_hot(0.15), force_exit=exit_hot(0.15))
            out.append(f"MA{ein}/MA{eout}: 現行 {f(a)}  加濾網 {f(b)}")

    out.append("\n== H. C 類 n=250 y=15% 逐年差異（加濾網 − 現行）與觸發期間 ==")
    ya = run(*PER["全期 2002-2026"], yearly=True)["yearly"]
    yb = run(*PER["全期 2002-2026"], entry_ok=ok_hot(0.15), force_exit=exit_hot(0.15), yearly=True)["yearly"]
    out.append("  ".join(f"{y}:{yb[y] - ya[y]:+.0%}" for y in sorted(ya) if abs(yb[y] - ya[y]) > 0.005))
    prev, seg = False, []
    for i, d in enumerate(bt.DAYS):
        if bt.WEEK_END[i] and d >= "2002":
            v = ratio_dev(i)
            h = v is not None and v > 0.15
            if h != prev:
                seg.append(("過熱起 " if h else "～") + d)
                prev = h
    out.append(" ".join(seg))

    out.append("\n== 參考：大盤（1x≈0050）買進持有 ==")
    out.append("  ".join(f(bt.run(bt.buyhold(), bt.POS['1x'], bt.POS['1x'], a, b) | {"tpy": 0}) for a, b in PER.values()))

    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究03_融資濾網.txt"), "w", encoding="utf-8").write(txt + "\n")
