"""研究 184：已經大跌好幾週之後，下一週再大跌的機率（使用者 2026-11-26 問）

現況：11/25 收 38,195，離 60 日高點 -23%，單日 -4.8%，20 日波動 62%（1998 起最高）。
問題：研究 182 說大跌後一週偏多，但「已經連跌幾週」時，下週會不會接著大跌？
做法：事件日 j 的條件
- 深跌：收盤離 60 日最高收盤 ≤ -15%／≤ -20%
- 深跌＋當天跌 ≥4%（最像現在）
- 高波動：20 日年化波動前 5%
對每個事件看「之後 5 個交易日」（從事件隔天收盤算起＝今天收盤進，和研究 182 的建議一致；另附從事件當天收盤算）：
- 5 天報酬 < 0、≤ -5%、≤ -10% 的機率；≥ +5% 的機率
- 5 天內「再出現單日跌 ≥4%」「再出現單日跌 ≥3%」的機率
- 5 天內收盤最低點（相對進場價）的分布＝抱一週中途最痛會痛多少
基準：全部交易日。去叢集：事件後 5 天內不重複計（獨立事件）。
用法：python -X utf8 backtest/research_184_連跌數週後下週再大跌機率.py
"""
import math
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import data  # noqa: E402

TODAY = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
tw = data.load("TWII")
DAYS = [d for d in sorted(tw) if "1998-01-01" <= d < TODAY]
PX = [tw[d][0] for d in DAYS]
N = len(PX)
R = [0.0] + [PX[i] / PX[i - 1] - 1 for i in range(1, N)]
DD = [PX[i] / max(PX[max(0, i - 59):i + 1]) - 1 for i in range(N)]
VOL = [None] * N
for i in range(20, N):
    w = R[i - 19:i + 1]
    m = sum(w) / 20
    VOL[i] = math.sqrt(sum((x - m) ** 2 for x in w) / 19) * math.sqrt(245)
vs = sorted(v for v in VOL if v is not None)
V95 = vs[int(len(vs) * 0.95)]


def outcome(j, lag):
    a = j + lag
    if a + 5 >= N:
        return None
    path = PX[a + 1:a + 6]
    rs = R[a + 1:a + 6]
    return {"ret": path[-1] / PX[a] - 1, "low": min(path) / PX[a] - 1,
            "d4": any(r <= -0.04 for r in rs), "d3": any(r <= -0.03 for r in rs), "u4": any(r >= 0.04 for r in rs)}


def events(cond, gap=5):
    out, last = [], -99
    for j in range(60, N):
        if cond(j) and j - last > gap:
            out.append(j)
            last = j
    return out


def line(name, ev, lag):
    o = [x for x in (outcome(j, lag) for j in ev) if x is not None]
    n = len(o)
    if not n:
        return f"  {name}：0 筆"
    f = lambda k: sum(k(x) for x in o) / n  # noqa: E731
    lows = sorted(x["low"] for x in o)
    return (f"  {name}：{n:>4} 筆｜一週下跌 {f(lambda x: x['ret'] < 0):4.0%}｜≤-5% {f(lambda x: x['ret'] <= -0.05):4.0%}"
            f"｜≤-10% {f(lambda x: x['ret'] <= -0.10):4.0%}｜≥+5% {f(lambda x: x['ret'] >= 0.05):4.0%}"
            f"｜再一天跌≥4% {f(lambda x: x['d4']):4.0%}｜跌≥3% {f(lambda x: x['d3']):4.0%}｜漲≥4% {f(lambda x: x['u4']):4.0%}"
            f"｜中途最低 中位 {lows[n // 2]:+.1%}、最差 1/4 {lows[n // 4]:+.1%}、最差 {lows[0]:+.1%}")


def main():
    i = N - 1
    L = ["研究 184：連跌數週後，下一週再大跌的機率（加權收盤；去叢集 5 天）",
         f"現況 {DAYS[i]}：收 {PX[i]:,.0f}、離 60 日高 {DD[i]:+.1%}、當天 {R[i]:+.2%}、20 日波動 {VOL[i]:.0%}（第 95 分位＝{V95:.0%}）"]
    wk = []
    k = i
    for _ in range(6):
        k0 = max(0, k - 5)
        wk.append(f"{DAYS[k0 + 1][5:]}～{DAYS[k][5:]} {PX[k] / PX[k0] - 1:+.1%}")
        k = k0
    L.append("近 6 週（每 5 個交易日）：" + "；".join(reversed(wk)))
    sets = [
        ("全部交易日（基準）", lambda j: True, 0),
        ("離 60 日高 ≤-15%", lambda j: DD[j] <= -0.15, 5),
        ("離 60 日高 ≤-20%", lambda j: DD[j] <= -0.20, 5),
        ("20 日波動前 5%", lambda j: VOL[j] is not None and VOL[j] >= V95, 5),
        ("離高 ≤-15% 且當天跌 ≥4%", lambda j: DD[j] <= -0.15 and R[j] <= -0.04, 5),
        ("離高 ≤-20% 且當天跌 ≥4%（最像現在）", lambda j: DD[j] <= -0.20 and R[j] <= -0.04, 5),
    ]
    for lag, lab in ((1, "從事件隔天收盤算（＝今天 11/26 收盤進）"), (0, "從事件當天收盤算")):
        L.append(f"\n【{lab}，之後 5 個交易日】")
        for name, c, gap in sets:
            ev = events(c, gap) if gap else list(range(60, N))
            L.append(line(name, ev, lag))
    ev = events(lambda j: DD[j] <= -0.20 and R[j] <= -0.04)
    L.append("\n最像現在的事件明細（隔天收盤進，5 天報酬／中途最低／期間有沒有再跌 ≥4%）：")
    for j in ev:
        o = outcome(j, 1)
        if o:
            L.append(f"  {DAYS[j]} 離高 {DD[j]:+.0%}、當天 {R[j]:+.1%} → 5 天 {o['ret']:+.1%}、中途最低 {o['low']:+.1%}{'、又跌≥4%' if o['d4'] else ''}")
    L.append("\n三段（離高 ≤-15% 且跌 ≥4%，隔天收盤進）：")
    for y0, y1 in (("1998", "2012"), ("2013", "2026")):
        L.append(line(f"{y0}–{y1}", [j for j in events(lambda j: DD[j] <= -0.15 and R[j] <= -0.04) if y0 <= DAYS[j][:4] <= y1], 1))
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究184_連跌數週後下週再大跌機率.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
