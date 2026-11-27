"""研究 289：Fed 升降息循環的「第一次降息」「第一次升息」之後台股

日期（FOMC 決策日，美國時間；台股反應在下一個台股交易日 E）：
  首次降息：1990-07-13、1995-07-06、1998-09-29、2001-01-03、2007-09-18、2019-07-31、2024-09-18
    （2020-03-03 緊急降息接在 2019 循環後，不算新循環）
  首次升息：1994-02-04、1999-06-30、2004-06-30、2015-12-16、2022-03-16
報酬：E-1 收盤 → E 後 20／60／120／250 日加權（%）；對照＝1990 起所有交易日同天期報酬分布，看事件平均的百分位
  （百分位用「隨機抽同數量日子」5,000 次的平均分布，雙尾）
另標記：降息後 12 個月內美國是否進入 NBER 衰退（2001、2007 是；1990 已在衰退中）
用法：python -X utf8 backtest/research_289_Fed首次升降息.py
"""
import csv
import os
import random
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import strategy_v3 as s  # noqa: E402

CUTS = [("1990-07-13", "已在衰退"), ("1995-07-06", "軟著陸"), ("1998-09-29", "LTCM 保險性"), ("2001-01-03", "衰退"),
        ("2007-09-18", "衰退"), ("2019-07-31", "保險性"), ("2024-09-18", "軟著陸")]
HIKES = ["1994-02-04", "1999-06-30", "2004-06-30", "2015-12-16", "2022-03-16"]
HS = (20, 60, 120, 250)


def load():
    px = {}
    for r in csv.DictReader(open(os.path.join(HERE, "taiex_1990_1997.csv"), encoding="utf-8")):
        px[r["date"]] = float(r["close"])
    for d, v in zip(s.DAYS, s.PX):
        px[d] = v
    days = sorted(px)
    return days, [px[d] for d in days]


def main():
    days, P = load()
    n = len(P)
    idx = lambda d: next(i for i, x in enumerate(days) if x > d)  # noqa: E731  台股在美國決策日之後的第一個交易日
    fwd = lambda i, h: (P[i - 1 + h] / P[i - 1] - 1) * 100 if i - 1 + h < n else None  # noqa: E731
    pool = list(range(1, n - 251))
    rnd = random.Random(289)
    out = []
    p = out.append
    p("研究 289：Fed 首次降息／升息後的加權報酬（%，E-1 收盤起算）\n")
    p("全部日子平均：" + "  ".join(f"{h}日 {statistics.mean(fwd(i, h) for i in pool):+.1f}%" for h in HS) + "\n")
    for name, evs in (("首次降息", [d for d, _ in CUTS]), ("首次升息", HIKES)):
        p(f"【{name}】")
        rows = {h: [] for h in HS}
        for k, d in enumerate(evs):
            i = idx(d)
            tag = CUTS[k][1] if name == "首次降息" else ""
            cells = []
            for h in HS:
                r = fwd(i, h)
                if r is not None:
                    rows[h].append(r)
                cells.append(f"{r:+6.1f}%" if r is not None else "   —  ")
            p(f"  {d} → 台股 {days[i]}  " + " ".join(cells) + f"  {tag}")
        for h in HS:
            a = rows[h]
            sims = [statistics.mean(fwd(rnd.choice(pool), h) for _ in a) for _ in range(5000)]
            pct = sum(x <= statistics.mean(a) for x in sims) / len(sims)
            p(f"  {h:>3}日：{len(a)} 次 平均 {statistics.mean(a):+.1f}% 中位 {statistics.median(a):+.1f}% 上漲 {sum(x > 0 for x in a)}/{len(a)}"
              f"  在隨機分布的百分位 {pct * 100:.0f}%（雙尾 p {2 * min(pct, 1 - pct):.2f}）")
        p("")
    text = "\n".join(out)
    print(text)
    with open(os.path.join(HERE, "結果_研究289_Fed首次升降息.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")


if __name__ == "__main__":
    main()
