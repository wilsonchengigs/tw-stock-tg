"""研究 288：中國長假（陸股休市、台股照常）期間的台股

窗格（日曆日，近似；陸股實際休市日每年略有不同）：
  十一黃金週：10/1～10/7（2000～）
  五一長假：2000–2007 5/1～5/7；2008–2019 5/1～5/3；2020～ 5/1～5/5
問題：陸股休市時，台股（少了陸股情緒、外資亞洲部位集中到台韓）是否表現不同？
做法：每年一筆「窗格內台股交易日平均日報酬 − 同年同季節對照日平均」（對照＝9/15～10/31 或 4/15～5/31 窗格外的交易日），
  以年為單位做 t 檢定與符號檢定（避免同一年的日子互相不獨立）；另列窗格內累計報酬
用法：python -X utf8 backtest/research_288_中國黃金週.py
"""
import math
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import strategy_v3 as s  # noqa: E402

DAYS, PX, N = s.DAYS, s.PX, s.N
R = [None] + [(PX[i] / PX[i - 1] - 1) * 1e4 for i in range(1, N)]


def may_end(y):
    return 7 if y <= 2007 else (3 if y <= 2019 else 5)


def window(name, y):
    if name == "十一":
        return (f"{y}-10-01", f"{y}-10-07"), (f"{y}-09-15", f"{y}-10-31")
    return (f"{y}-05-01", f"{y}-05-{may_end(y):02d}"), (f"{y}-04-15", f"{y}-05-31")


def main():
    out = []
    p = out.append
    p("研究 288：中國長假（陸股休市）期間台股日報酬（bp）\n")
    for name in ("十一", "五一"):
        diffs, cums = [], []
        p(f"【{name}】年    窗格天數  窗格平均  對照平均   差     窗格累計")
        for y in range(2000, 2026 + (1 if name == "五一" else 0)):
            (a, b), (c, d) = window(name, y)
            inw = [i for i in range(1, N) if a <= DAYS[i] <= b]
            ctl = [i for i in range(1, N) if c <= DAYS[i] <= d and not (a <= DAYS[i] <= b)]
            if not inw or len(ctl) < 10:
                continue
            m1 = statistics.mean(R[i] for i in inw)
            m0 = statistics.mean(R[i] for i in ctl)
            cum = (PX[inw[-1]] / PX[inw[0] - 1] - 1) * 1e4
            diffs.append(m1 - m0)
            cums.append(cum)
            p(f"       {y}   {len(inw):>3}     {m1:+7.1f}   {m0:+7.1f}  {m1 - m0:+7.1f}   {cum:+7.0f}")
        mu = statistics.mean(diffs)
        sd = statistics.stdev(diffs)
        t = mu / (sd / math.sqrt(len(diffs)))
        pos = sum(x > 0 for x in diffs)
        # 雙尾符號檢定
        k = min(pos, len(diffs) - pos)
        sp = min(1.0, 2 * sum(math.comb(len(diffs), j) for j in range(k + 1)) / 2 ** len(diffs))
        p(f"  {len(diffs)} 年：差 平均 {mu:+.1f} bp／天、t {t:+.2f}；差 >0 {pos}/{len(diffs)}（符號檢定 p {sp:.3f}）；"
          f"窗格累計 平均 {statistics.mean(cums):+.0f} bp、中位 {statistics.median(cums):+.0f}、上漲 {sum(x > 0 for x in cums)}/{len(cums)}\n")
    # 安慰劑：每個月 1～7 日 vs 前月 15 日～當月底（窗格外），同統計量；10 月是否特別突出（月初效應）
    p("安慰劑：各月 1～7 日 vs 前月 15 日～當月底（窗格外），每年一筆差的平均 bp／天、差 >0 年數")
    res = {}
    for m in range(1, 13):
        diffs = []
        for y in range(2000, 2027):
            a, b = f"{y}-{m:02d}-01", f"{y}-{m:02d}-07"
            pm, py = (m - 1, y) if m > 1 else (12, y - 1)
            c, d = f"{py}-{pm:02d}-15", f"{y}-{m:02d}-31"
            inw = [i for i in range(1, N) if a <= DAYS[i] <= b]
            ctl = [i for i in range(1, N) if c <= DAYS[i] <= d and not (a <= DAYS[i] <= b)]
            if inw and len(ctl) >= 10:
                diffs.append(statistics.mean(R[i] for i in inw) - statistics.mean(R[i] for i in ctl))
        res[m] = (statistics.mean(diffs), sum(x > 0 for x in diffs), len(diffs))
    for m in range(1, 13):
        mu, pos, k = res[m]
        p(f"  {m:>2} 月：{mu:+6.1f}  {pos}/{k}" + ("  ← 十一" if m == 10 else ""))
    rank = 1 + sum(res[m][0] > res[10][0] for m in res if m != 10)
    others = [res[m][0] for m in res if m != 10]
    p(f"  10 月排名 {rank}/12；其他 11 個月平均 {statistics.mean(others):+.1f}（月初效應），10 月扣掉它後超額 {res[10][0] - statistics.mean(others):+.1f} bp／天")
    # 分兩段
    for lab, lo, hi in (("2000–2012", 2000, 2012), ("2013～", 2013, 2026)):
        dd = []
        for y in range(lo, hi + 1):
            (a, b), (c, d) = window("十一", y)
            inw = [i for i in range(1, N) if a <= DAYS[i] <= b]
            ctl = [i for i in range(1, N) if c <= DAYS[i] <= d and not (a <= DAYS[i] <= b)]
            if inw and len(ctl) >= 10:
                dd.append(statistics.mean(R[i] for i in inw) - statistics.mean(R[i] for i in ctl))
        p(f"  十一 {lab}：差 {statistics.mean(dd):+.1f} bp／天，>0 {sum(x > 0 for x in dd)}/{len(dd)}")
    text = "\n".join(out)
    print(text)
    with open(os.path.join(HERE, "結果_研究288_中國黃金週.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")


if __name__ == "__main__":
    main()
