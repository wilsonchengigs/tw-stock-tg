"""研究 293：國安基金結束護盤（退場決議）後的加權走勢

決議日（多為下午例會，台股反應在下一個交易日 E；報酬從決議日收盤＝E-1 收盤起算）：
  確認：2016-04-12、2020-10-12、2023-04-13（首季例會）、2026-01-12（第四季例會）
  區間終點（可信度較低）：2000-11-15、2004-06-01、2008-12-17、2012-04-20
做法同研究 281：E-1 收盤 → 1／5／20／60 日；安慰劑＝隨機抽同數量非事件日 5,000 次（看是否偏空）
用法：python -X utf8 backtest/research_293_國安基金退場.py
"""
import csv
import os
import random
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
EVENTS = ["2000-11-16", "2004-06-02", "2008-12-18", "2012-04-23", "2016-04-13", "2020-10-13", "2023-04-14", "2026-01-13"]
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
    p("研究 293：國安基金退場決議後的加權走勢（決議日收盤起算）\n")
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
    with open(os.path.join(HERE, "結果_研究293_國安基金退場.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")


if __name__ == "__main__":
    main()
