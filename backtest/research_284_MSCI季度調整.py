"""研究 284：MSCI 季度調整生效日前後的加權走勢

MSCI 季度／半年度調整在 2／5／8／11 月最後一個營業日收盤生效（被動資金在當天尾盤集合競價調整），E＝該月台股最後交易日。
窗格（加權收盤對收盤，bp）：PRE5＝E-6→E-1（調整前一週）、DAY＝E-1→E（生效日）、NEXT1＝E→E+1（隔天回補）、POST5＝E→E+5
對照：其他 8 個月份的最後交易日（同樣是月底，控制月底／月初效應）；月份標籤置換 5,000 次，4 窗格最小 p×4；分 2000–2012／2013～
用法：python -X utf8 backtest/research_284_MSCI季度調整.py
"""
import os
import random
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import strategy_v3 as s  # noqa: E402

DAYS, PX, N = s.DAYS, s.PX, s.N
KEYS = ["PRE5", "DAY", "NEXT1", "POST5"]


def main():
    rows = []
    for i in range(7, N - 6):
        if DAYS[i] < "2000-01-01" or DAYS[i][:7] == DAYS[i + 1][:7]:
            continue  # 只取每月最後交易日
        r = lambda a, b: (PX[b] / PX[a] - 1) * 1e4  # noqa: E731
        m = int(DAYS[i][5:7])
        rows.append((DAYS[i], m in (2, 5, 8, 11), {"PRE5": r(i - 6, i - 1), "DAY": r(i - 1, i),
                                                  "NEXT1": r(i, i + 1), "POST5": r(i, i + 5)}))
    out = []
    p = out.append
    p("研究 284：MSCI 季度調整生效日（2／5／8／11 月最後交易日）前後加權報酬（bp，未扣成本）\n")

    def block(sel, label):
        cb = [w for _, c, w in sel if c]
        ot = [w for _, c, w in sel if not c]
        labels = [c for _, c, _ in sel]
        rnd = random.Random(284)
        p(f"【{label}】MSCI 月底 {len(cb)} 次 vs 其他月底 {len(ot)} 次")
        p("窗格     MSCI 平均/中位/勝率          其他月底 平均/中位/勝率       差      置換 p")
        ps = []
        for k in KEYS:
            a = [w[k] for w in cb]
            b = [w[k] for w in ot]
            diff = statistics.mean(a) - statistics.mean(b)
            vals = [w[k] for _, _, w in sel]
            hit = 0
            for _ in range(5000):
                lab = labels[:]
                rnd.shuffle(lab)
                aa = [v for v, c in zip(vals, lab) if c]
                bb = [v for v, c in zip(vals, lab) if not c]
                hit += abs(statistics.mean(aa) - statistics.mean(bb)) >= abs(diff)
            ps.append(hit / 5000)
            wr = lambda xs: sum(x > 0 for x in xs) / len(xs) * 100  # noqa: E731
            p(f"{k:<7} {statistics.mean(a):+7.1f} {statistics.median(a):+7.1f} {wr(a):4.0f}%     "
              f"{statistics.mean(b):+7.1f} {statistics.median(b):+7.1f} {wr(b):4.0f}%   {diff:+7.1f}   {ps[-1]:.3f}")
        p(f"家族（最小 p×4）≈ {min(1, min(ps) * 4):.3f}\n")

    block(rows, "2000～2026")
    block([r for r in rows if r[0] < "2013"], "2000–2012")
    block([r for r in rows if r[0] >= "2013"], "2013～")
    p("依月份 DAY 平均（bp）：" + "  ".join(
        f"{m}月 {statistics.mean(w['DAY'] for d, _, w in rows if int(d[5:7]) == m):+.1f}" for m in (2, 5, 8, 11)))
    p("依月份 NEXT1 平均（bp）：" + "  ".join(
        f"{m}月 {statistics.mean(w['NEXT1'] for d, _, w in rows if int(d[5:7]) == m):+.1f}" for m in (2, 5, 8, 11)))
    for lab, sel in (("全期", lambda d: True), ("2013～", lambda d: d >= "2013")):
        p(f"PRE5 依月份（{lab}）：" + "  ".join(
            f"{m}月 {statistics.mean(w['PRE5'] for d, _, w in rows if int(d[5:7]) == m and sel(d)):+.0f}" for m in range(1, 13)))
    # 錨點平移：PRE5 視窗整體往前／後移 k 個交易日，MSCI 月 − 其他月的差（看是否只在生效日前一週才有）
    pos = {d: i for i, d in enumerate(DAYS)}
    p("PRE5 錨點平移（2013～，差＝MSCI 月 − 其他月，bp）：")
    for k in (-15, -10, -5, 0, 5, 10):
        a, b = [], []
        for d, c, _ in rows:
            i = pos[d] + k
            if d < "2013" or i - 6 < 0 or i >= N:
                continue
            (a if c else b).append((PX[i - 1] / PX[i - 6] - 1) * 1e4)
        p(f"  平移 {k:+3d} 日：{statistics.mean(a) - statistics.mean(b):+6.1f}")
    p("2013～ MSCI 月 PRE5 逐筆：" + " ".join(f"{d[2:7]}:{w['PRE5']:+.0f}" for d, c, w in rows if c and d >= "2013"))
    text = "\n".join(out)
    print(text)
    with open(os.path.join(HERE, "結果_研究284_MSCI季度調整.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")


if __name__ == "__main__":
    main()
