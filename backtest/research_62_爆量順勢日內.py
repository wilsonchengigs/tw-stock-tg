"""研究 62：爆量順勢「日內」版（研究 61 的分鐘級版本；使用者描述的馬克羊方法）

資料：backtest/tx_1min.csv（期交所近 30 交易日逐筆 → 台指期近月 1 分 K，2026-10-12～11-23，29 天，日盤＋夜盤）
規則：
- K 棒：1 分 K 或 5 分 K（由 1 分 K 合成，每個盤別各自從開盤起算）
- 爆量：(roll) 量 ≥ k × 同盤別前 20 根平均（至少要有 20 根歷史，所以開盤前 20 根不出訊號）
        (tod)  量 ≥ k × 「前 5～N 個交易日同一時刻」的中位數（去掉開盤／收盤本來就大量的時段效應；只用過去資料）
- 方向：該根收紅（收 > 開）做多、收黑做空；收平不做
- 進場：下一根開盤；出場：停損 s 點、停利 t 點（進場價起算），同一根都碰到 → 保守算停損；
        最多持有 H 分鐘，或盤別結束前最後一根收盤強制出場（不留倉）
- 一次只有一個部位（持倉中出現的訊號略過）
- 成本：每筆來回 4 點（大台手續費＋期交稅≈2 點、滑價 1 點×2），另測 2／6 點
報表：筆數、勝率、每筆期望（點、大台元＝點×200）；多空分開；前後半段分開；
      對照：同訊號反向、同訊號隨機方向（格點最佳值的隨機分布）、同時點一律做空／做多
注意：這 29 天台指從約 49,000 跌到 36,000（-27%），是很強的空頭，做空本來就容易賺
用法：python -X utf8 backtest/research_62_爆量順勢日內.py
"""
import csv
import itertools
import os
import random
import statistics
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
COST = 4.0


def load():
    sess = defaultdict(list)  # (trade_day, session) -> [(ts, o, h, l, c, v)]
    for r in csv.DictReader(open(os.path.join(HERE, "tx_1min.csv"), encoding="utf-8")):
        sess[(r["trade_day"], r["session"])].append((r["ts"], float(r["open"]), float(r["high"]), float(r["low"]),
                                                     float(r["close"]), float(r["volume"])))
    for k in sess:
        sess[k].sort()
    return sess


def resample(bars, m):
    if m == 1:
        return bars
    out = []
    for g in range(0, len(bars), m):
        ch = bars[g:g + m]
        out.append((ch[0][0], ch[0][1], max(b[2] for b in ch), min(b[3] for b in ch), ch[-1][4], sum(b[5] for b in ch)))
    return out


def build(sess, m):
    """回傳 {session: [(day, bars, slot_index_list)]}，bars 為 m 分 K"""
    out = defaultdict(list)
    for (day, s), bars in sorted(sess.items()):
        out[s].append((day, resample(bars, m)))
    return out


def vol_ratio(days, mode, look=20, min_hist=5):
    """days: [(day, bars)] 同一盤別依日期排序；回傳每天每根的量比（None 表示不足）"""
    res = []
    hist = defaultdict(list)  # 時刻 HH:MM -> 過去各天的量
    for day, bars in days:
        vr = []
        for i, b in enumerate(bars):
            if mode == "roll":
                if i >= look:
                    base = sum(x[5] for x in bars[i - look:i]) / look
                    vr.append(b[5] / base if base > 0 else None)
                else:
                    vr.append(None)
            else:
                h = hist.get(b[0][-5:], [])
                if len(h) >= min_hist:
                    med = statistics.median(h)
                    vr.append(b[5] / med if med > 0 else None)
                else:
                    vr.append(None)
        res.append(vr)
        for b in bars:  # 當天結束後才加入歷史（只用過去）
            hist[b[0][-5:]].append(b[5])
    return res


def sim(bars, e, d, s, t, hold):
    """從 bars[e] 開盤進場，方向 d；回傳 (點數損益未扣成本, 出場 index)"""
    px = bars[e][1]
    stop = px - d * s
    tgt = px + d * t
    last = min(e + hold, len(bars)) - 1
    for j in range(e, last + 1):
        _ts, o, h, lo, c, _v = bars[j]
        if j > e:  # 開盤跳過停損／停利 → 以開盤成交
            if (d > 0 and o <= stop) or (d < 0 and o >= stop):
                return d * (o - px), j
            if (d > 0 and o >= tgt) or (d < 0 and o <= tgt):
                return d * (o - px), j
        if (d > 0 and lo <= stop) or (d < 0 and h >= stop):
            return -s, j
        if (d > 0 and h >= tgt) or (d < 0 and lo <= tgt):
            return t, j
    return d * (bars[last][4] - px), last


class Engine:
    def __init__(self, days):
        self.days = days
        self.cache = {}

    def outcome(self, di, e, d, s, t, hold):
        key = (di, e, d, s, t, hold)
        r = self.cache.get(key)
        if r is None:
            r = self.cache[key] = sim(self.days[di][1], e, d, s, t, hold)
        return r

    def run(self, sigs, s, t, hold, dir_fn=None):
        """sigs: [(di, i, d)] 依時間排序；一次一個部位。回傳 [(di, d, 點數)]"""
        out = []
        busy = (-1, -1)
        for di, i, d in sigs:
            e = i + 1
            if e >= len(self.days[di][1]):
                continue
            if (di, e) <= busy:
                continue
            if dir_fn is not None:
                d = dir_fn(di, i, d)
            pnl, j = self.outcome(di, e, d, s, t, hold)
            busy = (di, j)
            out.append((di, d, pnl))
        return out


def summ(trs, cost=COST):
    if not trs:
        return None
    p = [x[2] - cost for x in trs]
    w = [x for x in p if x > 0]
    return dict(n=len(p), win=len(w) / len(p), ev=statistics.mean(p), sum=sum(p))


def fmt(st):
    if not st:
        return "無交易"
    return f"{st['n']:4d} 筆 勝率 {st['win']:4.0%} 每筆 {st['ev']:+6.1f} 點（大台 {st['ev'] * 200:+7,.0f} 元） 累計 {st['sum']:+7.0f} 點"


def main():
    sess = load()
    rng = random.Random(62)
    L = ["研究 62：爆量順勢日內版（台指期近月 1 分 K，2026-10-12～11-23，29 個交易日；成本每筆 4 點；大台每點 200 元）"]
    allday = sorted({k[0] for k in sess})
    L.append(f"期間台指期：{sess[(allday[0], 'day')][0][1]:.0f} → {sess[(allday[-1], 'day')][-1][4]:.0f}（強烈空頭）")
    grid_params = list(itertools.product((1, 5), ("roll", "tod"), (3.0, 5.0, 8.0), (20, 40, 80), (40, 80, 160), (15, 60, 999)))
    results = {}
    engines = {}
    sigsets = {}
    for session in ("day", "night"):
        for m in (1, 5):
            days = build(sess, m)[session]
            eng = engines[(session, m)] = Engine(days)
            for mode in ("roll", "tod"):
                vr = vol_ratio(days, mode)
                for k in (3.0, 5.0, 8.0):
                    sigs = []
                    for di, (day, bars) in enumerate(days):
                        for i, b in enumerate(bars):
                            if vr[di][i] is not None and vr[di][i] >= k and b[4] != b[1]:
                                sigs.append((di, i, 1 if b[4] > b[1] else -1))
                    sigsets[(session, m, mode, k)] = sigs
        for p in grid_params:
            m, mode, k, s, t, hold = p
            hold_bars = hold if hold == 999 else max(1, hold // m)
            eng = engines[(session, m)]
            trs = eng.run(sigsets[(session, m, mode, k)], s, t, hold_bars)
            results[(session, p)] = trs

    for session, nm in (("day", "日盤 08:45～13:45"), ("night", "夜盤 15:00～05:00")):
        L.append(f"\n==================== {nm} ====================")
        rows = [(p, summ(results[(session, p)])) for p in grid_params]
        rows = [(p, st) for p, st in rows if st and st["n"] >= 20]
        if not rows:
            L.append("沒有至少 20 筆的設定")
            continue
        evs = sorted(st["ev"] for _p, st in rows)
        wins = sorted(st["win"] for _p, st in rows)
        L.append(f"至少 20 筆的設定 {len(rows)} 組：每筆期望中位 {evs[len(evs) // 2]:+.1f} 點、最好 {evs[-1]:+.1f}、最差 {evs[0]:+.1f}；"
                 f">0 的 {sum(e > 0 for e in evs)} 組；勝率中位 {wins[len(wins) // 2]:.0%}（{wins[0]:.0%}～{wins[-1]:.0%}）")
        for c in (2.0, 6.0):
            e2 = sorted(summ(results[(session, p)], c)["ev"] for p, _ in rows)
            L.append(f"  成本改 {c:.0f} 點：中位 {e2[len(e2) // 2]:+.1f} 點、>0 的 {sum(x > 0 for x in e2)} 組")
        L.append("\n期望值前 8 名（K 週期／量比方式／倍數／停損／停利／最多分鐘）：")
        for p, st in sorted(rows, key=lambda x: -x[1]["ev"])[:8]:
            trs = results[(session, p)]
            lo = summ([x for x in trs if x[1] > 0])
            sh = summ([x for x in trs if x[1] < 0])
            L.append(f"  {p[0]}分K {p[1]:4s} ≥{p[2]:.0f}x 損{p[3]} 利{p[4]} {'收盤' if p[5] == 999 else str(p[5]) + '分'}：{fmt(st)}")
            L.append(f"      做多 {fmt(lo)}")
            L.append(f"      做空 {fmt(sh)}")
        # 代表組：最直覺的設定
        rep = (1, "tod", 5.0, 40, 80, 60)
        L.append(f"\n代表組（1 分 K、同時刻量比 ≥5x、停損 40、停利 80、最多 60 分）：")
        trs = results[(session, rep)]
        L.append("  順勢：" + fmt(summ(trs)))
        L.append("  做多：" + fmt(summ([x for x in trs if x[1] > 0])))
        L.append("  做空：" + fmt(summ([x for x in trs if x[1] < 0])))
        half = len(allday) // 2
        eng = engines[(session, rep[0])]
        dname = [d for d, _b in eng.days]
        L.append("  前半段：" + fmt(summ([x for x in trs if dname[x[0]] < allday[half]])))
        L.append("  後半段：" + fmt(summ([x for x in trs if dname[x[0]] >= allday[half]])))

        # 對照：全格點 順勢 vs 逆勢 vs 一律做空／做多
        L.append("\n全格點對照（同樣的訊號時點）：")
        cmp_ = {"順勢": [], "逆勢": [], "一律做多": [], "一律做空": []}
        for p, st in rows:
            m, mode, k, s, t, hold = p
            hb = hold if hold == 999 else max(1, hold // m)
            eng = engines[(session, m)]
            sg = sigsets[(session, m, mode, k)]
            cmp_["順勢"].append(st["ev"])
            cmp_["逆勢"].append(summ(eng.run(sg, s, t, hb, lambda di, i, d: -d))["ev"])
            cmp_["一律做多"].append(summ(eng.run(sg, s, t, hb, lambda di, i, d: 1))["ev"])
            cmp_["一律做空"].append(summ(eng.run(sg, s, t, hb, lambda di, i, d: -1))["ev"])
        for nm2, xs in cmp_.items():
            xs = sorted(xs)
            L.append(f"  {nm2:6s}：每筆期望中位 {xs[len(xs) // 2]:+6.1f} 點、>0 的 {sum(x > 0 for x in xs):3d}/{len(xs)}")
        beat = sum(1 for a, b in zip(cmp_["順勢"], cmp_["逆勢"]) if a > b)
        L.append(f"  順勢勝過逆勢的組數 {beat}/{len(rows)}")

        # 多重比較：隨機方向下的格點最佳值
        reps = 200
        bests, meds = [], []
        for _ in range(reps):
            flips = {}

            def fn(di, i, d):
                key = (di, i)
                if key not in flips:
                    flips[key] = rng.choice((1, -1))
                return flips[key]
            e = []
            for p, _st in rows:
                m, mode, k, s, t, hold = p
                hb = hold if hold == 999 else max(1, hold // m)
                # 同一根 K 在 1 分／5 分是不同時點，各自隨機；同一設定族共用 flips
                e.append(summ(engines[(session, m)].run(sigsets[(session, m, mode, k)], s, t, hb, fn))["ev"])
            bests.append(max(e))
            meds.append(statistics.median(e))
        bests.sort()
        meds.sort()
        L.append(f"\n隨機方向 {reps} 次：格點最佳值中位 {bests[reps // 2]:+.1f}、95 分位 {bests[int(reps * .95)]:+.1f} 點；"
                 f"格點中位的中位 {meds[reps // 2]:+.1f}、95 分位 {meds[int(reps * .95)]:+.1f}")
        L.append(f"實際：格點最佳 {evs[-1]:+.1f}（p＝{(sum(b >= evs[-1] for b in bests) + 1) / (reps + 1):.3f}）、"
                 f"格點中位 {evs[len(evs) // 2]:+.1f}（p＝{(sum(m_ >= evs[len(evs) // 2] for m_ in meds) + 1) / (reps + 1):.3f}）")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究62_爆量順勢日內.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
