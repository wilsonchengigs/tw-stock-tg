"""研究 287：美國大選前後的台股

選舉日＝11 月第一個週一之後的週二（美東）；台灣時間週三上午開票，台股反應在「週三」收盤。
偶數年＝大選（總統：1992、1996…2024；期中：1990、1994…2026），奇數年同規則的週三＝對照（同季節、沒有選舉）。
窗格（加權收盤，bp）：PRE20＝E-21→E-1（選前一個月）、REACT＝E-1→E（開票日）、POST20＝E→E+20、POST60＝E→E+60
另：總統任期週期（選後第 1～4 年，曆年加權報酬，1990～2025）
用法：python -X utf8 backtest/research_287_美國大選.py
"""
import csv
import datetime as dt
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import strategy_v3 as s  # noqa: E402


def load():
    px = {}
    for r in csv.DictReader(open(os.path.join(HERE, "taiex_1990_1997.csv"), encoding="utf-8")):
        px[r["date"]] = float(r["close"])
    for d, v in zip(s.DAYS, s.PX):
        px[d] = v
    days = sorted(px)
    return days, [px[d] for d in days]


def elec_wed(y):
    d = dt.date(y, 11, 1)
    while d.weekday() != 0:
        d += dt.timedelta(days=1)
    return (d + dt.timedelta(days=2)).isoformat()  # 週二選舉 → 台灣週三


def main():
    days, P = load()
    n = len(P)
    idx = lambda d: next(i for i, x in enumerate(days) if x >= d)  # noqa: E731
    out = []
    p = out.append
    p("研究 287：美國大選前後加權報酬（bp）\n")
    rows = []
    for y in range(1990, 2027):
        i = idx(elec_wed(y))
        if i < 22:
            continue
        g = lambda a, b: (P[b] / P[a] - 1) * 1e4 if b < n else None  # noqa: E731
        kind = "總統" if y % 4 == 0 else ("期中" if y % 2 == 0 else "對照")
        rows.append((y, kind, days[i], {"PRE20": g(i - 21, i - 1), "REACT": g(i - 1, i),
                                         "POST20": g(i, i + 20), "POST60": g(i, i + 60)}))
    p("年    類別  台股日       PRE20  REACT  POST20  POST60")
    for y, k, d, w in rows:
        p(f"{y}  {k}  {d}  " + " ".join(f"{w[x]:+6.0f}" if w[x] is not None else "    — " for x in ("PRE20", "REACT", "POST20", "POST60")))
    p("\n類別   次數   PRE20   REACT   POST20   POST60   （平均；REACT 另列 |絕對值| 平均）")
    for k in ("總統", "期中", "對照"):
        sel = [w for _, kk, _, w in rows if kk == k]
        cells = []
        for x in ("PRE20", "REACT", "POST20", "POST60"):
            v = [w[x] for w in sel if w[x] is not None]
            cells.append(f"{statistics.mean(v):+7.1f}")
        ab = statistics.mean(abs(w["REACT"]) for w in sel)
        p(f"{k}   {len(sel):>3}  " + " ".join(cells) + f"   |REACT| {ab:.0f}")
    # 簡單置換：選舉年（總統＋期中）vs 對照的 REACT、POST20 差
    import random
    rnd = random.Random(287)
    for x in ("REACT", "POST20", "POST60"):
        sel = [(k != "對照", w[x]) for _, k, _, w in rows if w[x] is not None]
        a = [v for c, v in sel if c]
        b = [v for c, v in sel if not c]
        diff = statistics.mean(a) - statistics.mean(b)
        vals = [v for _, v in sel]
        labs = [c for c, _ in sel]
        hit = 0
        for _ in range(5000):
            rnd.shuffle(labs)
            aa = [v for v, c in zip(vals, labs) if c]
            bb = [v for v, c in zip(vals, labs) if not c]
            hit += abs(statistics.mean(aa) - statistics.mean(bb)) >= abs(diff)
        p(f"選舉年 vs 對照 {x}：差 {diff:+.1f} bp，置換 p {hit / 5000:.3f}")
    # 任期週期
    p("\n總統任期週期（選後第 N 年的曆年加權報酬，1990～2025）")
    yr = {}
    for y in range(1990, 2026):
        a = max(i for i, d in enumerate(days) if d < f"{y}-01-01") if y > 1990 else 0
        b = max(i for i, d in enumerate(days) if d < f"{y + 1}-01-01")
        yr[y] = (P[b] / P[a] - 1) * 100
    for c in (1, 2, 3, 4):
        ys = [y for y in yr if (y - 1) % 4 == (c - 1) % 4 and y % 4 == c % 4]
        v = [yr[y] for y in ys]
        p(f"  第 {c} 年（{','.join(str(y)[2:] for y in ys)}）：平均 {statistics.mean(v):+.1f}%  中位 {statistics.median(v):+.1f}%  上漲 {sum(x > 0 for x in v)}/{len(v)}")
    # 任期週期置換：把 36 個年報酬的「週期標籤」整組循環平移（0～3 年）以外，再做隨機重排 10,000 次，
    # 統計量＝4 組平均的全距（最大−最小），家族檢定；另看「第 1 年」單組平均的單尾 p
    ys = sorted(yr)
    vals = [yr[y] for y in ys]
    lab = [((y - 1) % 4) + 1 for y in ys]  # 1993→第1年... 用 y%4：1=第1年,2=第2年,3=第3年,0=第4年
    lab = [{1: 1, 2: 2, 3: 3, 0: 4}[y % 4] for y in ys]

    def spread(lb):
        g = {c: [v for v, l in zip(vals, lb) if l == c] for c in (1, 2, 3, 4)}
        m = {c: statistics.mean(g[c]) for c in g}
        return max(m.values()) - min(m.values()), m[1]
    obs_sp, obs_1 = spread(lab)
    h_sp = h_1 = 0
    T = 10000
    for _ in range(T):
        lb = lab[:]
        rnd.shuffle(lb)
        sp, m1 = spread(lb)
        h_sp += sp >= obs_sp
        h_1 += m1 >= obs_1
    p(f"  置換 10,000 次：4 組全距 {obs_sp:.1f}pp 的 p＝{h_sp / T:.3f}；第 1 年平均 ≥{obs_1:.1f}% 的單尾 p＝{h_1 / T:.3f}"
      f"（第 1 年是看結果才挑的，要看家族 p）")
    up_all = sum(v > 0 for v in vals)
    p(f"  全部 36 年上漲 {up_all} 年；隨機 9 年全部上漲的機率 ≈ {statistics.mean([1.0]) * 0 + __import__('math').comb(up_all, 9) / __import__('math').comb(36, 9):.3f}")
    for lab2, lo, hi in (("1990–2007", 1990, 2007), ("2008–2025", 2008, 2025)):
        p(f"  {lab2}：" + "  ".join(
            f"第{c}年 {statistics.mean(yr[y] for y in yr if lo <= y <= hi and {1: 1, 2: 2, 3: 3, 0: 4}[y % 4] == c):+.1f}%"
            for c in (1, 2, 3, 4)))
    # 主策略 v3（2x，2002～）依週期年的曆年報酬
    _, _, curve = s.run("2002-01-01", s.DAYS[-1], curve=True)
    i0 = next(i for i, d in enumerate(s.DAYS) if d >= "2002-01-01")
    cv = dict(zip(s.DAYS[i0:i0 + len(curve)], curve))
    cd = sorted(cv)
    p("  主策略 v3（2002～2025）依週期年：")
    vy = {}
    for y in range(2002, 2026):
        a = [d for d in cd if d < f"{y}-01-01"]
        b = [d for d in cd if d < f"{y + 1}-01-01"]
        if a and b:
            vy[y] = (cv[b[-1]] / cv[a[-1]] - 1) * 100
    for c in (1, 2, 3, 4):
        v = [vy[y] for y in vy if {1: 1, 2: 2, 3: 3, 0: 4}[y % 4] == c]
        p(f"    第 {c} 年：平均 {statistics.mean(v):+.1f}%（{len(v)} 年，上漲 {sum(x > 0 for x in v)}）")
    text = "\n".join(out)
    print(text)
    with open(os.path.join(HERE, "結果_研究287_美國大選.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")


if __name__ == "__main__":
    main()
