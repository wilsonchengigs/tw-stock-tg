"""研究 07：週線 MACD、Donchian 通道突破（海龜）、ADX 趨勢強度

做法來源：
- 海龜：System 1 20 日新高進場／10 日新低出場；System 2 55 日新高進場／20 日新低出場（N=ATR 停損、加碼此處不做）
  https://www.stockopedia.com/content/turtle-trading-rules-trend-following-investing-based-on-20-55-day-highs-58024
- 週線 MACD（12,26,9）DIF 與訊號線交叉、搭配 20 週均線（台股常見看法，玩股網／商周）
- ADX(14) > 25 當趨勢濾網，避免盤整洗單；ADX 從 20 以下升到 25 以上代表新趨勢（SentimenTrader、algolab）

限制：資料只有加權指數收盤價（無高低價）。Donchian 用收盤價新高／新低；ADX 用「每週由日收盤組成的週 K（高=週內最高收盤、低=週內最低收盤）」計算週線 ADX，
另做日線版（用前一日收盤到當日收盤當作 K 棒範圍的近似）。
規則都是週五收盤判斷、下一交易日收盤成交（同 bt.py），2x＝00631L 模擬，出場現金。
用法：python backtest/research_07_週線MACD_通道_ADX.py
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402
import data  # noqa: E402

PER = {"全期": ("1998-01-01", "2026-12-31"), "前段": ("1998-01-01", "2012-12-31"), "後段": ("2013-01-01", "2026-12-31")}
REAL = ("2015-09-01", "2026-12-31")
PX, DAYS, WE = bt.PX, bt.DAYS, bt.WEEK_END
N = len(PX)
_, l1, l2 = data.series()


def real_ret(src, sim):
    px = [src.get(d, (None, None))[1] for d in DAYS]
    out, lp = [0.0], None
    for i in range(1, len(px)):
        out.append(px[i] / lp - 1 if (px[i] and lp) else sim[i])
        if px[i]:
            lp = px[i]
    return out


R2R = real_ret(l2, bt.R2)
M60, M80 = bt.get_sma(60), bt.get_sma(80)


def run(sig, start, end, real=False, yearly=False):
    """sig(i, on) -> bool（週末才呼叫），True=全押 2x"""
    r2 = R2R if real else bt.R2
    i0 = next(i for i, d in enumerate(DAYS) if d >= start)
    i1 = max(i for i, d in enumerate(DAYS) if d <= end)
    eq = peak = 1.0
    mdd, on, pos, pend, trades, ys = 0.0, False, 0.0, None, 0, {}
    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + pos * r2[i] + (1 - pos) * bt.RC
        if pend is not None:
            if pend != pos:
                eq *= 1 - bt.COST * 2 * abs(pend - pos)
                trades += 1
            pos, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        ys[DAYS[i][:4]] = eq
        if WE[i] and i >= 260:
            on = bool(sig(i, on))
            t = 1.0 if on else 0.0
            if t != pos:
                pend = t
    yrs = (i1 - i0) / bt.TD
    res = {"cagr": eq ** (1 / yrs) - 1, "mdd": mdd, "tpy": trades / yrs}
    if yearly:
        prev, yr = 1.0, {}
        for y in sorted(ys):
            yr[y], prev = ys[y] / prev - 1, ys[y]
        res["yearly"] = yr
    return res


def cur(i, on):
    return PX[i] < M80[i] * 0.98 and False or (not (PX[i] < M80[i] * 0.98) if on else PX[i] > M60[i] * 1.01)


# ---------- 週 K ----------
WK_IDX = [i for i in range(N) if WE[i]]          # 每週最後一天的 index
WPOS = {i: k for k, i in enumerate(WK_IDX)}
WC, WH, WL = [], [], []
s = 0
for i in WK_IDX:
    seg = PX[s:i + 1]
    WC.append(PX[i]); WH.append(max(seg)); WL.append(min(seg))
    s = i + 1


def ema(xs, n):
    a, out, e = 2 / (n + 1), [], None
    for x in xs:
        e = x if e is None else e + a * (x - e)
        out.append(e)
    return out


_MACD = {}


def macd(f, sl, sg):
    k = (f, sl, sg)
    if k not in _MACD:
        dif = [a - b for a, b in zip(ema(WC, f), ema(WC, sl))]
        dea = ema(dif, sg)
        _MACD[k] = (dif, dea)
    return _MACD[k]


def wilder(xs, n):
    out, e = [], None
    for k, x in enumerate(xs):
        if k < n:
            out.append(None)
            if k == n - 1:
                e = sum(xs[:n]) / n
                out[-1] = e
            continue
        e = e + (x - e) / n
        out.append(e)
    return out


def adx_from(H, L, C, n):
    tr, pdm, mdm = [0.0], [0.0], [0.0]
    for k in range(1, len(C)):
        tr.append(max(H[k] - L[k], abs(H[k] - C[k - 1]), abs(L[k] - C[k - 1])))
        up, dn = H[k] - H[k - 1], L[k - 1] - L[k]
        pdm.append(up if up > dn and up > 0 else 0.0)
        mdm.append(dn if dn > up and dn > 0 else 0.0)
    st, sp, sm = wilder(tr, n), wilder(pdm, n), wilder(mdm, n)
    pdi, mdi, dx = [], [], []
    for a, b, c in zip(st, sp, sm):
        if a is None or a == 0:
            pdi.append(None); mdi.append(None); dx.append(0.0); continue
        p, m = 100 * b / a, 100 * c / a
        pdi.append(p); mdi.append(m); dx.append(100 * abs(p - m) / (p + m) if p + m else 0.0)
    adx = wilder(dx, n)
    return pdi, mdi, adx


_ADXW, _ADXD = {}, {}


def adx_w(n):
    if n not in _ADXW:
        _ADXW[n] = adx_from(WH, WL, WC, n)
    return _ADXW[n]


def adx_d(n):
    """日線近似：K 棒高低 = max/min(前收, 今收)"""
    if n not in _ADXD:
        H = [PX[0]] + [max(PX[i - 1], PX[i]) for i in range(1, N)]
        L = [PX[0]] + [min(PX[i - 1], PX[i]) for i in range(1, N)]
        _ADXD[n] = adx_from(H, L, PX, n)
    return _ADXD[n]


# ---------- 訊號 ----------
def sig_macd(f, sl, sg, mode):
    dif, dea = macd(f, sl, sg)

    def g(i, on):
        k = WPOS[i]
        if mode == "cross":       # DIF > 訊號線
            return dif[k] > dea[k]
        if mode == "zero":        # DIF > 0（= 週 EMA 黃金交叉）
            return dif[k] > 0
        if mode == "both":        # 進場 DIF>DEA 且 DIF>0；出場 DIF<DEA
            return (dif[k] > dea[k]) if on else (dif[k] > dea[k] and dif[k] > 0)
        if mode == "hyst":        # 進場 DIF>DEA；出場 DIF<0（較慢出場）
            return (dif[k] > 0) if on else (dif[k] > dea[k])
    return g


def rmax(i, n):
    return max(PX[i - n:i])


def rmin(i, n):
    return min(PX[i - n:i])


def sig_don(ne, nx):
    def g(i, on):
        if on:
            return not (PX[i] < rmin(i, nx))
        k = WPOS[i]
        s0 = WK_IDX[k - 1] + 1
        brk = any(PX[j] > rmax(j, ne) for j in range(s0, i + 1))   # 本週任一天創 ne 日收盤新高
        return brk and PX[i] >= rmin(i, nx)
    return g


def sig_cur_adx(n, t, weekly=True, mode="filter"):
    pdi, mdi, adx = adx_w(n) if weekly else adx_d(n)

    def val(i):
        k = WPOS[i] if weekly else i
        return pdi[k], mdi[k], adx[k]

    def g(i, on):
        p, m, a = val(i)
        if a is None or p is None:
            return cur(i, on)
        if mode == "filter":      # 現行＋進場需 ADX>t（出場不變）
            return cur(i, on) if on else (cur(i, on) and a > t)
        if mode == "filter_di":   # 現行＋進場需 ADX>t 且 +DI>-DI
            return cur(i, on) if on else (cur(i, on) and a > t and p > m)
        if mode == "early":       # 現行，另外 ADX>t 且 +DI>-DI 且站上 MA60 提早進場
            return cur(i, on) if on else (cur(i, on) or (a > t and p > m and PX[i] > M60[i]))
        if mode == "exit":        # 現行＋在場時 ADX>t 且 -DI>+DI 提早出場
            return (cur(i, on) and not (a > t and m > p)) if on else cur(i, on)
        if mode == "pure":        # 純 DMI：+DI>-DI 且 ADX>t 進；-DI>+DI 出
            return (p >= m) if on else (p > m and a > t)
    return g


def sig_random_block(prob, seed):
    """對照組：現行進場訊號隨機擋掉 prob 比例的『週』（同 ADX 濾網擋掉的比例）"""
    rng = random.Random(seed)
    blk = {i: rng.random() < prob for i in WK_IDX}

    def g(i, on):
        return cur(i, on) if on else (cur(i, on) and not blk[i])
    return g


def f(r):
    return f"{r['cagr']:6.1%}/{r['mdd']:6.1%}"


ROWS = []


def evaluate(name, sig, base, br):
    rs = [run(sig, a, b) for a, b in PER.values()]
    rr = run(sig, *REAL, real=True)
    win = all(rs[j]["cagr"] > base[j]["cagr"] for j in range(3)) and rr["cagr"] > br["cagr"] and rs[0]["mdd"] > -0.5
    ROWS.append((name, rs, rr, win))
    return (f"{name:34s} " + "  ".join(f(r) for r in rs) + f"  真實 {f(rr)}  年交易 {rs[0]['tpy']:.1f}"
            + ("  ★" if win else ""))


if __name__ == "__main__":
    base = [run(cur, a, b) for a, b in PER.values()]
    br = run(cur, *REAL, real=True)
    out = ["研究 07：週線 MACD／Donchian 通道（海龜）／ADX（格式：年化/最大回檔；全期 前段 後段；真實＝2015-09 後 00631L 真實價格）",
           "★＝三段＋真實都勝現行且全期回檔 < 50%", ""]
    out.append(f"{'現行 MA60×1.01 進／MA80×0.98 出':34s} " + "  ".join(f(r) for r in base) + f"  真實 {f(br)}  年交易 {base[0]['tpy']:.1f}")
    out.append(f"{'大盤 1x 買進持有':34s} " + "  ".join(f(bt.run(bt.buyhold(), bt.POS['1x'], bt.POS['1x'], a, b)) for a, b in PER.values()))
    out.append(f"{'2x 買進持有':34s} " + "  ".join(f(bt.run(bt.buyhold(), bt.POS['2x'], bt.POS['2x'], a, b)) for a, b in PER.values()))

    out.append("\n== A. 週線 MACD（快,慢,訊號）==")
    for fsl in ((6, 13, 5), (8, 17, 9), (12, 26, 9), (16, 35, 9), (24, 52, 9)):
        for mode in ("cross", "zero", "both", "hyst"):
            out.append(evaluate(f"A MACD{fsl} {mode}", sig_macd(*fsl, mode), base, br))

    out.append("\n== B. Donchian 收盤通道：本週創 ne 日新高進場、跌破 nx 日新低出場 ==")
    for ne in (20, 40, 55, 80, 120, 250):
        for nx in (10, 20, 40, 60, 80):
            if nx >= ne and ne > 20:
                continue
            out.append(evaluate(f"B Donchian {ne}/{nx}", sig_don(ne, nx), base, br))

    out.append("\n== C. 現行＋ADX（週線 ADX 用週內收盤高低；日線為近似）==")
    for weekly in (True, False):
        ns = (10, 14, 20) if weekly else (14, 20, 28)
        tag = "週" if weekly else "日"
        for mode in ("filter", "filter_di", "early", "exit"):
            for n in ns:
                for t in (15, 20, 25, 30):
                    out.append(evaluate(f"C {tag}ADX{n} {mode} t={t}", sig_cur_adx(n, t, weekly, mode), base, br))
    out.append("\n== D. 純 DMI（+DI>-DI 且 ADX>t 進場、-DI>+DI 出場）==")
    for weekly in (True, False):
        for n in ((10, 14, 20) if weekly else (14, 20, 28)):
            for t in (15, 20, 25):
                out.append(evaluate(f"D {'週' if weekly else '日'}DMI{n} t={t}", sig_cur_adx(n, t, weekly, "pure"), base, br))

    out.append("\n== 統計（組數／全期勝現行／★）==")
    for p in ("A ", "B ", "C 週ADX", "C 日ADX", "D "):
        rows = [r for r in ROWS if r[0].startswith(p)]
        out.append(f"{p.strip():8s} {len(rows):3d} 組，全期年化勝現行 {sum(r[1][0]['cagr'] > base[0]['cagr'] for r in rows):3d}，"
                   f"全期回檔<50% {sum(r[1][0]['mdd'] > -0.5 for r in rows):3d}，★ {sum(r[3] for r in rows):3d}")
    for p in ("C 週ADX", "C 日ADX"):
        for mode in ("filter", "filter_di", "early", "exit"):
            rows = [r for r in ROWS if r[0].startswith(p) and f" {mode} " in r[0]]
            out.append(f"  {p} {mode:10s} {len(rows)} 組：全期勝 {sum(r[1][0]['cagr'] > base[0]['cagr'] for r in rows)}，★ {sum(r[3] for r in rows)}")

    out.append("\n== ★ 組合 ==")
    wins = [r for r in ROWS if r[3]]
    out += [f"{r[0]}: " + "  ".join(f(x) for x in r[1]) + f"  真實 {f(r[2])}" for r in wins] or ["（無）"]
    out.append("\n全期年化最高 10 組（不論回檔）：")
    for r in sorted(ROWS, key=lambda r: -r[1][0]["cagr"])[:10]:
        out.append(f"  {r[0]}: " + "  ".join(f(x) for x in r[1]) + f"  真實 {f(r[2])}")
    ok = [r for r in ROWS if r[1][0]["mdd"] > -0.5]
    out.append("全期回檔 < 50% 中年化最高 10 組：")
    for r in sorted(ok, key=lambda r: -r[1][0]["cagr"])[:10]:
        out.append(f"  {r[0]}: " + "  ".join(f(x) for x in r[1]) + f"  真實 {f(r[2])}")

    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究07_週線MACD_通道_ADX.txt"), "w", encoding="utf-8").write(txt + "\n")


# ---------- C early 的對照組與鄰近參數 ----------
def sig_early(n, t, weekly=True, use_adx=True, use_di=True, mab=(60, 1.0), gate=None):
    pdi, mdi, adx = adx_w(n) if weekly else adx_d(n)
    mm = bt.get_sma(mab[0])

    def g(i, on):
        if on:
            return cur(i, on)
        k = WPOS[i] if weekly else i
        p, m, a = pdi[k], mdi[k], adx[k]
        if a is None or p is None:
            return cur(i, on)
        c = PX[i] > mm[i] * mab[1]
        if use_adx:
            c = c and a > t
        if use_di:
            c = c and p > m
        if gate is not None:
            c = c and gate[i]
        return cur(i, on) or c
    return g


def controls():
    base = [run(cur, a, b) for a, b in PER.values()]
    br = run(cur, *REAL, real=True)
    out = ["\n== C early 對照組（現行＋『站上 MA60 且 X』提早進場；判斷效果來自 ADX/DMI 還是單純放寬進場）=="]
    out.append(f"{'現行':34s} " + "  ".join(f(r) for r in base) + f"  真實 {f(br)}")
    for nm, sg in (("早進：只要站上 MA60（=×1.00 緩衝）", sig_early(14, 0, use_adx=False, use_di=False)),
                   ("早進：MA60 且週+DI>-DI（無 ADX）", sig_early(14, 0, use_adx=False)),
                   ("早進：MA60 且週ADX14>20（無 DI）", sig_early(14, 20, use_di=False)),
                   ("早進：MA60 且週ADX14>20 且 DI（C）", sig_early(14, 20)),
                   ("早進：MA60×0.99 只要站上", sig_early(14, 0, use_adx=False, use_di=False, mab=(60, 0.99)))):
        out.append(evaluate(nm, sg, base, br))
    # 隨機閘門：與 C 早進條件同樣比例的週數為 True
    pdi, mdi, adx = adx_w(14)
    frac = sum(1 for i in WK_IDX if adx[WPOS[i]] and pdi[WPOS[i]] and adx[WPOS[i]] > 20 and pdi[WPOS[i]] > mdi[WPOS[i]]) / len(WK_IDX)
    res = []
    for seed in range(30):
        rng = random.Random(seed)
        gate = {i: rng.random() < frac for i in range(N)}
        sg = sig_early(14, 0, use_adx=False, use_di=False, gate=gate)
        res.append([run(sg, a, b) for a, b in PER.values()] + [run(sg, *REAL, real=True)])
    med = lambda xs: sorted(xs)[len(xs) // 2]
    out.append(f"隨機閘門 30 次（閘門開啟比例 {frac:.0%}，同 C 的 ADX/DI 條件比例）中位數：" + "  ".join(
        f"{med([r[j]['cagr'] for r in res]):6.1%}/{med([r[j]['mdd'] for r in res]):6.1%}" for j in range(3))
        + f"  真實 {med([r[3]['cagr'] for r in res]):6.1%}/{med([r[3]['mdd'] for r in res]):6.1%}"
        + f"；全期勝現行 {sum(r[0]['cagr'] > base[0]['cagr'] for r in res)}/30")

    out.append("\n== C early 鄰近參數：早進均線 × 緩衝（週 ADX14 t=20 且 +DI>-DI）==")
    for ma in (40, 50, 60, 70, 80):
        for b in (0.99, 1.0, 1.01):
            out.append(evaluate(f"早進 MA{ma}×{b} 週ADX14>20+DI", sig_early(14, 20, mab=(ma, b)), base, br))
    rows = [r for r in ROWS if r[0].startswith("早進 MA")]
    out.append(f"鄰近 {len(rows)} 組：全期勝現行 {sum(r[1][0]['cagr'] > base[0]['cagr'] for r in rows)}，★ {sum(r[3] for r in rows)}，"
               f"回檔<50% {sum(r[1][0]['mdd'] > -0.5 for r in rows)}")

    out.append("\n== 逐年差異（變體 − 現行，只列差 > 1%）==")
    ya = run(cur, *PER["全期"], yearly=True)["yearly"]
    for nm, sg in (("C 週ADX14>20 早進", sig_early(14, 20)), ("只要站上 MA60 早進", sig_early(14, 0, use_adx=False, use_di=False)),
                   ("MA60 且 +DI>-DI 早進", sig_early(14, 0, use_adx=False))):
        yb = run(sg, *PER["全期"], yearly=True)["yearly"]
        out.append(nm + ": " + "  ".join(f"{y}:{yb[y] - ya[y]:+.0%}" for y in sorted(ya) if abs(yb[y] - ya[y]) > 0.01))
    return out


if __name__ == "__main__":
    extra = "\n".join(controls())
    print(extra)
    open(os.path.join(HERE, "結果_研究07_週線MACD_通道_ADX.txt"), "a", encoding="utf-8").write(extra + "\n")
