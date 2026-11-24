"""研究 62b：爆量順勢日內版的「實戰化」變形（研究 62 是最機械的版本）

資料同研究 62（台指期近月 1 分 K，29 個交易日）。訊號變形：
  base   ：研究 62 原版（爆量 K 收紅做多／收黑做空）
  break  ：爆量 K 的收盤同時創當盤新高（做多）或新低（做空）——爆量突破
  confirm：爆量 K 之後下一根也同方向收（收 > 開 做多／收 < 開 做空），再下一根開盤進場
  maxvol ：該根是「開盤 15 分鐘後、到目前為止當盤最大量」且 ≥ k 倍
  event  ：只限夜盤美國數據時點（20:30、21:30、22:00、02:00 起 5 分鐘內）的爆量
出場：固定停損／停利＋最多持有；或「移動停損」（從進場後最有利價回吐 s 點出場，無停利，最晚盤別結束）
一次一個部位；成本每筆 4 點；對照：同訊號反向、同訊號隨機方向（格點最佳值與中位的分布）
用法：python -X utf8 backtest/research_62b_爆量日內變形.py
"""
import importlib.util
import itertools
import os
import random
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("r62", os.path.join(HERE, "research_62_爆量順勢日內.py"))
r62 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r62)
COST = 4.0
EVENT_HM = ("20:30", "21:30", "22:00", "02:00")


def sim_trail(bars, e, d, s):
    px = bars[e][1]
    best = px
    for j in range(e, len(bars)):
        _ts, o, h, lo, c, _v = bars[j]
        stop = best - d * s
        if j > e and ((d > 0 and o <= stop) or (d < 0 and o >= stop)):
            return d * (o - px), j
        if (d > 0 and lo <= stop) or (d < 0 and h >= stop):
            return d * (stop - px), j
        best = max(best, h) if d > 0 else min(best, lo)
    return d * (bars[-1][4] - px), len(bars) - 1


class Engine:
    def __init__(self, days):
        self.days = days
        self.cache = {}

    def outcome(self, di, e, d, ex):
        key = (di, e, d, ex)
        r = self.cache.get(key)
        if r is None:
            bars = self.days[di][1]
            r = sim_trail(bars, e, d, ex[1]) if ex[0] == "trail" else r62.sim(bars, e, d, ex[1], ex[2], ex[3])
            self.cache[key] = r
        return r

    def run(self, sigs, ex, dir_fn=None):
        out, busy = [], (-1, -1)
        for di, e, d in sigs:  # 這裡的 sigs 已是「進場 index」
            if e >= len(self.days[di][1]) or (di, e) <= busy:
                continue
            if dir_fn is not None:
                d = dir_fn(di, e, d)
            pnl, j = self.outcome(di, e, d, ex)
            busy = (di, j)
            out.append((di, d, pnl))
        return out


def make_signals(days, vr, k, kind, m):
    sigs = []
    for di, (_day, bars) in enumerate(days):
        hi, lo, maxv = -1e18, 1e18, 0.0
        skip = max(1, 15 // m)
        for i, b in enumerate(bars):
            ts, o, h, l_, c, v = b
            prev_hi, prev_lo, prev_maxv = hi, lo, maxv
            hi, lo = max(hi, h), min(lo, l_)
            if i >= skip:
                maxv = max(maxv, v)
            x = vr[di][i]
            if x is None or x < k or c == o:
                continue
            d = 1 if c > o else -1
            if kind == "base":
                sigs.append((di, i + 1, d))
            elif kind == "break":
                if (d > 0 and c > prev_hi) or (d < 0 and c < prev_lo):
                    sigs.append((di, i + 1, d))
            elif kind == "confirm":
                if i + 1 < len(bars):
                    n_ = bars[i + 1]
                    if (n_[4] - n_[1]) * d > 0:
                        sigs.append((di, i + 2, d))
            elif kind == "maxvol":
                if i >= skip and v > prev_maxv:
                    sigs.append((di, i + 1, d))
            elif kind == "event":
                hm = ts[-5:]
                if any(0 <= (int(hm[:2]) * 60 + int(hm[3:])) - (int(e_[:2]) * 60 + int(e_[3:])) < 5 for e_ in EVENT_HM):
                    sigs.append((di, i + 1, d))
    return sigs


def summ(trs, cost=COST):
    if not trs:
        return None
    p = [x[2] - cost for x in trs]
    return dict(n=len(p), win=sum(x > 0 for x in p) / len(p), ev=statistics.mean(p), sum=sum(p))


def main():
    sess = r62.load()
    rng = random.Random(622)
    exits = [("fix", 40, 80, 60), ("fix", 80, 160, 60), ("fix", 40, 160, 999), ("fix", 80, 160, 999), ("trail", 40), ("trail", 80)]
    L = ["研究 62b：爆量日內變形（台指期近月 1 分 K，29 個交易日；成本每筆 4 點；大台每點 200 元）",
         "出場代號：fix 停損/停利/最多分鐘（999＝到盤別結束），trail 移動停損點數"]
    for session, nm in (("day", "日盤"), ("night", "夜盤")):
        L.append(f"\n==================== {nm} ====================")
        L.append("變形     組數  每筆期望中位  最好    >0組  勝率中位 | 逆勢中位  順>逆 | 隨機方向下：最佳 p  中位 p")
        for kind in ("base", "break", "confirm", "maxvol", "event"):
            if kind == "event" and session == "day":
                continue
            rows = []
            for m in (1, 5):
                days = r62.build(sess, m)[session]
                eng = Engine(days)
                for mode in ("roll", "tod"):
                    vr = r62.vol_ratio(days, mode)
                    for k in ((2.0, 3.0) if kind in ("event", "maxvol") else (3.0, 5.0)):
                        sg = make_signals(days, vr, k, kind, m)
                        for ex in exits:
                            ex2 = ex if ex[0] == "trail" or ex[3] == 999 else (ex[0], ex[1], ex[2], max(1, ex[3] // m))
                            st = summ(eng.run(sg, ex2))
                            if st and st["n"] >= 15:
                                rows.append(((m, mode, k, ex), st, eng, sg, ex2))
            if not rows:
                L.append(f"{kind:8s} 沒有至少 15 筆的設定")
                continue
            evs = sorted(r[1]["ev"] for r in rows)
            wins = sorted(r[1]["win"] for r in rows)
            rev = [summ(eng.run(sg, ex2, lambda di, e, d: -d))["ev"] for _p, _st, eng, sg, ex2 in rows]
            better = sum(1 for r, rv in zip(rows, rev) if r[1]["ev"] > rv)
            bests, meds = [], []
            for _ in range(150):
                flips = {}

                def fn(di, e, d):
                    return flips.setdefault((id(fn), di, e), rng.choice((1, -1)))
                xs = [summ(eng.run(sg, ex2, fn))["ev"] for _p, _st, eng, sg, ex2 in rows]
                bests.append(max(xs))
                meds.append(statistics.median(xs))
            med = evs[len(evs) // 2]
            pb = (sum(b >= evs[-1] for b in bests) + 1) / 151
            pm = (sum(x >= med for x in meds) + 1) / 151
            L.append(f"{kind:8s} {len(rows):4d}  {med:+7.1f} 點  {evs[-1]:+6.1f}  {sum(e > 0 for e in evs):3d}   {wins[len(wins) // 2]:4.0%}   | "
                     f"{sorted(rev)[len(rev) // 2]:+6.1f}  {better:3d}/{len(rows)} |  {pb:.2f}  {pm:.2f}")
            top = sorted(rows, key=lambda r: -r[1]["ev"])[:3]
            for p, st, eng, sg, ex2 in top:
                trs = eng.run(sg, ex2)
                lo_ = summ([x for x in trs if x[1] > 0])
                sh_ = summ([x for x in trs if x[1] < 0])
                L.append(f"    {p[0]}分K {p[1]:4s} ≥{p[2]:.0f}x {p[3]}：{st['n']} 筆 勝率 {st['win']:.0%} 每筆 {st['ev']:+.1f} 點"
                         f"（做多 {lo_['ev'] if lo_ else float('nan'):+.1f}／{lo_['n'] if lo_ else 0} 筆、做空 {sh_['ev'] if sh_ else float('nan'):+.1f}／{sh_['n'] if sh_ else 0} 筆）")
    L.append("\n讀法：p 是「隨機決定多空」時，格點最佳值／中位數 ≥ 實際值的比例；p 小（<0.05）才代表順勢方向真的有資訊")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究62b_爆量日內變形.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
