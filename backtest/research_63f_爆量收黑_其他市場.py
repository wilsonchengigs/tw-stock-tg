"""研究 63f：爆量收黑買進的「外部複製」——同樣規則套到其他市場，看是不是只在台股出現（只在台股 → 比較像巧合）

規則（與研究 63b 相同、參數不改）：量 ≥ k × 前 20 日均量且收盤 < 前收 → 隔天開盤買、抱 H 天收盤賣；持有中訊號略過
市場：^GSPC（1970～）、SPY、^NDX、QQQ、2330.TW、TSM（Yahoo 日 K 含量）；^TWII 用研究 61 的成交金額當對照
美股排除季度到期日（3／6／9／12 月第三個星期五，結算巨量）
成本：每筆 0.05%；檢定：(a) 同筆數同持有天數隨機進場 (b) 10 日內合併成段的 sign-flip（群聚校正）
用法：python -X utf8 backtest/research_63f_爆量收黑_其他市場.py
"""
import json
import os
import random
import statistics
from datetime import date, datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
COST = 0.0005


def load(fn, tz=-5):
    r = json.load(open(os.path.join(HERE, fn)))
    q = r["indicators"]["quote"][0]
    out = []
    for t, o, h, lo, c, v in zip(r["timestamp"], q["open"], q["high"], q["low"], q["close"], q["volume"]):
        if o and c and v and h and lo and o > 0:
            out.append((datetime.fromtimestamp(t, timezone(timedelta(hours=tz))).strftime("%Y-%m-%d"), o, c, float(v)))
    return out


def third_friday_quarter(d):
    y, m, dd = map(int, d.split("-"))
    if m not in (3, 6, 9, 12):
        return False
    x = date(y, m, dd)
    return x.weekday() == 4 and 15 <= dd <= 21


def test(bars, k, H, rng, us=True, lo="1900", hi="2100"):
    n = len(bars)
    D = [b[0] for b in bars]
    O = [b[1] for b in bars]
    C = [b[2] for b in bars]
    V = [b[3] for b in bars]
    sig = []
    for i in range(21, n - 1):
        if not (lo <= D[i] < hi):
            continue
        base = sum(V[i - 20:i]) / 20
        if base > 0 and V[i] >= k * base and C[i] < C[i - 1] and not (us and third_friday_quarter(D[i])):
            sig.append(i)
    trs, busy = [], -1
    for i in sig:
        e, x = i + 1, i + H
        if e <= busy or x >= n:
            continue
        trs.append((i, C[x] / O[e] - 1 - COST))
        busy = x
    if len(trs) < 8:
        return None
    rets = [r for _i, r in trs]
    ev = statistics.mean(rets)
    pool = [i for i in range(21, n - H - 1) if lo <= D[i] < hi]
    allr = [C[i + H] / O[i + 1] - 1 - COST for i in pool]
    bm = statistics.mean(allr)
    rnd = sorted(statistics.mean(rng.choice(allr) for _ in rets) for _ in range(2000))
    p = (sum(x >= ev for x in rnd) + 1) / 2001
    eps, last = [], -99
    for i, r in trs:
        if i - last > 10:
            eps.append([])
        eps[-1].append(r - bm)
        last = i
    seg = [statistics.mean(e) for e in eps]
    obs = statistics.mean(seg)
    sims = [statistics.mean(s * rng.choice((1, -1)) for s in seg) for _ in range(3000)]
    pc = (sum(x >= obs for x in sims) + 1) / 3001
    return dict(n=len(trs), win=sum(r > 0 for r in rets) / len(rets), ev=ev, bm=bm, p=p, segs=len(seg), pc=pc)


def main():
    rng = random.Random(636)
    L = ["研究 63f：爆量收黑買進的外部複製（量 ≥k×20 日均且收黑 → 隔天開盤買抱 H 天；成本 0.05%；美股排除季度到期日）",
         "欄位：筆數 勝率 每筆平均（同期任一天進場的平均） 隨機進場 p ｜ 段數 群聚校正 p"]
    import importlib.util
    spec = importlib.util.spec_from_file_location("r61", os.path.join(HERE, "research_61_爆量順勢短線.py"))
    r61 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(r61)
    tw = [(d, o, c, v) for d, o, c, v in zip(r61.DAYS, r61.O, r61.C, r61.VOL["成交金額"]) if v]
    mk = [("^TWII（成交金額，對照）", tw, False), ("^GSPC", load("GSPC.json"), True), ("SPY", load("SPY.json"), True),
          ("^NDX", load("NDX.json"), True), ("QQQ", load("QQQ.json"), True), ("2330.TW", load("2330.json", 8), False),
          ("TSM", load("TSM.json"), True)]
    for k in (1.5, 2.0):
        for H in (5, 10):
            L.append(f"\n== k={k}、抱 {H} 天 ==")
            for nm, bars, us in mk:
                for lab, lo, hi in (("全期", "1900", "2100"), ("2000 前", "1900", "2000"), ("2000-2012", "2000", "2013"), ("2013 後", "2013", "2100")):
                    r = test(bars, k, H, rng, us, lo, hi)
                    if r is None:
                        continue
                    flag = " ★" if r["p"] < 0.05 and r["pc"] < 0.05 else ""
                    L.append(f"  {nm:22s} {lab:9s} {r['n']:4d} 筆 勝率 {r['win']:4.0%} 每筆 {r['ev']:+.2%}（{r['bm']:+.2%}） p＝{r['p']:.3f} ｜ {r['segs']:3d} 段 p＝{r['pc']:.3f}{flag}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究63f_其他市場.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
