"""研究 06：季節性（Sell in May／萬聖節效應、九月效應）對現行策略有沒有額外效果

做法來源：Bouman & Jacobsen (2002) 37 國中 36 國 11～4 月報酬高於 5～10 月；
Schroders：MSCI 台灣 1990–2016 年 5～10 月中位數 -6.0%，27 年只有 10 年上漲；
台灣媒體統計 12 月最強、9 月最弱（2015–2024）。

測試（週五判斷、下一交易日收盤成交，同 bt.py）：
0  逐月統計：加權指數各月平均報酬／上漲機率，前後兩段分開看是否穩定
A  純季節：強勢期持 2x（或 1x）、弱勢期現金（不看均線）
B  現行＋弱勢期不新進場（已在場照常用 MA80 出場）
C  現行＋弱勢期也強制出場（弱勢期一律現金）
D  現行＋弱勢期在場只用 1.5x／1x
E  現行＋弱勢期出場線收緊（MA80×0.98 → MA60×0.99）
F  現行＋強勢期進場放寬（MA60×1.01 → MA60×0.99）
弱勢期視窗：起始月 4～7 × 結束月 8～11（鄰近穩定度），另測單獨 9 月
用法：python backtest/research_06_季節性.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402
import data  # noqa: E402

PER = {"全期 1998-2026": ("1998-01-01", "2026-12-31"), "前段 1998-2012": ("1998-01-01", "2012-12-31"),
       "後段 2013-2026": ("2013-01-01", "2026-12-31")}
REAL = ("2015-09-01", "2026-12-31")
PX, DAYS = bt.PX, bt.DAYS
MON = [int(d[5:7]) for d in DAYS]

_, l1, l2 = data.series()


def real_ret(src, sim):
    px = [src.get(d, (None, None))[1] for d in DAYS]
    out, lp = [0.0], None
    for i in range(1, len(px)):
        out.append(px[i] / lp - 1 if (px[i] and lp) else sim[i])
        if px[i]:
            lp = px[i]
    return out


R1R, R2R = real_ret(l1, bt.R1), real_ret(l2, bt.R2)


def w_of(lev):
    return (0.0, lev) if lev <= 1 else (lev - 1, 2 - lev)


def weak(m0, m1):
    """弱勢期：m0 月～m1 月（含）"""
    s = set(range(m0, m1 + 1))
    return lambda i: MON[i] in s


def run(start, end, weak_f=None, mode=None, lev_weak=2.0, real=False, yearly=False, pure=None, fbuf=0.99):
    r1, r2 = (R1R, R2R) if real else (bt.R1, bt.R2)
    m60, m80 = bt.get_sma(60), bt.get_sma(80)
    i0 = next(i for i, d in enumerate(DAYS) if d >= start)
    i1 = max(i for i, d in enumerate(DAYS) if d <= end)
    eq = peak = 1.0
    mdd, on, pos, pend, trades, ys, expo = 0.0, False, (0.0, 0.0), None, 0, {}, 0.0
    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + pos[0] * r2[i] + pos[1] * r1[i] + (1 - pos[0] - pos[1]) * bt.RC
            expo += pos[0] * 2 + pos[1]
        if pend is not None:
            to = abs(pend[0] - pos[0]) * 2 + abs(pend[1] - pos[1])
            if to > 0:
                eq *= 1 - bt.COST * to
                trades += 1
            pos, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        ys[DAYS[i][:4]] = eq
        if not bt.WEEK_END[i] or not m80[i]:
            continue
        p, wk = PX[i], (weak_f(i) if weak_f else False)
        if pure is not None:
            lev = 0.0 if wk else pure
        else:
            if not on:
                go = p > m60[i] * (fbuf if (mode == "F" and not wk) else 1.01)
                if wk and mode == "B":
                    go = False
                on = go
            else:
                if wk and mode == "E":
                    on = not (p < m60[i] * 0.99)
                else:
                    on = not (p < m80[i] * 0.98)
            if wk and mode == "C":
                on = False
            lev = (lev_weak if (wk and mode == "D") else 2.0) if on else 0.0
        tgt = w_of(lev)
        if tgt != pos:
            pend = tgt
    yrs = (i1 - i0) / bt.TD
    res = {"cagr": eq ** (1 / yrs) - 1, "mdd": mdd, "tpy": trades / yrs, "exp": expo / max(i1 - i0, 1)}
    if yearly:
        prev, yr = 1.0, {}
        for y in sorted(ys):
            yr[y] = ys[y] / prev - 1
            prev = ys[y]
        res["yearly"] = yr
    return res


def f(r):
    return f"{r['cagr']:6.1%}/{r['mdd']:6.1%}"


def month_stats():
    out = ["== 0. 加權指數（含 3% 配息）各月報酬：平均／上漲機率 =="]
    me = {}
    for i, d in enumerate(DAYS):
        me[d[:7]] = i
    keys = sorted(me)
    rows = {m: {"a": [], "b": []} for m in range(1, 13)}
    for k0, k1 in zip(keys, keys[1:]):
        r = PX[me[k1]] / PX[me[k0]] - 1 + 0.0025
        y, m = int(k1[:4]), int(k1[5:7])
        if y < 1998:
            continue
        rows[m]["a" if y <= 2012 else "b"].append(r)
    out.append("月   1998-2012 平均/上漲率   2013-2026 平均/上漲率   全期")
    for m in range(1, 13):
        a, b = rows[m]["a"], rows[m]["b"]
        al = a + b
        g = lambda xs: f"{sum(xs) / len(xs):+5.1%}/{sum(x > 0 for x in xs) / len(xs):4.0%}"
        out.append(f"{m:2d}月   {g(a)}            {g(b)}            {g(al)}")
    # 5–10 vs 11–4 累計
    for nm, lo, hi in (("1998-2012", 1998, 2012), ("2013-2026", 2013, 2026)):
        s = w = 1.0
        for k0, k1 in zip(keys, keys[1:]):
            y, m = int(k1[:4]), int(k1[5:7])
            if lo <= y <= hi:
                r = PX[me[k1]] / PX[me[k0]]
                if 5 <= m <= 10:
                    s *= r
                else:
                    w *= r
        n = hi - lo + 1
        out.append(f"{nm}：5～10 月年均 {s ** (1 / n) - 1:+.1%}，11～4 月年均 {w ** (1 / n) - 1:+.1%}（不含息）")
    return out


if __name__ == "__main__":
    out = ["研究 06：季節性（格式：年化/最大回檔；真實＝2015-09 後 0050／00631L 真實價格）", ""]
    out += month_stats()
    base = [run(a, b) for a, b in PER.values()]
    br = run(*REAL, real=True)
    out.append(f"\n{'現行':30s} " + "  ".join(f(r) for r in base) + f"  真實 {f(br)}  年交易 {base[0]['tpy']:.1f}")
    out.append("大盤 1x 買進持有              " + "  ".join(
        f(bt.run(bt.buyhold(), bt.POS['1x'], bt.POS['1x'], a, b)) for a, b in PER.values()))
    allrows = []

    def line(name, kw):
        rs = [run(a, b, **kw) for a, b in PER.values()]
        rr = run(*REAL, real=True, **kw)
        win = all(rs[j]["cagr"] > base[j]["cagr"] for j in range(3)) and rr["cagr"] > br["cagr"]
        allrows.append((name, rs, rr, win))
        return (f"{name:30s} " + "  ".join(f(r) for r in rs) + f"  真實 {f(rr)}  年交易 {rs[0]['tpy']:.1f}"
                + ("  ★三段+真實都勝" if win else ""))

    out.append("\n== A. 純季節（不看均線）：強勢期持有、弱勢期現金 ==")
    for lv in (2.0, 1.0):
        for m0, m1 in ((5, 10), (6, 10), (5, 9), (8, 10)):
            out.append(line(f"A {lv:.0f}x 弱勢 {m0}-{m1} 月", dict(weak_f=weak(m0, m1), pure=lv)))
        out.append(line(f"A {lv:.0f}x 全年持有", dict(weak_f=lambda i: False, pure=lv)))

    windows = [(m0, m1) for m0 in (4, 5, 6, 7) for m1 in (8, 9, 10, 11) if m1 > m0] + [(9, 9), (8, 9), (9, 10)]
    titles = {"B": "現行＋弱勢期不新進場", "C": "現行＋弱勢期強制出場（現金）", "E": "現行＋弱勢期出場線收緊為 MA60×0.99",
              "F": "現行＋強勢期進場放寬為 MA60×0.99"}
    for mode in ("B", "C", "E", "F"):
        out.append(f"\n== {mode}. {titles[mode]}（弱勢期 起-迄月）==")
        for m0, m1 in windows:
            out.append(line(f"{mode} {m0}-{m1} 月", dict(weak_f=weak(m0, m1), mode=mode)))
    out.append("\n== D. 現行＋弱勢期在場降槓桿 ==")
    for lv in (1.5, 1.0):
        for m0, m1 in ((5, 10), (6, 10), (5, 9), (8, 10), (9, 9)):
            out.append(line(f"D {lv}x {m0}-{m1} 月", dict(weak_f=weak(m0, m1), mode="D", lev_weak=lv)))

    out.append("\n== 統計 ==")
    for mode in ("B", "C", "D", "E", "F"):
        rows = [r for r in allrows if r[0].startswith(mode + " ")]
        better = sum(r[1][0]["cagr"] > base[0]["cagr"] for r in rows)
        win = sum(r[3] for r in rows)
        ok = sum(r[1][0]["mdd"] > -0.5 for r in rows)
        out.append(f"{mode}：{len(rows)} 組，全期年化勝現行 {better}，三段＋真實都勝 {win}，全期回檔 < 50% {ok}")
    out.append("\n== 三段＋真實價格都勝過現行的組合 ==")
    wins = [r for r in allrows if r[3]]
    out += [f"{r[0]}: " + "  ".join(f(x) for x in r[1]) + f"  真實 {f(r[2])}" for r in wins] or ["（無）"]

    out.append("\n== 逐年差異（變體 − 現行，只列差 > 1%）==")
    ya = run(*PER["全期 1998-2026"], yearly=True)["yearly"]
    best = sorted(allrows, key=lambda r: -r[1][0]["cagr"])[:4]
    reps = {"C 5-10 月": dict(weak_f=weak(5, 10), mode="C"), "B 5-10 月": dict(weak_f=weak(5, 10), mode="B"),
            "E 5-10 月": dict(weak_f=weak(5, 10), mode="E"), "C 9-9 月": dict(weak_f=weak(9, 9), mode="C")}
    for nm, kw in reps.items():
        yb = run(*PER["全期 1998-2026"], yearly=True, **kw)["yearly"]
        out.append(nm + ": " + "  ".join(f"{y}:{yb[y] - ya[y]:+.0%}" for y in sorted(ya) if abs(yb[y] - ya[y]) > 0.01))
    out.append("\n全期年化最高 4 組：" + "；".join(f"{r[0]} {f(r[1][0])}" for r in best))

    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究06_季節性.txt"), "w", encoding="utf-8").write(txt + "\n")


def control():
    """F 類對照：放寬進場若全年都用、或只在『強勢期以外』用，是否一樣好？→ 判斷是季節還是緩衝效果"""
    out = ["\n== F 類對照組（判斷是季節效果還是單純進場緩衝放寬）=="]
    base = [run(a, b) for a, b in PER.values()]
    br = run(*REAL, real=True)
    out.append(f"{'現行（進場 MA60×1.01）':34s} " + "  ".join(f(r) for r in base) + f"  真實 {f(br)}")
    never = lambda i: False
    always = lambda i: True
    rows = []
    for b in (0.99, 1.0, 1.005):
        rows += [(f"b={b} 全年放寬（不分季節）", dict(weak_f=never, mode="F", fbuf=b)),
                 (f"b={b} 只在 5-10 月放寬（反向）", dict(weak_f=lambda i: not (5 <= MON[i] <= 10), mode="F", fbuf=b)),
                 (f"b={b} 只在 11-4 月放寬（F 5-10）", dict(weak_f=weak(5, 10), mode="F", fbuf=b)),
                 (f"b={b} 對照：單數月放寬", dict(weak_f=lambda i: MON[i] % 2 == 0, mode="F", fbuf=b)),
                 (f"b={b} 對照：雙數月放寬", dict(weak_f=lambda i: MON[i] % 2 == 1, mode="F", fbuf=b))]
    rows.append(("全年不放寬（=現行）", dict(weak_f=always, mode="F")))
    for nm, kw in rows:
        rs = [run(a, b, **kw) for a, b in PER.values()]
        rr = run(*REAL, real=True, **kw)
        out.append(f"{nm:34s} " + "  ".join(f(r) for r in rs) + f"  真實 {f(rr)}  年交易 {rs[0]['tpy']:.1f}")
    out.append("（全年放寬也等於研究『進場緩衝 −1%』；先前單一均線掃描已看過不同緩衝，見 結果_參數排名.txt）")
    return out


if __name__ == "__main__":
    extra = "\n".join(control())
    print(extra)
    open(os.path.join(HERE, "結果_研究06_季節性.txt"), "a", encoding="utf-8").write(extra + "\n")


def fbuf_sweep():
    out = ["\n== F 類緩衝掃描：強勢期（非 5-10 月）進場 MA60×b，弱勢期維持 ×1.01 =="]
    base = [run(a, b) for a, b in PER.values()]
    for b in (0.98, 0.99, 0.995, 1.0, 1.005):
        for m0, m1 in ((5, 10), (6, 9)):
            kw = dict(weak_f=weak(m0, m1), mode="F", fbuf=b)
            rs = [run(a, c, **kw) for a, c in PER.values()]
            rr = run(*REAL, real=True, **kw)
            out.append(f"b={b:.3f} 弱勢 {m0}-{m1}    " + "  ".join(f(r) for r in rs) + f"  真實 {f(rr)}")
    ya = run(*PER["全期 1998-2026"], yearly=True)["yearly"]
    yb = run(*PER["全期 1998-2026"], yearly=True, weak_f=weak(5, 10), mode="F")["yearly"]
    out.append("逐年差異 F 5-10 b=0.99: " + "  ".join(f"{y}:{yb[y] - ya[y]:+.0%}" for y in sorted(ya) if abs(yb[y] - ya[y]) > 0.01))
    return out


if __name__ == "__main__":
    extra = "\n".join(fbuf_sweep())
    print(extra)
    open(os.path.join(HERE, "結果_研究06_季節性.txt"), "a", encoding="utf-8").write(extra + "\n")
