"""研究 17：滾動最佳化（walk-forward）

問題：現行參數（MA60x1.01 進／MA80x0.98 出）是用 1998–2026 全部資料挑的，有「看過答案」的嫌疑。
做法：每年初只用「過去 n 年」資料，在格點中挑一組（目標：年化最高，或年化/回檔比最高，限回檔 < 50%），
套用到當年；串起來就是不偷看未來的樣本外績效。跟固定現行參數比較。
格點：進場 MA40～100 × (1.00, 1.01, 1.02)、出場 MA60～150 × (0.97, 0.98, 0.99)
用法：python -X utf8 backtest/research_17_滾動最佳化.py
"""
import itertools
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402

PX, DAYS, WE = bt.PX, bt.DAYS, bt.WEEK_END
N = len(PX)
GRID = [(a, b, c, d) for a, b, c, d in itertools.product((40, 50, 60, 70, 80, 100), (1.0, 1.01, 1.02),
                                                         (60, 70, 80, 90, 100, 120, 150), (0.97, 0.98, 0.99)) if c >= a]
YEARS = sorted({d[:4] for d in DAYS})
YI = {y: (DAYS.index(next(d for d in DAYS if d[:4] == y)), max(i for i, d in enumerate(DAYS) if d[:4] == y)) for y in YEARS}


def signal(p):
    ein, bi, eo, bo = p
    mi, mo = bt.get_sma(ein), bt.get_sma(eo)
    st, out = False, []
    for i in range(N):
        if WE[i] and i >= 260:
            st = (not PX[i] < mo[i] * bo) if st else (PX[i] > mi[i] * bi)
        out.append(st)
    return out


SIG = {p: signal(p) for p in GRID}


def daily_eq(sig):
    """整段每日淨值（週五訊號、隔天成交）"""
    eq, pos, pend, out = 1.0, False, None, [1.0]
    for i in range(1, N):
        eq *= 1 + (bt.R2[i] if pos else bt.RC)
        if pend is not None:
            eq *= 1 - bt.COST * 2
            pos, pend = pend, None
        if WE[i] and sig[i] != pos:
            pend = sig[i]
        out.append(eq)
    return out


EQ = {p: daily_eq(s) for p, s in SIG.items()}


def stats(eq, i0, i1):
    peak, mdd = eq[i0], 0.0
    for i in range(i0, i1 + 1):
        peak = max(peak, eq[i])
        mdd = min(mdd, eq[i] / peak - 1)
    yrs = (i1 - i0) / bt.TD
    return (eq[i1] / eq[i0]) ** (1 / yrs) - 1, mdd


def walk(lookback, objective):
    """回傳每年用的參數與串接後的淨值序列（每年換參數時若部位不同，收一次換手成本）"""
    chosen, seq = {}, []
    for y in YEARS:
        if int(y) < 1998 + lookback:
            continue
        i0 = YI[str(int(y) - lookback)][0] if str(int(y) - lookback) in YI else 260
        i0 = max(i0, 260)
        i1 = YI[y][0] - 1
        best, bv = None, -9
        for p in GRID:
            c, m = stats(EQ[p], i0, i1)
            if m < -0.5:
                continue
            v = c if objective == "cagr" else c / abs(m) if m else c
            if v > bv:
                best, bv = p, v
        chosen[y] = best
    eq, prev_pos = 1.0, None
    peak, mdd, series = 1.0, 0.0, {}
    for y, p in chosen.items():
        a, b = YI[y]
        e = EQ[p]
        pos_now = SIG[p][a - 1]
        if prev_pos is not None and pos_now != prev_pos:
            eq *= 1 - bt.COST * 2
        for i in range(a, b + 1):
            eq *= e[i] / e[i - 1]
            peak = max(peak, eq)
            mdd = min(mdd, eq / peak - 1)
        series[y] = eq
        prev_pos = SIG[p][b]
    return chosen, series, mdd


def cagr_from(series, y0, y1):
    ys = [y for y in series if y0 <= y <= y1]
    if not ys:
        return None
    start = series.get(str(int(ys[0]) - 1), 1.0)
    return (series[ys[-1]] / start) ** (1 / len(ys)) - 1


def main():
    L = ["研究 17：滾動最佳化（每年初用過去 n 年挑參數，套用當年；樣本外）", f"格點 {len(GRID)} 組"]
    cur = (60, 1.01, 80, 0.98)
    for lb in (5, 8, 10, 15):
        for obj, on in (("cagr", "年化最高"), ("ratio", "年化/回檔最高")):
            chosen, series, mdd = walk(lb, obj)
            y0 = min(series)
            fixed = {}
            e = EQ[cur]
            base = e[YI[y0][0] - 1]
            peak, fm = 1.0, 0.0
            for y in series:
                a, b = YI[y]
                for i in range(a, b + 1):
                    v = e[i] / base
                    peak = max(peak, v)
                    fm = min(fm, v / peak - 1)
                fixed[y] = e[b] / base
            c_w = cagr_from(series, y0, "2026")
            c_f = cagr_from(fixed, y0, "2026")
            c_w2 = cagr_from(series, "2013", "2026")
            c_f2 = cagr_from(fixed, "2013", "2026")
            L.append(f"\n回顧 {lb} 年、{on}：{y0}～2026 滾動 {c_w:.1%}／{mdd:.1%}  vs 固定現行 {c_f:.1%}／{fm:.1%}"
                     f"；2013～2026 滾動 {c_w2:.1%} vs 現行 {c_f2:.1%}")
            uniq = {}
            for y, p in chosen.items():
                uniq.setdefault(p, []).append(y)
            L.append("  各年採用參數：" + "；".join(f"MA{p[0]}x{p[1]}/MA{p[2]}x{p[3]}：{ys[0]}" + (f"～{ys[-1]}" if len(ys) > 1 else "")
                                              + f"（{len(ys)} 年）" for p, ys in sorted(uniq.items(), key=lambda x: x[1][0])))
            print(L[-2], flush=True)
    out = "\n".join(L) + "\n"
    open(os.path.join(HERE, "結果_研究17_滾動最佳化.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
