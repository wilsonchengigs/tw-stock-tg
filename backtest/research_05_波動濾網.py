"""研究 05：台指 VIX／實現波動 regime 當現行策略的濾網或降槓桿條件

資料：
- 台指 VIX（期交所 VIXTWN，2001-12-24～）：公開倉庫 salmonmisosoup/leverage-dashboard 的 data/vixtwn.csv
  （雲端擋期交所，只能用鏡像）。VIX 是當天收盤後就有的數字，週五判斷、下一交易日收盤成交，不會偷看。
- 實現波動：加權指數 n 日報酬年化標準差（1998 起都能算）

測試：
A 高波動不進場（延後進場）        B 高波動也強制出場
C 高波動時只用 1.5x（在場時）      D 高波動時只用 1x
E VIX 相對自己 250 日均值過高 → 不進／出場
F VIX 恐慌反轉提早進場（VIX 曾 > x 且回落到 5 日均線下、指數站上 20 日線）
G 波動目標：在場時槓桿 = min(2, 目標波動 / 實現波動)，變動超過 0.25 才調整

三段：實現波動版 1998–2026／1998–2012／2013–2026；VIX 版 2002–2026／2002–2012／2013–2026。
用法：python backtest/research_05_波動濾網.py [vixtwn.csv 路徑]
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

URL = "https://raw.githubusercontent.com/salmonmisosoup/leverage-dashboard/HEAD/data/vixtwn.csv"
PER98 = {"全期 1998-2026": ("1998-01-01", "2026-12-31"), "前段 1998-2012": ("1998-01-01", "2012-12-31"),
         "後段 2013-2026": ("2013-01-01", "2026-12-31")}
PER02 = {"全期 2002-2026": ("2002-01-01", "2026-12-31"), "前段 2002-2012": ("2002-01-01", "2012-12-31"),
         "後段 2013-2026": ("2013-01-01", "2026-12-31")}
REAL = ("2015-09-01", "2026-12-31")
PX = bt.PX


def load_vix():
    if len(sys.argv) > 1:
        txt = open(sys.argv[1], encoding="utf-8").read()
    else:
        txt = urllib.request.urlopen(URL, timeout=60).read().decode("utf-8")
    m = {r["date"]: float(r["vix"]) for r in csv.DictReader(io.StringIO(txt)) if r["vix"]}
    out, last = [], None
    for d in bt.DAYS:
        last = m.get(d, last)
        out.append(last)
    return out, min(m), max(m)


VIX, VIX0, VIX1 = load_vix()
LR = [0.0] + [math.log(PX[i] / PX[i - 1]) for i in range(1, len(PX))]


def rv(n):
    out = [None] * len(PX)
    for i in range(n, len(PX)):
        xs = LR[i - n + 1:i + 1]
        m = sum(xs) / n
        out[i] = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1) * bt.TD) * 100
    return out


RV = {n: rv(n) for n in (20, 60)}


def mean_arr(arr, n):
    out = [None] * len(arr)
    for i in range(n - 1, len(arr)):
        xs = arr[i - n + 1:i + 1]
        if all(x is not None for x in xs):
            out[i] = sum(xs) / n
    return out


VIX_M250 = mean_arr(VIX, 250)
VIX_M5 = mean_arr(VIX, 5)

# 真實價格報酬（2015-09 之後；之前用模擬）
_, l1, l2 = data.series()


def real_ret(src, sim):
    px = [src.get(d, (None, None))[1] for d in bt.DAYS]
    out, lp = [0.0], None
    for i in range(1, len(px)):
        if px[i] and lp:
            out.append(px[i] / lp - 1)
        else:
            out.append(sim[i])
        if px[i]:
            lp = px[i]
    return out


R1R, R2R = real_ret(l1, bt.R1), real_ret(l2, bt.R2)


def w_of(lev):
    if lev <= 1:
        return (0.0, lev)
    return (lev - 1, 2 - lev)


def run(start, end, entry_ok=None, force_exit=None, early_entry=None, lev_on=None, ein=60, eout=80,
        bin_=0.01, bout=0.02, real=False, yearly=False, min_step=0.0):
    """現行規則；lev_on(i) 給在場時的槓桿（預設 2）"""
    r1, r2 = (R1R, R2R) if real else (bt.R1, bt.R2)
    mi, mo = bt.get_sma(ein), bt.get_sma(eout)
    i0 = next(i for i, d in enumerate(bt.DAYS) if d >= start)
    i1 = max(i for i, d in enumerate(bt.DAYS) if d <= end)
    eq = peak = 1.0
    mdd, on, pos, pend, trades = 0.0, False, (0.0, 0.0), None, 0
    ys, exp_days, n_days = {}, 0.0, 0
    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + pos[0] * r2[i] + pos[1] * r1[i] + (1 - pos[0] - pos[1]) * bt.RC
            exp_days += pos[0] * 2 + pos[1]
            n_days += 1
        if pend is not None:
            to = abs(pend[0] - pos[0]) * 2 + abs(pend[1] - pos[1])
            if to > 0:
                eq *= 1 - bt.COST * to
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
            lev = (lev_on(i) if lev_on else 2.0) if on else 0.0
            cur = pos[0] * 2 + pos[1]
            if (lev == 0) != (cur == 0) or abs(lev - cur) > min_step + 1e-9:
                tgt = w_of(lev)
                if tgt != pos:
                    pend = tgt
    yrs = (i1 - i0) / bt.TD
    res = {"cagr": eq ** (1 / yrs) - 1, "mdd": mdd, "tpy": trades / yrs, "exp": exp_days / max(n_days, 1)}
    if yearly:
        prev, yr = 1.0, {}
        for y in sorted(ys):
            yr[y] = ys[y] / prev - 1
            prev = ys[y]
        res["yearly"] = yr
    return res


def f(r):
    return f"{r['cagr']:6.1%}/{r['mdd']:6.1%}"


def vol_of(kind):
    return VIX if kind == "VIX" else RV[int(kind[2:])]


def hi(kind, x):
    a = vol_of(kind)
    return lambda i: a[i] is not None and a[i] > x


def lo(kind, x):
    a = vol_of(kind)
    return lambda i: a[i] is None or a[i] <= x


def vix_rel_hi(y):
    return lambda i: VIX_M250[i] is not None and VIX[i] > VIX_M250[i] * (1 + y)


def vix_rel_ok(y):
    h = vix_rel_hi(y)
    return lambda i: not h(i)


def panic_reversal(x, look=20, ma=20):
    m = bt.get_sma(ma)

    def g(i):
        if VIX_M5[i] is None or m[i] is None:
            return False
        peak = max((v for v in VIX[i - look + 1:i + 1] if v is not None), default=0)
        return peak > x and VIX[i] < VIX_M5[i] and PX[i] > m[i]
    return g


def voltarget(tgt, n=20, cap=2.0):
    a = RV[n]
    return lambda i: cap if not a[i] else max(1.0, min(cap, round(tgt / a[i] * 4) / 4))


if __name__ == "__main__":
    out = ["研究 05：台指 VIX／實現波動 regime（格式：年化/最大回檔；『曝險』為平均曝險倍數）",
           f"台指 VIX 資料 {VIX0}～{VIX1}（期交所 2006 年才正式編製，之前為回推值）", ""]
    allrows = []

    def block(title, per, variants, tag):
        out.append(f"\n== {title} ==")
        base = [run(a, b) for a, b in per.values()]
        br = run(*REAL, real=True)
        out.append(f"{'現行':26s} " + "  ".join(f(r) for r in base) + f"  真實 {f(br)}  曝險 {base[0]['exp']:.2f}")
        for name, kw in variants:
            rs = [run(a, b, **kw) for a, b in per.values()]
            rr = run(*REAL, real=True, **kw)
            win = all(rs[j]["cagr"] > base[j]["cagr"] for j in range(3)) and rr["cagr"] > br["cagr"]
            out.append(f"{name:26s} " + "  ".join(f(r) for r in rs) + f"  真實 {f(rr)}  曝險 {rs[0]['exp']:.2f}"
                       + ("  ★三段+真實都勝" if win else ""))
            allrows.append((tag, name, rs, rr, base, br, win))

    vix_x = (20, 25, 30, 35, 40)
    rv_x = {"RV20": (15, 20, 25, 30, 35), "RV60": (15, 20, 25, 30)}

    block("A. 台指 VIX > x 不進場", PER02, [(f"VIX>{x}", dict(entry_ok=lo("VIX", x))) for x in vix_x], "A-VIX")
    for k, xs in rv_x.items():
        block(f"A. {k} > x 不進場", PER98, [(f"{k}>{x}", dict(entry_ok=lo(k, x))) for x in xs], f"A-{k}")
    block("B. 台指 VIX > x 不進、在場也出場", PER02,
          [(f"VIX>{x}", dict(entry_ok=lo("VIX", x), force_exit=hi("VIX", x))) for x in vix_x], "B-VIX")
    for k, xs in rv_x.items():
        block(f"B. {k} > x 不進、在場也出場", PER98,
              [(f"{k}>{x}", dict(entry_ok=lo(k, x), force_exit=hi(k, x))) for x in xs], f"B-{k}")
    for lv, tag in ((1.5, "C"), (1.0, "D")):
        block(f"{tag}. 台指 VIX > x 時在場只用 {lv}x", PER02,
              [(f"VIX>{x}", dict(lev_on=(lambda h, lv=lv: lambda i: lv if h(i) else 2.0)(hi("VIX", x))))
               for x in vix_x], f"{tag}-VIX")
        for k, xs in rv_x.items():
            block(f"{tag}. {k} > x 時在場只用 {lv}x", PER98,
                  [(f"{k}>{x}", dict(lev_on=(lambda h, lv=lv: lambda i: lv if h(i) else 2.0)(hi(k, x))))
                   for x in xs], f"{tag}-{k}")
    block("E. 台指 VIX 高於自己 250 日均值 y 以上：不進／出場", PER02,
          [(f"y={y:.0%} 只擋進場", dict(entry_ok=vix_rel_ok(y))) for y in (0.2, 0.4, 0.6)]
          + [(f"y={y:.0%} 也出場", dict(entry_ok=vix_rel_ok(y), force_exit=vix_rel_hi(y))) for y in (0.2, 0.4, 0.6)],
          "E")
    block("F. VIX 恐慌反轉提早進場（近 20 日 VIX 曾 > x、回落到 5 日均線下、指數 > MA20）", PER02,
          [(f"x={x}", dict(early_entry=panic_reversal(x))) for x in (30, 35, 40, 45)], "F")
    block("G. 波動目標：在場槓桿 = clip(目標 / RV20, 1, 2)，0.25 一格，變動 > 0.25 才調整", PER98,
          [(f"目標 {t}%", dict(lev_on=voltarget(t), min_step=0.25)) for t in (20, 25, 30, 35, 40)], "G")
    block("G2. 同上但用 RV60", PER98,
          [(f"目標 {t}%", dict(lev_on=voltarget(t, 60), min_step=0.25)) for t in (20, 25, 30, 35, 40)], "G2")

    out.append("\n== 三段＋真實價格都勝過現行的組合 ==")
    wins = [r for r in allrows if r[6]]
    for r in wins:
        out.append(f"{r[0]} {r[1]}: " + "  ".join(f(x) for x in r[2]) + f"  真實 {f(r[3])}")
    if not wins:
        out.append("（無）")
    out.append("\n== 全期年化較高且全期回檔較淺的組合 ==")
    for r in allrows:
        if r[2][0]["cagr"] > r[4][0]["cagr"] and r[2][0]["mdd"] > r[4][0]["mdd"]:
            out.append(f"{r[0]} {r[1]}: 全期 {f(r[2][0])} vs 現行 {f(r[4][0])}  後段 {f(r[2][2])} vs {f(r[4][2])}"
                       f"  真實 {f(r[3])} vs {f(r[5])}")

    # 逐年差異：挑幾個代表
    out.append("\n== 逐年差異（變體 − 現行，只列差 > 0.5%）==")
    reps = [("C VIX>30 用1.5x", PER02, dict(lev_on=(lambda h: lambda i: 1.5 if h(i) else 2.0)(hi("VIX", 30)))),
            ("C RV20>25 用1.5x", PER98, dict(lev_on=(lambda h: lambda i: 1.5 if h(i) else 2.0)(hi("RV20", 25)))),
            ("G 目標30% RV20", PER98, dict(lev_on=voltarget(30), min_step=0.25)),
            ("A VIX>30 不進", PER02, dict(entry_ok=lo("VIX", 30)))]
    for nm, per, kw in reps:
        a, b = list(per.values())[0]
        ya = run(a, b, yearly=True)["yearly"]
        yb = run(a, b, yearly=True, **kw)["yearly"]
        out.append(nm + ": " + "  ".join(f"{y}:{yb[y] - ya[y]:+.0%}" for y in sorted(ya) if abs(yb[y] - ya[y]) > 0.005))

    out.append("\n== 參考：大盤（1x≈0050）買進持有 ==")
    for per in (PER98, PER02):
        out.append("  ".join(f"{k} {f(bt.run(bt.buyhold(), bt.POS['1x'], bt.POS['1x'], a, b))}" for k, (a, b) in per.items()))

    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究05_波動濾網.txt"), "w", encoding="utf-8").write(txt + "\n")


def f_robust():
    """F 類穩定度：門檻 x × 回顧 look × 確認均線 ma，與逐年差異"""
    out = ["\n== F 類穩定度：x（VIX 門檻）× look（回顧天數）× ma（指數確認均線）；最後一欄真實價格 =="]
    base = [run(a, b) for a, b in PER02.values()]
    br = run(*REAL, real=True)
    out.append(f"{'現行':22s} " + "  ".join(f(r) for r in base) + f"  真實 {f(br)}")
    n = w = ok = 0
    for x in (30, 35, 40, 45, 50):
        for look in (10, 20, 40):
            for ma in (10, 20, 40):
                kw = dict(early_entry=panic_reversal(x, look, ma))
                rs = [run(a, b, **kw) for a, b in PER02.values()]
                rr = run(*REAL, real=True, **kw)
                win = all(rs[j]["cagr"] > base[j]["cagr"] for j in range(3)) and rr["cagr"] > br["cagr"]
                n += 1
                w += win
                ok += rs[0]["mdd"] > -0.5
                out.append(f"x={x} look={look:2d} ma={ma:2d}    " + "  ".join(f(r) for r in rs) + f"  真實 {f(rr)}"
                           + ("  ★" if win else ""))
    out.append(f"三段＋真實都勝：{w}/{n}；全期回檔 < 50%：{ok}/{n}")
    ya = run(*PER02["全期 2002-2026"], yearly=True)["yearly"]
    for x in (35, 40, 45):
        yb = run(*PER02["全期 2002-2026"], yearly=True, early_entry=panic_reversal(x))["yearly"]
        out.append(f"逐年差異 x={x}: " + "  ".join(f"{y}:{yb[y] - ya[y]:+.0%}" for y in sorted(ya) if abs(yb[y] - ya[y]) > 0.005))
    return out


if __name__ == "__main__":
    extra = "\n".join(f_robust())
    print(extra)
    open(os.path.join(HERE, "結果_研究05_波動濾網.txt"), "a", encoding="utf-8").write(extra + "\n")
