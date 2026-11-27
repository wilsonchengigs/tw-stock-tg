"""研究 282：央行理監事會前後的加權走勢

日期重建：3／6／9／12 月的第三個週四（官網新聞稿 2019-03-21、2024-03-21、2024-12-19、2025-09-18、2026-03-19 都符合），
收盤後約 16:00 公布 → 反應在下一個交易日。2000-01 起；該週四休市就順延到下一個交易日當「會議日」。
窗格（加權收盤對收盤，做多扣 6 點約 0.03%；以報酬 bp 呈現，未扣成本）：
  PRE3＝會議日前 3 個交易日收盤 → 會議日收盤（卡位）
  REACT＝會議日收盤 → 下一個交易日收盤（消息反應）
  POST5＝下一個交易日收盤 → 再 5 個交易日（漂移）
  ABS_REACT＝|REACT|（消息日是否波動較大）
安慰劑：其餘 8 個月份的第三個週四（同樣緊接第三個週三的台指期結算，也控制週四／週五星期效應）；
  兩組差異用置換檢定（月份標籤隨機重排 5,000 次），4 個窗格取最小 p 做家族校正；另分 2000–2012／2013～
注意：Fed FOMC 常在同一週（週三美國時間），台股週四／週五也同時反應 FOMC；研究 67 已測 FOMC 日線無優勢
用法：python -X utf8 backtest/research_282_央行理監事會.py
"""
import datetime as dt
import os
import random
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import strategy_v3 as s  # noqa: E402

DAYS, PX, N = s.DAYS, s.PX, s.N
POS = {d: i for i, d in enumerate(DAYS)}


def third_thu(y, m):
    d = dt.date(y, m, 1)
    d += dt.timedelta(days=(3 - d.weekday()) % 7)
    return d + dt.timedelta(days=14)


def anchor(y, m):
    d = third_thu(y, m).isoformat()
    for i, x in enumerate(DAYS):
        if x >= d:
            return i
    return None


def wins(i):
    if i is None or i < 4 or i + 6 >= N:
        return None
    r = lambda a, b: (PX[b] / PX[a] - 1) * 1e4  # noqa: E731
    react = r(i, i + 1)
    return {"PRE3": r(i - 3, i), "REACT": react, "POST5": r(i + 1, i + 6), "ABS_REACT": abs(react)}


KEYS = ["PRE3", "REACT", "POST5", "ABS_REACT"]


def main():
    rows = []  # (year, month, is_cbc, wins)
    for y in range(2000, 2027):
        for m in range(1, 13):
            w = wins(anchor(y, m))
            if w:
                rows.append((y, m, m in (3, 6, 9, 12), w))
    out = []
    p = out.append
    p("研究 282：央行理監事會（3／6／9／12 月第三個週四）前後加權報酬（bp，未扣成本）\n")

    def stats(sel, label):
        cb = [w for _, _, c, w in sel if c]
        ot = [w for _, _, c, w in sel if not c]
        p(f"【{label}】理監事會 {len(cb)} 次 vs 其他月份第三週四 {len(ot)} 次")
        p("窗格        理監事會 平均/中位/勝率         其他月份 平均/中位/勝率        差     置換 p(雙尾)")
        rnd = random.Random(282)
        labels = [c for _, _, c, _ in sel]
        ps = {}
        diffs = {}
        for k in KEYS:
            a = [w[k] for w in cb]
            b = [w[k] for w in ot]
            diff = statistics.mean(a) - statistics.mean(b)
            vals = [w[k] for _, _, _, w in sel]
            hit = 0
            T = 5000
            for _ in range(T):
                lab = labels[:]
                rnd.shuffle(lab)
                aa = [v for v, c in zip(vals, lab) if c]
                bb = [v for v, c in zip(vals, lab) if not c]
                hit += abs(statistics.mean(aa) - statistics.mean(bb)) >= abs(diff)
            ps[k] = hit / T
            diffs[k] = diff
            wr = lambda xs: sum(x > 0 for x in xs) / len(xs) * 100  # noqa: E731
            p(f"{k:<10} {statistics.mean(a):+7.1f} {statistics.median(a):+7.1f} {wr(a):4.0f}%     "
              f"{statistics.mean(b):+7.1f} {statistics.median(b):+7.1f} {wr(b):4.0f}%    {diff:+7.1f}   {ps[k]:.3f}")
        mn = min(ps.values())
        p(f"家族（4 窗格最小 p，Bonferroni）≈ {min(1.0, mn * 4):.3f}\n")
        return diffs, ps

    stats(rows, "2000～2026 全期")
    stats([r for r in rows if r[0] <= 2012], "2000–2012")
    stats([r for r in rows if r[0] >= 2013], "2013～")
    # 依季別：12 月（年底）與 3 月是否不同
    p("依月份 REACT 平均（bp）：" + "  ".join(
        f"{m}月 {statistics.mean(w['REACT'] for _, mm, _, w in rows if mm == m):+.1f}" for m in (3, 6, 9, 12)))
    text = "\n".join(out)
    print(text)
    with open(os.path.join(HERE, "結果_研究282_央行理監事會.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")


if __name__ == "__main__":
    main()
