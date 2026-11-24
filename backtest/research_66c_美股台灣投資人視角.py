"""研究 66c：台灣投資人買美股的實際報酬——台灣掛牌美股 ETF vs 直接買美國 ETF（新台幣計、含股息預扣稅）

比較（各自從台灣 ETF 上市日起）：
  00646（元大 S&P500）   vs  SPY
  00662（富邦 NASDAQ）   vs  QQQ
  00670L（富邦 NASDAQ 正2）vs  QLD
美國 ETF：Yahoo 還原價（股息再投入）拆成「價格報酬＋股息」，股息只計 70%（美國對台灣居民預扣 30%）；以 ext_USDTWD 換成新台幣
台灣 ETF：Yahoo 還原價（新台幣；這幾檔不配息，費用已內含在淨值）
未計：複委託／海外券商手續費、匯兌價差、台灣 ETF 的折溢價變化（已反映在市價）
用法：python -X utf8 backtest/research_66c_美股台灣投資人視角.py
"""
import json
import os
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))


def series(fn, tz, field="adjclose"):
    r = json.load(open(os.path.join(HERE, fn)))
    q = r["indicators"]["quote"][0]
    vals = list(r["indicators"]["adjclose"][0]["adjclose"] if field == "adjclose" else q["close"])
    # Yahoo 偶爾沒把分割反映進還原價（如 00662 2026-11-09 1 拆 5）：若分割日前後價格仍跳動約同比例，手動調整
    for sp in (r.get("events", {}).get("splits") or {}).values():
        ratio = sp["numerator"] / sp["denominator"]
        k0 = next((i for i, t in enumerate(r["timestamp"]) if t >= sp["date"]), len(vals) - 1)
        # Yahoo 記的分割日與價格實際跳動日可能差幾天：在前後 10 個交易日內找「跳動 ≈ 1/ratio」的那天
        for k in range(max(1, k0 - 10), min(len(vals), k0 + 11)):
            if vals[k] and vals[k - 1] and abs(vals[k] / vals[k - 1] * ratio - 1) < 0.15:
                vals = [v / ratio if v and i < k else v for i, v in enumerate(vals)]
                break
    return {datetime.fromtimestamp(t, timezone(timedelta(hours=tz))).strftime("%Y-%m-%d"): v for t, v in zip(r["timestamp"], vals) if v}


def fx():
    s = series("ext_USDTWD.json", 0, "close")
    return s


def stats(days, val):
    eq = [val[d] / val[days[0]] for d in days]
    peak, mdd = 1.0, 0.0
    for x in eq:
        peak = max(peak, x)
        mdd = min(mdd, x / peak - 1)
    yrs = (datetime.fromisoformat(days[-1]) - datetime.fromisoformat(days[0])).days / 365.25
    return eq[-1] ** (1 / yrs) - 1, mdd, yrs


def main():
    FX = fx()
    fxd = sorted(FX)

    def fx_at(d):
        # 該日或之前最近的匯率
        lo, hi = 0, len(fxd) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if fxd[mid] <= d:
                lo = mid
            else:
                hi = mid - 1
        return FX[fxd[lo]]

    L = ["研究 66c：台灣投資人買美股（新台幣計；美國 ETF 股息只計 70%）",
         "格式：年化／最大回檔"]
    for tw, us, nm in (("00646.json", "SPY.json", "S&P 500"), ("00662.json", "QQQ.json", "NASDAQ-100"), ("00670L.json", "QLD.json", "NASDAQ-100 正2")):
        T = series(tw, 8)
        A = series(us, -5)
        P = series(us, -5, "close")
        start = min(T)
        # 台灣日期 d 對應前一個美國交易日收盤（台灣收盤時美股尚未開盤）
        ud = sorted(A)
        days = [d for d in sorted(T) if d >= start]
        # 美國 ETF 新台幣淨值（股息 70%）
        net = {}
        gross = {}
        g = n_ = None
        prev = None
        j = 0
        for d in days:
            while j + 1 < len(ud) and ud[j + 1] < d:
                j += 1
            u = ud[j]
            if prev is None:
                g = n_ = 1.0
            elif u != prev:
                tr = A[u] / A[prev] - 1
                pr = P[u] / P[prev] - 1
                div = max(tr - pr, 0.0)
                g *= 1 + tr
                n_ *= 1 + pr + 0.7 * div
            prev = u
            gross[d] = g * fx_at(u)
            net[d] = n_ * fx_at(u)
        c1, m1, yrs = stats(days, T)
        c2, m2, _ = stats(days, gross)
        c3, m3, _ = stats(days, net)
        us_n = us.split(".")[0]
        tw_n = tw.split(".")[0]
        L.append(f"\n== {nm}：{days[0]}～{days[-1]}（{yrs:.1f} 年）==")
        L.append(f"  {tw_n:7s}（台灣掛牌）        {c1:6.1%}／{m1:6.1%}")
        L.append(f"  {us_n:7s} 新台幣、股息全拿   {c2:6.1%}／{m2:6.1%}")
        L.append(f"  {us_n:7s} 新台幣、股息扣 30%  {c3:6.1%}／{m3:6.1%}   ← 台灣居民實際")
        L.append(f"  差距（{us_n} 實際 − {tw_n}）：{c3 - c1:+.2%}／年")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究66c_台灣投資人視角.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
