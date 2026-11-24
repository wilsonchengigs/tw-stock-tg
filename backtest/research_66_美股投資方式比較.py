"""研究 66：單純投資美股的常見方式比較（使用者問「最適合的美股投資方式」；這裡只做歷史比較，不是個人化建議）

標的：S&P 500（^GSPC＋股息 2%／年近似 SPY）、Nasdaq-100（^NDX＋股息 0.8%／年近似 QQQ）、長期美債（VUSTX 還原價）
期間：1986-06～2026-11（債券資料起點）；分段 1986-2005、2006-2026；以美元計、未計台灣投資人的股息預扣稅 30% 與匯率
槓桿：每日再平衡 L 倍，額外每單位曝險扣 3%／年（借貸＋內扣，與 backtest/us 一致）；現金 2%／年；換手成本 0.05%
做法：
  買進持有 1x／2x／3x
  趨勢：每天收盤 > 200 日線才持有（隔天收盤成交）；月底 > 10 個月線；週五 MA60×1.01 進／MA80×0.98 出（專案台股規則）
  60/40：股 60%＋長債 40% 每月再平衡；股 2x 版本（120/40 不合理，改成 股 2x 50%＋債 50%）
  波動目標：曝險 ＝ 15% ÷ 近 20 日實現波動，上限 2x，每週調整
報表：年化、最大回檔、最差年、波動、報酬／回檔比；2006 後另以 SSO／QLD 真實價格核對 2x 模擬
用法：python -X utf8 backtest/research_66_美股投資方式比較.py
"""
import json
import math
import os
from datetime import date, datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
NY = timezone(timedelta(hours=-5))
TD = 252
DRAG, CASH, COST = 0.03, 0.02, 0.0005


def load(fn, adj=False):
    r = json.load(open(os.path.join(HERE, fn)))
    q = r["indicators"]["quote"][0]
    px = r["indicators"]["adjclose"][0]["adjclose"] if adj else q["close"]
    return {datetime.fromtimestamp(t, NY).strftime("%Y-%m-%d"): c for t, c in zip(r["timestamp"], px) if c}


SPX, NDX, BOND = load("GSPC.json"), load("NDX.json"), load("ext_VUSTX.json", adj=True)
DAYS = sorted(set(SPX) & set(NDX) & set(BOND))
DAYS = [d for d in DAYS if d >= "1985-06-01"]
N = len(DAYS)
WE = [i == N - 1 or date.fromisoformat(DAYS[i]).isocalendar()[:2] != date.fromisoformat(DAYS[i + 1]).isocalendar()[:2] for i in range(N)]
ME = [i == N - 1 or DAYS[i][:7] != DAYS[i + 1][:7] for i in range(N)]


def rets(px, div):
    p = [px[d] for d in DAYS]
    return p, [0.0] + [p[i] / p[i - 1] - 1 + div / TD for i in range(1, N)]


PS, RS = rets(SPX, 0.02)
PN, RN = rets(NDX, 0.008)
_, RB = rets(BOND, 0.0)


def sma(p, n):
    out = [None] * N
    s = 0.0
    for i in range(N):
        s += p[i]
        if i >= n:
            s -= p[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def lev_ret(r, L):
    return L * r - max(L - 1, 0) * DRAG / TD


def simulate(expo_fn, start, end):
    """expo_fn(i) 回傳 [(資產報酬序列, 曝險)]＝今天收盤決定、下一交易日收盤生效的目標部位"""
    i0 = next(i for i, d in enumerate(DAYS) if d >= start)
    i1 = max(i for i, d in enumerate(DAYS) if d <= end)
    eq = peak = 1.0
    mdd = 0.0
    pos = []
    pend = expo_fn(i0 - 1) if i0 > 0 else None  # 起始日收盤建倉（非調整日則等第一個調整日）
    daily = []
    yearly = {}
    for i in range(i0, i1 + 1):
        r = sum(lev_ret(R[i], L) for R, L in pos) if pos else 0.0
        tot = sum(L for _R, L in pos)
        r += max(1 - tot, 0) * CASH / TD
        eq *= 1 + r
        daily.append(r)
        if pend is not None:
            turn = sum(abs(a - b) for a, b in zip([L for _R, L in pend], [L for _R, L in pos])) if len(pend) == len(pos) else sum(L for _R, L in pend) + tot
            eq *= 1 - COST * turn
            pos, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        yearly.setdefault(DAYS[i][:4], [eq / (1 + r), eq])[1] = eq
        tgt = expo_fn(i)
        if tgt is not None and [L for _R, L in tgt] != [L for _R, L in pos]:
            pend = tgt
    yrs = (i1 - i0) / TD
    cagr = eq ** (1 / yrs) - 1
    vol = (sum(x * x for x in daily) / len(daily) - (sum(daily) / len(daily)) ** 2) ** 0.5 * math.sqrt(TD)
    worst = min((v[1] / v[0] - 1, y) for y, v in yearly.items())
    return cagr, mdd, worst, vol


def strategies():
    S = {}
    m200s, m200n = sma(PS, 200), sma(PN, 200)
    m210s, m210n = sma(PS, 210), sma(PN, 210)
    m60s, m80s, m60n, m80n = sma(PS, 60), sma(PS, 80), sma(PN, 60), sma(PN, 80)
    for nm, P, R, m200, m210, m60, m80 in (("S&P", PS, RS, m200s, m210s, m60s, m80s), ("NDX", PN, RN, m200n, m210n, m60n, m80n)):
        for L in (1, 2, 3):
            S[f"{nm} 買進持有 {L}x"] = (lambda R, L: lambda i: [(R, L)])(R, L)
        for L in (1, 2):
            S[f"{nm} 200日線 {L}x"] = (lambda P, R, m, L: lambda i: ([(R, L)] if m[i] and P[i] > m[i] else []))(P, R, m200, L)
            S[f"{nm} 10個月線 {L}x"] = (lambda P, R, m, L: lambda i: (None if not ME[i] else ([(R, L)] if m[i] and P[i] > m[i] else [])))(P, R, m210, L)

            def wk(P=P, R=R, m60=m60, m80=m80, L=L):
                st = {"on": False}

                def f(i):
                    if not WE[i] or m80[i] is None:
                        return None
                    if not st["on"] and P[i] > m60[i] * 1.01:
                        st["on"] = True
                    elif st["on"] and P[i] < m80[i] * 0.98:
                        st["on"] = False
                    return [(R, L)] if st["on"] else []
                return f
            S[f"{nm} 週MA60/80 {L}x"] = ("factory", wk)
        S[f"{nm} 60/40 股債"] = (lambda R: lambda i: (None if not ME[i] else [(R, 0.6), (RB, 0.4)]))(R)
        S[f"{nm} 2x 50%＋債 50%"] = (lambda R: lambda i: (None if not ME[i] else [(R, 1.0), (RB, 0.5)]))(R)

        def vt(R=R):
            def f(i):
                if not WE[i] or i < 21:
                    return None
                xs = R[i - 19:i + 1]
                m = sum(xs) / 20
                v = (sum((x - m) ** 2 for x in xs) / 19) ** 0.5 * math.sqrt(TD)
                L = round(min(2.0, 0.15 / v) if v > 0 else 2.0, 1)
                return [(R, L)]
            return f
        S[f"{nm} 波動目標15% 上限2x"] = ("factory", vt)
    S["S&P 60/40 股債"] = S.pop("S&P 60/40 股債")
    return S


def main():
    L = ["研究 66：美股投資方式比較（美元計；S&P 含息 2%、NDX 含息 0.8% 近似；槓桿每單位扣 3%／年；現金 2%；成本 0.05%）",
         "注意：歷史比較不是個人化建議；台灣投資人買美國 ETF 股息預扣 30%（每年約 -0.2～-0.6%）、加上匯率波動，未計入",
         "\n格式：年化／最大回檔（最差年）；報酬回檔比＝年化÷|回檔|"]
    periods = (("1986-06-01", "2026-12-31", "全期 1986-2026"), ("1986-06-01", "2005-12-31", "前段 1986-2005"), ("2006-01-01", "2026-12-31", "後段 2006-2026"))
    S = strategies()
    rows = []
    for nm, f in S.items():
        cells = []
        res = []
        for s, e, _p in periods:
            fn = f[1]() if isinstance(f, tuple) else f
            res.append(simulate(fn, s, e))
        rows.append((nm, res))
    L.append(f"{'做法':22s} | " + " | ".join(f"{p[2]:^30s}" for p in periods) + " | 全期波動 報酬回檔比")
    for nm, res in rows:
        cells = [f"{c:6.1%}／{m:6.1%}（{w[1]} {w[0]:+.0%}）" for c, m, w, _v in res]
        c, m, _w, v = res[0]
        L.append(f"{nm:22s} | " + " | ".join(cells) + f" | {v:5.1%}  {c / abs(m):.2f}")
    # 真實 ETF 核對（2006-06 起）
    L.append("\n== 2006-06 起真實 ETF（還原價，買進持有）vs 模擬 ==")
    for etf, sim_nm, R, Lv in (("SPY", "S&P 1x", RS, 1), ("SSO", "S&P 2x", RS, 2), ("QQQ", "NDX 1x", RN, 1), ("QLD", "NDX 2x", RN, 2)):
        px = load(f"{etf}.json", adj=True)
        ds = [d for d in DAYS if d >= "2006-06-22" and d in px]
        yrs = len(ds) / TD
        eq, peak, mdd = 1.0, 1.0, 0.0
        for a, b in zip(ds, ds[1:]):
            eq *= px[b] / px[a]
            peak = max(peak, eq)
            mdd = min(mdd, eq / peak - 1)
        c, m, _w, _v = simulate(lambda i: [(R, Lv)], "2006-06-22", ds[-1])
        L.append(f"  {etf:4s} 真實 {eq ** (1 / yrs) - 1:6.1%}／{mdd:6.1%}   模擬 {sim_nm} {c:6.1%}／{m:6.1%}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究66_美股投資方式.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
