"""研究 63g：「爆量收黑買台指期」當獨立策略的資金曲線與凱利部位（台指期真實價格，研究 63d 的資料與進出場）

規則：證交所成交金額 ≥1.5x 20 日均、台指期日盤收黑 → 隔天日盤開盤買近月、抱 5 個日盤後收盤賣；停損 無／3％／5％
      （停損以進場價計，盤中最低觸及即出、開盤跳空以開盤價；成本每筆 3 點）
曝險：名目部位 ＝ 資金 × L（L＝0.5、1、2、3；例如資金 200 萬、指數 4 萬點、大台每點 200 → 1 口 800 萬名目 ≈ L 4）
空手時資金年息 1%
報表：年化、最大回檔、在場時間比例、每年報酬；凱利 f*（以每筆報酬的 平均／變異數 近似）、半凱利
用法：python -X utf8 backtest/research_63g_爆量收黑期貨資金曲線.py
"""
import importlib.util
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("r63d", os.path.join(HERE, "research_63d_爆量收黑_台指期真實價.py"))
r63d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r63d)
COST, ROLL, CASH = 3.0, 2.0, 0.01


def main():
    dates, day, night, near = r63d.load()
    n = len(dates)
    amt = [r63d.AMT.get(d) for d in dates]

    def vr(i):
        xs = [amt[k] for k in range(i - 20, i) if amt[k]]
        return amt[i] / (sum(xs) / len(xs)) if amt[i] and len(xs) >= 16 else None

    def bar(i, m=None):
        d = dates[i]
        return day[d].get(m or near[d])

    def trade(i, H, stop):
        """回傳 (逐日報酬 list[(index, r)], 出場 index)；第一天＝開盤到收盤"""
        e = i + 1
        m = near[dates[e]]
        o, h, lo, c, _v = bar(e, m)
        px = o
        lim = px * (1 - stop) if stop else None
        path = []
        prev = px
        for j in range(e, min(i + H, n - 1) + 1):
            mj = near[dates[j]]
            b = bar(j, m) or bar(j, mj)
            if b is None:
                break
            if j > e and mj != m:  # 換月：前一日用新契約收盤接續
                pb = bar(j - 1, mj)
                if pb:
                    prev = pb[3] * (1 + ROLL / pb[3])
                m = mj
                b = bar(j, m)
            bo, bh, bl, bc, _ = b
            if lim is not None:
                lim_j = lim  # 以原始進場價計（換月後近似）
                if j > e and bo <= lim_j:
                    path.append((j, bo / prev - 1))
                    return path, j
                if bl <= lim_j:
                    path.append((j, lim_j / prev - 1))
                    return path, j
            path.append((j, bc / prev - 1))
            prev = bc
        return path, path[-1][0] if path else e

    L = ["研究 63g：爆量收黑買台指期——獨立策略資金曲線（成交金額 ≥1.5x、收黑、隔天開盤買、抱 5 天；成本 3 點）"]
    start = next(i for i, d in enumerate(dates) if d >= "1998-09-01")
    for stop in (None, 0.03, 0.05):
        sig = [i for i in range(max(start, 21), n - 2) if (v := vr(i)) is not None and v >= 1.5
               and bar(i)[3] < (bar(i - 1, near[dates[i]]) or bar(i - 1))[3]]
        trades, busy = [], -1
        daily = {}
        for i in sig:
            if i + 1 <= busy:
                continue
            path, x = trade(i, 5, stop)
            if not path:
                continue
            px = bar(i + 1)[0]
            tot = 1.0
            for j, r in path:
                tot *= 1 + r
                daily[j] = daily.get(j, 0) + r
            daily[path[0][0]] -= COST / px
            trades.append(tot - 1 - COST / px)
            busy = x
        mu = statistics.mean(trades)
        var = statistics.pvariance(trades)
        kelly = mu / var if var > 0 else 0
        L.append(f"\n== 停損 {'無' if stop is None else f'{stop:.0%}'}：{len(trades)} 筆、勝率 {sum(t > 0 for t in trades) / len(trades):.0%}、"
                 f"每筆 {mu:+.2%}、標準差 {var ** 0.5:.2%}、最差 {min(trades):+.1%} ==")
        L.append(f"  凱利 f*≈ 平均／變異數 ＝ {kelly:.1f} 倍名目（半凱利 {kelly / 2:.1f}）"
                 f"——資金 100 萬、指數 4 萬點：大台 1 口名目 800 萬（8 倍）、小台 1 口 200 萬（2 倍）")
        yrs = (n - start) / 245
        for lev in (0.5, 1.0, 2.0, 3.0, 4.0):
            eq = peak = 1.0
            mdd = 0.0
            by_year = {}
            for i in range(start, n):
                r = daily.get(i)
                eq *= 1 + (lev * r if r is not None else CASH / 245)
                eq = max(eq, 1e-9)
                peak = max(peak, eq)
                mdd = min(mdd, eq / peak - 1)
                y = dates[i][:4]
                by_year.setdefault(y, [eq, eq])[1] = eq
            cagr = eq ** (1 / yrs) - 1
            yr = {y: v[1] / v[0] - 1 for y, v in by_year.items()}
            worst = min(yr.items(), key=lambda x: x[1])
            L.append(f"  名目 {lev:.1f} 倍：年化 {cagr:+.1%}  最大回檔 {mdd:.1%}  最差年 {worst[0]} {worst[1]:+.1%}  虧損年數 {sum(v < 0 for v in yr.values())}/{len(yr)}")
        L.append(f"  在場時間 ≈ {len(daily) / (n - start):.1%}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究63g_期貨資金曲線.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
