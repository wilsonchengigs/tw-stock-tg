"""研究 63i：爆量收黑買台指期 × 趨勢條件（研究 64 拆解發現反彈集中在多頭急跌，用台指期真實價驗證）

訊號同研究 63d：證交所成交金額 ≥1.5x（另測 1.3x）20 日均、台指期日盤收黑 → 隔天日盤開盤買、抱 5／10 天
趨勢條件（訊號日當天可知）：台指期收盤 vs 近月連續收盤的 60／80／120 日均線；多頭＝在均線上
注意：這是研究 64 看過資料後的假說（事後分組），前後段一致才算數
用法：python -X utf8 backtest/research_63i_爆量收黑_趨勢條件.py
"""
import importlib.util
import os
import random
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("r63d", os.path.join(HERE, "research_63d_爆量收黑_台指期真實價.py"))
r63d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r63d)
COST, ROLL = 3.0, 2.0


def main():
    dates, day, night, near = r63d.load()
    n = len(dates)
    C = [day[d][near[d]][3] for d in dates]
    # 換月接續的連續價格（回溯調整）
    R = [0.0] * n
    for i in range(1, n):
        m, pm = near[dates[i]], near[dates[i - 1]]
        prev = day[dates[i - 1]].get(m)
        R[i] = C[i] / prev[3] - 1 if prev else C[i] / C[i - 1] - 1
    P = [1.0]
    for i in range(1, n):
        P.append(P[-1] * (1 + R[i]))

    def ma(k):
        out = [None] * n
        for i in range(k - 1, n):
            out[i] = sum(P[i - k + 1:i + 1]) / k
        return out
    MA = {k: ma(k) for k in (60, 80, 120)}
    amt = [r63d.AMT.get(d) for d in dates]

    def vr(i):
        xs = [amt[k] for k in range(i - 20, i) if amt[k]]
        return amt[i] / (sum(xs) / len(xs)) if amt[i] and len(xs) >= 16 else None

    def trade(i, H):
        e, x = i + 1, i + H
        if x >= n:
            return None
        m = near[dates[e]]
        px = day[dates[e]][m][0]
        g = day[dates[e]][m][3] / px
        for j in range(e + 1, x + 1):
            g *= 1 + R[j]
        return g - 1 - COST / px, x

    rng = random.Random(639)
    L = ["研究 63i：爆量收黑買台指期 × 趨勢條件（台指期真實價；隔天開盤買；成本 3 點）"]
    for k_ in (1.5, 1.3):
        sig = [i for i in range(130, n - 1) if dates[i] >= "1998-09-01" and (v := vr(i)) is not None and v >= k_ and R[i] < 0]
        for H in (5, 10):
            L.append(f"\n== 成交金額 ≥{k_}x 收黑、抱 {H} 天 ==")
            for nm, cond in [("全部", lambda i: True)] + [(f"多頭（> MA{k}）", (lambda k: lambda i: P[i] > MA[k][i])(k)) for k in (60, 80, 120)] \
                    + [(f"空頭（≤ MA{k}）", (lambda k: lambda i: P[i] <= MA[k][i])(k)) for k in (60, 80, 120)]:
                cells = []
                for lab, lo, hi in (("全期", "1998", "2027"), ("1998-2012", "1998", "2013"), ("2013-2026", "2013", "2027")):
                    trs, busy = [], -1
                    for i in sig:
                        if not (lo <= dates[i] < hi) or not cond(i) or i + 1 <= busy:
                            continue
                        t = trade(i, H)
                        if t:
                            trs.append(t[0])
                            busy = t[1]
                    if len(trs) < 5:
                        cells.append(f"{lab} {len(trs):2d} 筆")
                        continue
                    pool = [i for i in range(130, n - H - 1) if lo <= dates[i] < hi]
                    rnd = sorted(statistics.mean(trade(rng.choice(pool), H)[0] for _ in trs) for _ in range(500))
                    ev = statistics.mean(trs)
                    p = (sum(x >= ev for x in rnd) + 1) / 501
                    cells.append(f"{lab} {len(trs):2d} 筆 勝率 {sum(t > 0 for t in trs) / len(trs):4.0%} {ev:+.2%} p{p:.2f}")
                L.append(f"  {nm:12s} " + " ｜ ".join(cells))
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究63i_趨勢條件.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
