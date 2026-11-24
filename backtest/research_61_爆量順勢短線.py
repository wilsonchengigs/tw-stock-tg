"""研究 61：爆量順勢短線（使用者描述的馬克羊方法：爆大量 → 順著那根 K 的方向做多／做空，有停損、停利）

日線版（台指期日內資料只有近 30 天，長期用加權指數日 K 近似台指期點數）：
- 訊號日：成交量 ≥ k × 前 20 日平均（量的來源：證交所成交金額，或台指期全月份成交口數）
- 方向：訊號日收紅（收盤 > 開盤）做多、收黑做空；變形：用收盤 vs 前一天收盤；並要求實體 ≥ b%
- 進場：隔天開盤；出場：停損 s%、停利 t%（以進場價計）；同一天高低都碰到 → 保守先算停損；持有 H 天沒碰到就收盤出
- 成本：每筆來回 3 點（手續費＋期交稅＋滑價），換成 % ＝ 3／進場價
報表：筆數、勝率、平均賺／賠、每筆期望值（% 與以 2026 指數 4 萬點換算的點數、大台每點 200 元）、獲利因子、年交易數；
      多空分開、前後段分開；對照組：同訊號日但方向隨機（1000 次）、只做多
用法：python -X utf8 backtest/research_61_爆量順勢短線.py
"""
import csv
import itertools
import json
import os
import random
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
TW = timezone(timedelta(hours=8))

r = json.load(open(os.path.join(HERE, "TWII.json")))
q = r["indicators"]["quote"][0]
BARS = []
for t, o, h, lo, c in zip(r["timestamp"], q["open"], q["high"], q["low"], q["close"]):
    if o and h and lo and c and h >= lo:
        BARS.append((datetime.fromtimestamp(t, TW).strftime("%Y-%m-%d"), o, h, lo, c))
DAYS = [b[0] for b in BARS]
O = [b[1] for b in BARS]
H = [b[2] for b in BARS]
LO = [b[3] for b in BARS]
C = [b[4] for b in BARS]
N = len(BARS)

amt = {row["date"]: float(row["amount"]) for row in csv.DictReader(open(os.path.join(HERE, "turnover_daily.csv"), encoding="utf-8")) if row["amount"]}
txv = defaultdict(float)
for row in csv.DictReader(open(os.path.join(HERE, "tx_daily.csv"), encoding="utf-8")):
    try:
        txv[row["date"]] += float(row["volume"] or 0)
    except ValueError:
        pass
VOL = {"成交金額": [amt.get(d) for d in DAYS], "台指期口數": [txv.get(d) or None for d in DAYS]}
COST_PTS = 3.0


def vratio(v):
    out = [None] * N
    for i in range(21, N):
        xs = [v[k] for k in range(i - 20, i) if v[k]]
        if v[i] and len(xs) >= 16:
            out[i] = v[i] / (sum(xs) / len(xs))
    return out


VR = {k: vratio(v) for k, v in VOL.items()}


def signals(vsrc, k, dir_mode, body):
    out = []
    vr = VR[vsrc]
    for i in range(21, N - 1):
        if vr[i] is None or vr[i] < k:
            continue
        if dir_mode == "candle":
            move = C[i] / O[i] - 1
        else:
            move = C[i] / C[i - 1] - 1
        if abs(move) < body:
            continue
        out.append((i, 1 if move > 0 else -1))
    return out


def trade(i, d, s, t, hold):
    """訊號日 i、方向 d；回傳報酬（扣成本，% 以進場價計）"""
    e = i + 1
    px = O[e]
    stop = px * (1 - d * s)
    tgt = px * (1 + d * t)
    for j in range(e, min(e + hold, N)):
        hi, lo = H[j], LO[j]
        hit_stop = (lo <= stop) if d > 0 else (hi >= stop)
        hit_tgt = (hi >= tgt) if d > 0 else (lo <= tgt)
        if hit_stop:
            return -s - COST_PTS / px
        if hit_tgt:
            return t - COST_PTS / px
    j = min(e + hold, N) - 1
    return d * (C[j] / px - 1) - COST_PTS / px


def stats(rets):
    if not rets:
        return None
    w = [x for x in rets if x > 0]
    l_ = [x for x in rets if x <= 0]
    pf = sum(w) / -sum(l_) if l_ and sum(l_) < 0 else float("inf")
    return dict(n=len(rets), win=len(w) / len(rets), aw=statistics.mean(w) if w else 0, al=statistics.mean(l_) if l_ else 0,
                ev=statistics.mean(rets), pf=pf)


def fmt(st, years):
    if not st:
        return "無交易"
    return (f"{st['n']:4d} 筆（{st['n'] / years:4.1f}/年） 勝率 {st['win']:4.0%}  平均賺 {st['aw']:+.2%}／賠 {st['al']:+.2%}  "
            f"每筆期望 {st['ev']:+.3%}（≈{st['ev'] * 40000:+5.0f} 點，大台 {st['ev'] * 40000 * 200:+7,.0f} 元）  獲利因子 {st['pf']:.2f}")


def main():
    years = (datetime.fromisoformat(DAYS[-1]) - datetime.fromisoformat("1998-09-01")).days / 365.25
    rng = random.Random(61)
    L = ["研究 61：爆量順勢短線（日線近似；成本每筆 3 點；期望值點數以指數 40,000 換算）"]
    grid = []
    for vsrc, k, dm, body, s, t, hold in itertools.product(("成交金額", "台指期口數"), (1.5, 2.0, 2.5), ("candle", "close"), (0.0, 0.01),
                                                         (0.01, 0.02, 0.03), (0.02, 0.04, 0.06), (1, 3, 5, 10)):
        sig = [x for x in signals(vsrc, k, dm, body) if DAYS[x[0]] >= "1998-09-01"]
        rets = [trade(i, d, s, t, hold) for i, d in sig]
        st = stats(rets)
        if st and st["n"] >= 30:
            grid.append(((vsrc, k, dm, body, s, t, hold), st, sig))
    L.append(f"\n== 1. 全部 {len(grid)} 組設定（至少 30 筆）==")
    evs = sorted(g[1]["ev"] for g in grid)
    L.append(f"每筆期望值：中位 {evs[len(evs) // 2]:+.3%}、最好 {evs[-1]:+.3%}、最差 {evs[0]:+.3%}；期望值 > 0 的組數 {sum(e > 0 for e in evs)}/{len(evs)}")
    wins = sorted(g[1]["win"] for g in grid)
    L.append(f"勝率：中位 {wins[len(wins) // 2]:.0%}（範圍 {wins[0]:.0%}～{wins[-1]:.0%}）")
    L.append("\n期望值前 10 名：")
    for p, st, sig in sorted(grid, key=lambda x: -x[1]["ev"])[:10]:
        L.append(f"  {p[0]} ≥{p[1]}x {'K 棒' if p[2] == 'candle' else '漲跌'}{'、實體≥1%' if p[3] else ''} 停損 {p[4]:.0%} 停利 {p[5]:.0%} 最多 {p[6]} 天：{fmt(st, years)}")
    # 代表組：成交金額 2x、K 棒方向、停損 1%、停利 2%、最多 3 天
    rep = next(g for g in grid if g[0] == ("成交金額", 2.0, "candle", 0.0, 0.01, 0.02, 3)) if any(g[0] == ("成交金額", 2.0, "candle", 0.0, 0.01, 0.02, 3) for g in grid) else grid[0]
    p, st, sig = rep
    L.append(f"\n== 2. 代表組（{p[0]} ≥{p[1]}x、K 棒方向、停損 {p[4]:.0%}、停利 {p[5]:.0%}、最多 {p[6]} 天）==")
    L.append("全部：" + fmt(st, years))
    for nm, sel in (("做多", lambda x: x[1] > 0), ("做空", lambda x: x[1] < 0),
                    ("1998-2012", lambda x: DAYS[x[0]] < "2013"), ("2013-2026", lambda x: DAYS[x[0]] >= "2013")):
        sub = [x for x in sig if sel(x)]
        L.append(f"{nm:9s}：" + fmt(stats([trade(i, d, p[4], p[5], p[6]) for i, d in sub]), years))
    # 對照：同訊號日隨機方向
    rand_ev = []
    for _ in range(1000):
        rr = [trade(i, rng.choice((1, -1)), p[4], p[5], p[6]) for i, _d in sig]
        rand_ev.append(statistics.mean(rr))
    rand_ev.sort()
    pval = (sum(x >= st["ev"] for x in rand_ev) + 1) / 1001
    L.append(f"對照：同樣訊號日、方向隨機 1000 次，每筆期望中位 {rand_ev[500]:+.3%}、95 分位 {rand_ev[950]:+.3%}；順勢方向 p＝{pval:.3f}")
    L.append("對照：同樣訊號日一律做多：" + fmt(stats([trade(i, 1, p[4], p[5], p[6]) for i, _d in sig]), years))
    L.append("對照：同樣訊號日一律做空：" + fmt(stats([trade(i, -1, p[4], p[5], p[6]) for i, _d in sig]), years))
    # 全部設定對隨機方向的檢定（只看順勢是否勝過反向）
    better = sum(1 for g in grid if g[1]["ev"] > stats([trade(i, -d, g[0][4], g[0][5], g[0][6]) for i, d in g[2]])["ev"])
    L.append(f"\n全部設定中，順勢方向期望值 > 反向（逆勢）的組數：{better}/{len(grid)}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究61_爆量順勢短線.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
