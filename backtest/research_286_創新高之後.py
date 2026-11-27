"""研究 286：加權創歷史新高／250 日新高之後

資料：1990～1997-06 用 taiex_1990_1997.csv，之後用 strategy_v3 的 PX（加權收盤，價格指數、不含息）。
事件：
  ATH＝收盤 > 之前所有收盤（1990 起算；1990-02 的 12,682 到 2020 才被突破）
  H250＝收盤 > 前 250 個交易日最高（2000 起）
  ATH 首日＝距上一次 ATH ≥ 250 個交易日後的第一次（「睽違多年再創新高」）
報酬：事件日收盤 → 5／20／60／250 日後收盤（bp），重疊不去除（平均值不受影響，但勝率與 t 會高估，所以用分組比較）。
對照：同期間「近 60 日漲幅在同一個五分位」的非事件日——排除「新高只是代表最近漲很多」的動能效果。
用法：python -X utf8 backtest/research_286_創新高之後.py
"""
import csv
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import strategy_v3 as s  # noqa: E402

HS = (5, 20, 60, 250)


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
    ath, h250, ath_first = [], [], []
    hi, last_ath = P[0], -10 ** 9
    for i in range(1, n):
        if P[i] > hi:
            ath.append(i)
            if i - last_ath >= 250:
                ath_first.append(i)
            last_ath = i
            hi = P[i]
        if i >= 250 and days[i] >= "2000" and P[i] > max(P[i - 250:i]):
            h250.append(i)
    mom = [P[i] / P[i - 60] - 1 if i >= 60 else None for i in range(n)]
    out = []
    p = out.append
    p("研究 286：加權創新高之後（bp，價格指數）\n")

    def fwd(i, h):
        return (P[i + h] / P[i] - 1) * 1e4 if i + h < n else None

    def report(name, ev, start):
        ev = [i for i in ev if mom[i] is not None]
        evset = set(ev)
        pool = [i for i in range(60, n) if days[i] >= start and i not in evset and mom[i] is not None]
        # 動能五分位切點（同期間全部日子）
        allm = sorted(mom[i] for i in range(60, n) if days[i] >= start)
        cuts = [allm[int(len(allm) * q / 5)] for q in range(1, 5)]
        qof = lambda x: sum(x > c for c in cuts)  # noqa: E731
        p(f"【{name}】{len(ev)} 天（{start[:4]}～）")
        p("天期   事件 平均/中位/勝率        全部非事件平均   同動能五分位對照平均   差")
        for h in HS:
            a = [fwd(i, h) for i in ev if fwd(i, h) is not None]
            if not a:
                continue
            allb = [fwd(i, h) for i in pool if fwd(i, h) is not None]
            # 對照：依事件的動能分位分配權重
            ctrl = []
            for i in ev:
                if fwd(i, h) is None:
                    continue
                q = qof(mom[i])
                ctrl.append(q)
            byq = {q: [fwd(i, h) for i in pool if fwd(i, h) is not None and qof(mom[i]) == q] for q in range(5)}
            cm = statistics.mean(statistics.mean(byq[q]) for q in ctrl)
            p(f"{h:>4}日 {statistics.mean(a):+7.1f} {statistics.median(a):+7.1f} {sum(x > 0 for x in a) / len(a) * 100:4.0f}%"
              f"        {statistics.mean(allb):+7.1f}            {cm:+7.1f}          {statistics.mean(a) - cm:+7.1f}")
        p("")

    report("歷史新高 ATH", ath, "1990")
    report("250 日新高 H250", h250, "2000")
    p("睽違 ≥250 個交易日後的第一次 ATH：")
    for i in ath_first:
        p(f"  {days[i]} 收 {P[i]:,.0f}  " + "  ".join(
            f"{h}日 {fwd(i, h):+.0f}" if fwd(i, h) is not None else f"{h}日 —" for h in HS))
    # 依年份：ATH 天數與之後 60 日
    p("\nATH 依年份：天數、之後 60 日平均")
    yrs = sorted({days[i][:4] for i in ath})
    for y in yrs:
        a = [fwd(i, 60) for i in ath if days[i][:4] == y and fwd(i, 60) is not None]
        cnt = sum(days[i][:4] == y for i in ath)
        p(f"  {y} {cnt:>3} 天  60 日 {statistics.mean(a):+.0f}" if a else f"  {y} {cnt:>3} 天  60 日 —")
    text = "\n".join(out)
    print(text)
    with open(os.path.join(HERE, "結果_研究286_創新高之後.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")


if __name__ == "__main__":
    main()
