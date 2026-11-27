"""研究 281：台海軍演／飛彈危機後的加權走勢

事件日 E＝消息公布後的第一個台股交易日（公布在盤前就是當天）：
  1995-07-19（7/18 宣布飛彈試射）、1996-03-06（3/5 宣布飛彈試射）、2022-08-03（8/2 晚裴洛西抵台、宣布軍演）、
  2023-04-10（4/8 週六聯合利劍）、2024-05-23（聯合利劍-2024A，盤前）、2024-10-14（聯合利劍-2024B，盤前）、
  2025-04-01（海峽雷霆-2025A）、2025-12-29（正義使命-2025，盤前）
  來源：公視、聯合報、旺得富等新聞（2025 兩次）；1995／1996／2022～2024 為公開史實
做法：
(1) E-1 收盤 → E 後 1／5／20／60 日加權報酬
(2) 基準：全部非事件日同天期報酬；安慰劑＝隨機抽 8 個非事件日 5,000 次，看 1 日、5 日平均 ≤ 實際（是否顯著偏空）
(3) 事件日前 20 日漲跌、主策略位置（PX 相對 MA60×1.01、MA80×0.975；1995／1996 用核心均線算）
用法：python -X utf8 backtest/research_281_台海軍演.py
"""
import csv
import os
import random
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
EVENTS = ["1995-07-19", "1996-03-06", "2022-08-03", "2023-04-10", "2024-05-23",
          "2024-10-14", "2025-04-01", "2025-12-29"]
HS = [1, 5, 20, 60]


def load():
    px = {}
    for r in csv.DictReader(open(os.path.join(HERE, "taiex_1990_1997.csv"), encoding="utf-8")):
        px[r["date"]] = float(r["close"])
    for r in csv.DictReader(open(os.path.join(HERE, "..", "data", "taiex_daily.csv"), encoding="utf-8")):
        d = r["date"]
        px[f"{d[:4]}-{d[4:6]}-{d[6:]}"] = float(r["close"])
    import sys
    sys.path.insert(0, HERE)
    import strategy_v3 as s
    for d, v in zip(s.DAYS, s.PX):
        px.setdefault(d, v)
    days = sorted(px)
    return days, [px[d] for d in days]


def main():
    days, px = load()
    n = len(days)

    def idx(d):
        return next(i for i, x in enumerate(days) if x >= d)

    def fwd(i, h):
        j = i - 1 + h
        return px[j] / px[i - 1] - 1 if j < n else None

    def sma(i, k):
        return sum(px[i - k + 1:i + 1]) / k

    ev = [idx(d) for d in EVENTS]
    excl = set()
    for i in ev:
        excl.update(range(i - 5, i + 61))
    out = []
    p = out.append
    p("研究 281：台海軍演／飛彈危機後的加權走勢（E-1 收盤起算）\n")
    p("事件日      前20日   PX/進場線 PX/出場線 | " + "  ".join(f"{h:>4}日" for h in HS))
    rows = {h: [] for h in HS}
    for d, i in zip(EVENTS, ev):
        pre = px[i - 1] / px[i - 21] - 1
        cells = []
        for h in HS:
            r = fwd(i, h)
            if r is None:
                cells.append("   —  ")
                continue
            rows[h].append(r)
            cells.append(f"{r * 100:+6.1f}%")
        p(f"{d}  {pre * 100:+6.1f}%   {px[i - 1] / (sma(i - 1, 60) * 1.01):6.3f}   {px[i - 1] / (sma(i - 1, 80) * 0.975):6.3f}  | " + " ".join(cells))
    p("\n天期  筆數  平均     中位     勝率   非事件日平均   安慰劑 p(平均≤實際)")
    rnd = random.Random(281)
    pool = [k for k in range(80, n - 61) if k not in excl and days[k] >= "1991-01-01"]
    for h in HS:
        r = rows[h]
        base = statistics.mean(fwd(k, h) for k in pool)
        obs = statistics.mean(r)
        T = 5000
        hit = sum(statistics.mean(fwd(rnd.choice(pool), h) for _ in r) <= obs for _ in range(T))
        p(f"{h:>4}日 {len(r):>3}  {obs * 100:+6.2f}%  {statistics.median(r) * 100:+6.2f}%  {sum(x > 0 for x in r) / len(r) * 100:5.0f}%   "
          f"{base * 100:+6.2f}%        {hit / T:.3f}")
    p("\n事件後 20 日內最低收盤（相對 E-1）")
    for d, i in zip(EVENTS, ev):
        seg = px[i:min(n, i + 20)]
        k = min(range(len(seg)), key=lambda t: seg[t])
        p(f"{d}  最低 {seg[k] / px[i - 1] * 100 - 100:+6.1f}%（第 {k + 1} 天）")
    text = "\n".join(out)
    print(text)
    with open(os.path.join(HERE, "結果_研究281_台海軍演.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")


if __name__ == "__main__":
    main()
