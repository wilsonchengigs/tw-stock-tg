"""研究 195：跌破 -15%／-20% 那一刻，能不能分辨之後是 V 轉還是真熊市？（描述性，樣本少不做規則）

研究 193：跌破 -20% 的 17 次裡 6 次 V 轉、11 次再跌（中位 -32%），事前看不出。這裡試幾個有道理的特徵：
- 全球 vs 台灣自己：S&P 500 當時離 250 日高多遠（全球一起跌 vs 只有台灣跌）
- 跌速：從 250 日高點到跌破花了幾天（急殺 vs 陰跌）
- 20 日波動
- 融資：近 20 日融資金額變化（大減＝斷頭、籌碼清洗；2001～）
- 長期趨勢：跌破時 250 日均線的斜率（年線還在上升＝多頭中的修正）
結果：之後「再跌」幅度（回到前高之前的最低點）與 12 個月報酬；依各特徵中位數分兩組比較
用法：python -X utf8 backtest/research_195_V轉vs熊市分辨.py
"""
import bisect
import csv
import importlib.util
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r187", os.path.join(HERE, "research_187_高波動來回刷.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
D, P = R.D, R.P0
N = len(P)

g = json.load(open(os.path.join(HERE, "GSPC.json")))
NY = timezone(timedelta(hours=-5))
SPD = [datetime.fromtimestamp(t, NY).strftime("%Y-%m-%d") for t in g["timestamp"]]
SPP = g["indicators"]["quote"][0]["close"]
SP = [(d, p) for d, p in zip(SPD, SPP) if p]
SPD, SPP = [d for d, _ in SP], [p for _, p in SP]
MG = [(r["date"], float(r["balance"])) for r in csv.DictReader(open(os.path.join(HERE, "margin_tw.csv"), encoding="utf-8"))]
MGD = [d for d, _ in MG]


def sp_dd(day):
    k = bisect.bisect_left(SPD, day) - 1
    if k < 250:
        return None
    return SPP[k] / max(SPP[k - 249:k + 1]) - 1


def margin_chg(day, n=20):
    k = bisect.bisect_right(MGD, day) - 1
    if k < n:
        return None
    return MG[k][1] / MG[k - n][1] - 1


def events(th):
    hi = [max(P[max(0, i - 249):i + 1]) for i in range(N)]
    out, armed = [], True
    for j in range(250, N):
        dd = P[j] / hi[j] - 1
        if armed and dd <= -th:
            out.append(j)
            armed = False
        elif not armed and dd > -th / 2:
            armed = True
    return out, hi


def main():
    L = ["研究 195：跌破時能否分辨 V 轉 vs 真熊市（描述性）"]
    m250 = R.sma(P, 250)
    vol20 = R.rvol(P, 20)
    for th in (0.20, 0.15):
        ev, hi = events(th)
        rows = []
        for j in ev:
            pk = hi[j]
            ipk = max(range(j - 249, j + 1), key=lambda t: P[t])
            back = next((t for t in range(j + 1, N) if P[t] >= pk), None)
            end = back if back else N - 1
            more = min(P[j:end + 1]) / P[j] - 1
            f12 = P[j + 252] / P[j] - 1 if j + 252 < N else None
            slope = (m250[j] / m250[j - 60] - 1) if m250[j] and m250[j - 60] else None
            rows.append({"d": D[j], "more": more, "f12": f12, "sp": sp_dd(D[j]), "speed": j - ipk, "vol": vol20[j],
                         "mg": margin_chg(D[j]), "slope": slope, "done": j < N - 260})
        L.append(f"\n==== 跌破 -{th:.0%}（{len(rows)} 次；之後再跌＝回到前高前的最低點）====")
        L.append("  日期        再跌   12月   S&P離高  跌速(天)  20日波動  融資20日  年線60日斜率")
        for r in rows:
            fm = lambda v, f: (f.format(v) if v is not None else "  —  ")  # noqa: E731
            L.append(f"  {r['d']}  {r['more']:+5.0%}  {fm(r['f12'], '{:+5.0%}')}  {fm(r['sp'], '{:+6.0%}')}  {r['speed']:>6}  {r['vol']:6.0%}  "
                     f"{fm(r['mg'], '{:+6.0%}')}  {fm(r['slope'], '{:+6.1%}')}")
        done = [r for r in rows if r["done"]]
        L.append(f"  （已有 12 個月結果 {len(done)} 次）各特徵依中位數分兩組：再跌中位／12 月中位／真熊市（再跌 ≥10%）比例")
        for key, name in (("sp", "S&P 離高"), ("speed", "跌速（天）"), ("vol", "20 日波動"), ("mg", "融資 20 日變化"), ("slope", "年線斜率")):
            g2 = [r for r in done if r[key] is not None]
            if len(g2) < 6:
                continue
            med = sorted(r[key] for r in g2)[len(g2) // 2]
            for lab, grp in ((f"≤{med:.2f}", [r for r in g2 if r[key] <= med]), (f">{med:.2f}", [r for r in g2 if r[key] > med])):
                mm = sorted(r["more"] for r in grp)
                ff = sorted(r["f12"] for r in grp if r["f12"] is not None)
                L.append(f"    {name:<10}{lab:>8}：{len(grp):>2} 次  再跌中位 {mm[len(mm) // 2]:+.0%}  12 月中位 {ff[len(ff) // 2]:+.0%}  "
                         f"真熊市 {sum(r['more'] <= -0.10 for r in grp)}/{len(grp)}")
        cur = rows[-1]
        L.append(f"  現在（{cur['d']} 那次）：S&P 離高 {cur['sp']:+.0%}、跌速 {cur['speed']} 天、20 日波動 {cur['vol']:.0%}、"
                 f"融資 20 日 {cur['mg']:+.0%}、年線斜率 {cur['slope']:+.1%}" if cur["sp"] is not None and cur["mg"] is not None else "")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究195_V轉vs熊市分辨.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
