"""研究 64h：在場加碼（研究 64b，k 1.5、加 1x、抱 10 天）的逐筆風險

逐筆列出每次加碼：訊號日、出場日、持有天數、指數漲跌、持有期間最大不利（以收盤計）、是否因現行出場而提早平倉
統計：勝率、平均、最差、最大不利分布、連續虧損、加碼對帳戶的單筆影響（以加碼 1x 計＝指數漲跌 × 1）
另：同期間台指期真實價（夜盤開盤進）的對照（2017-05 後）
用法：python -X utf8 backtest/research_64h_在場加碼逐筆風險.py
"""
import importlib.util
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("r64b", os.path.join(HERE, "research_64b_在場時爆量收黑加碼.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
r64 = m.r64
DAYS, PX, VR, N = m.DAYS, m.PX, m.VR, m.N
K, H = 1.5, 10


def main():
    st = r64.state_series()  # 週五判斷後的狀態；實際持有＝前一天的 st
    held = [False] + st[:-1]
    i0 = next(i for i, d in enumerate(DAYS) if d >= "2002-01-01")
    trades = []
    busy = -1
    for i in range(i0, N - 1):
        if i <= busy or not (held[i] and st[i]):
            continue
        if VR[i] is None or VR[i] < K or PX[i] >= PX[i - 1]:
            continue
        x = min(i + H, N - 1)
        early = None
        for j in range(i + 1, x + 1):
            if not held[j]:
                early = j
                break
        x = early if early else x
        path = [PX[j] / PX[i] - 1 for j in range(i, x + 1)]
        trades.append(dict(d=DAYS[i], x=DAYS[x], n=x - i, ret=PX[x] / PX[i] - 1, mae=min(path), early=early is not None, vr=VR[i]))
        busy = x
    L = [f"研究 64h：在場加碼逐筆風險（k {K}、加 1x、抱 {H} 天；2002-2026；收盤進出，未扣成本）"]
    L.append("訊號日       出場日      天數  量比  指數漲跌  期間最大不利  備註")
    for t in trades:
        L.append(f"{t['d']}  {t['x']}  {t['n']:3d}  {t['vr']:.2f}  {t['ret']:+7.2%}   {t['mae']:+7.2%}    {'現行出場提早平' if t['early'] else ''}")
    rets = [t["ret"] for t in trades]
    maes = sorted(t["mae"] for t in trades)
    L.append(f"\n共 {len(trades)} 筆（{len(trades) / 24.9:.1f} 筆／年）；勝率 {sum(r > 0 for r in rets) / len(rets):.0%}；平均 {statistics.mean(rets):+.2%}；中位 {statistics.median(rets):+.2%}")
    L.append(f"最差 3 筆：" + "、".join(f"{t['d']} {t['ret']:+.1%}" for t in sorted(trades, key=lambda t: t['ret'])[:3]))
    L.append(f"期間最大不利：中位 {statistics.median(maes):+.1%}、最差 {maes[0]:+.1%}、≤-5% 的 {sum(x <= -0.05 for x in maes)} 筆、≤-3% 的 {sum(x <= -0.03 for x in maes)} 筆")
    L.append(f"因現行出場而提早平倉：{sum(t['early'] for t in trades)} 筆（平均 {statistics.mean([t['ret'] for t in trades if t['early']] or [0]):+.2%}）")
    streak = best = 0
    for r in rets:
        streak = streak + 1 if r <= 0 else 0
        best = max(best, streak)
    L.append(f"最長連續虧損：{best} 筆")
    for lab, lo, hi in (("2002-2012", "2002", "2013"), ("2013-2026", "2013", "2027")):
        rr = [t["ret"] for t in trades if lo <= t["d"] < hi]
        if rr:
            L.append(f"{lab}：{len(rr)} 筆 勝率 {sum(r > 0 for r in rr) / len(rr):.0%} 平均 {statistics.mean(rr):+.2%}")
    L.append("\n實務：加碼 1x 名目＝帳戶多承擔 1 倍指數漲跌；最差單筆約等於帳戶 "
             f"{min(rets):+.1%}、期間最大不利 {maes[0]:+.1%}。資金 200 萬加小台 1 口（名目約 200 萬＝1x）時，最大不利約 {abs(maes[0]) * 2e6:,.0f} 元")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究64h_在場加碼逐筆.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
