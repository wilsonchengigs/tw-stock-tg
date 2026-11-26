"""研究 203：2026-11 恐慌做多（P，1x、5% 災難停損）實際逐筆成績 vs 回測預期（上線規則的實盤核對）

訊號：研究 148 build（夜盤近月跌 ≥2% 或 S&P 前一晚跌 ≥2%）；D 日盤開盤進 → D+1 日盤開盤出
停損 5%（研究 175）：D 日盤低點、當晚夜盤（標記為 D+1 的夜盤列）低點碰到進場價 ×0.95 就以停損價出；開盤跳空在下方則用開盤價
回測預期（研究 172b／175）：2017-05～ 每筆約 +0.5%、勝率約 66%；熊市（研究 194）每筆約 +0.9～1.9%
用法：python -X utf8 backtest/research_203_本月恐慌做多實績.py
"""
import csv
import importlib.util
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r148", os.path.join(HERE, "research_148_恐慌連續觸發.py"))
R148 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R148)

ohlc = defaultdict(dict)
for r in csv.DictReader(open(os.path.join(HERE, "tx_daily_ohlc.csv"), encoding="utf-8")):
    try:
        ohlc[(r["date"], r["session"])][r["month"]] = tuple(float(r[k]) for k in ("open", "high", "low", "close"))
    except ValueError:
        pass


def main(month="2026-11", stop=0.05):
    dates, day, night, near = R148.R144.R139.load_tx()
    rows = [x for x in R148.build() if x["d"].startswith(month) and x["sig"]]
    L = [f"研究 203：{month} 恐慌做多實際逐筆（1x、5% 停損、扣 3 點）"]
    tot, tot_ns = 0.0, 0.0
    for x in rows:
        d = x["d"]
        k = dates.index(d)
        m = near[dates[k - 1]]
        d1 = dates[k + 1]
        dy, nt, d1o = ohlc[(d, "day")].get(m), ohlc[(d1, "night")].get(m), ohlc[(d1, "day")].get(m)
        if not (dy and d1o):
            continue
        e = dy[0]
        sp = e * (1 - stop)
        out, how = d1o[0], "隔天開盤出"
        if dy[2] <= sp:
            out, how = sp, "日盤觸停損"
        elif nt and nt[2] <= sp:
            out, how = (nt[0] if nt[0] < sp else sp), "夜盤觸停損"
        elif d1o[0] < sp:
            out, how = d1o[0], "隔天開盤跳空低於停損"
        r = (out - e - R148.COST) / e
        rn = (d1o[0] - e - R148.COST) / e
        tot += r
        tot_ns += rn
        L.append(f"  {d} 進 {e:,.0f} → {how} {out:,.0f}：{r:+.2%}（不停損 {rn:+.2%}）")
    L.append(f"  合計（1x，單利）：{tot:+.2%}（不停損 {tot_ns:+.2%}）；{len(rows)} 筆中勝 {sum(1 for x in rows if x['r'] > 0)}")
    L.append("  回測預期：2017～ 每筆 +0.5%／勝率 66%；熊市（≤-20%）每筆 +0.9～1.9%（研究 194）")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究203_本月恐慌做多實績.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
