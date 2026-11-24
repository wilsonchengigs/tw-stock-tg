"""研究 15：跨市場濾網（費城半導體 SOX、Nasdaq-100、美元兌台幣）

想法：台股（尤其權值股）跟美國半導體高度連動，外資進出也反映在匯率上。
- A 進場濾網：美股指標也在均線上才進場
- B 強制出場：美股指標跌破均線也出場
- C 提早進場：台股站上 MA60（不含 1% 緩衝）且美股指標在均線上就先進
- D 匯率：台幣近 n 日升值（USD/TWD 跌）才進場／台幣急貶就出場
來源：台股與費半連動、外資匯率效應為常見的市場觀察（例：MoneyDJ、鉅亨網的盤後分析）；這裡只做驗證不預設結論
對照：同樣開啟比例的隨機閘門
對齊：台股週五用「前一晚美股收盤」；匯率用研究 09 清洗版（2004-03～，之前不套用匯率條件）
用法：python -X utf8 backtest/research_15_跨市場濾網.py
"""
import bisect
import importlib.util
import json
import os
import random
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.argv = [sys.argv[0], os.path.join(HERE, "vixtwn.csv")]
spec = importlib.util.spec_from_file_location("r05", os.path.join(HERE, "research_05_波動濾網.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
bt = R.bt
DAYS, PX, N = bt.DAYS, bt.PX, len(bt.DAYS)
NY = timezone(timedelta(hours=-5))
PER = {"全期": ("1998-01-01", "2026-12-31"), "前段": ("1998-01-01", "2012-12-31"), "後段": ("2013-01-01", "2026-12-31")}


def yload(name, tz=NY):
    r = json.load(open(os.path.join(HERE, name + ".json")))
    q = r["indicators"]["quote"][0]
    return {datetime.fromtimestamp(t, tz).strftime("%Y-%m-%d"): c for t, c in zip(r["timestamp"], q["close"]) if c and c > 0}


class Ext:
    def __init__(self, series, strict_before=True):
        self.d = sorted(series)
        self.p = [series[k] for k in self.d]
        f = bisect.bisect_left if strict_before else bisect.bisect_right
        self.idx = [f(self.d, x) - 1 for x in DAYS]
        self._ma = {}

    def ma(self, n):
        if n not in self._ma:
            out, s = [None] * len(self.p), 0.0
            for i, v in enumerate(self.p):
                s += v
                if i >= n:
                    s -= self.p[i - n]
                if i >= n - 1:
                    out[i] = s / n
            self._ma[n] = out
        return self._ma[n]

    def above(self, n, band=0.0):
        m = self.ma(n)

        def g(i):
            k = self.idx[i]
            return k >= n and m[k] is not None and self.p[k] > m[k] * (1 + band)
        return g

    def below(self, n, band=0.0):
        m = self.ma(n)

        def g(i):
            k = self.idx[i]
            return k >= n and m[k] is not None and self.p[k] < m[k] * (1 - band)
        return g

    def chg(self, n):
        def g(i):
            k = self.idx[i]
            return None if k < n else self.p[k] / self.p[k - n] - 1
        return g


SOX = Ext(yload("SOX"))
NDX = Ext(yload("NDX"))
_fx = yload("TWD", timezone(timedelta(hours=8)))
_fd = sorted(_fx)
_fv = [_fx[d] for d in _fd]
FX = Ext({d: sorted(_fv[max(0, k - 2):k + 3])[len(_fv[max(0, k - 2):k + 3]) // 2] for k, d in enumerate(_fd)}, strict_before=False)
M60 = bt.get_sma(60)


def cells(kw):
    out = [R.f(R.run(a, b, **kw)) for a, b in PER.values()]
    return " | ".join(out) + f" | 真實 {R.f(R.run(*R.REAL, real=True, **kw))}"


def main():
    L = ["研究 15：跨市場濾網（全期 1998- | 前段 -2012 | 後段 2013- | 真實 2015-09～；年化/最大回檔）"]
    base = [R.run(a, b) for a, b in PER.values()]
    base_r = R.run(*R.REAL, real=True)

    def ok(kw):
        rs = [R.run(a, b, **kw) for a, b in PER.values()]
        rr = R.run(*R.REAL, real=True, **kw)
        return (all(r["cagr"] >= q["cagr"] - 1e-9 for r, q in zip(rs, base)) and rs[0]["mdd"] > -0.5
                and rr["cagr"] >= base_r["cagr"] - 1e-9 and rr["mdd"] >= base_r["mdd"] - 0.03)

    def add(name, kw):
        L.append(f"{name:34s} {'★' if ok(kw) else ' '} {cells(kw)}")
        print(L[-1], flush=True)

    add("現行", {})
    for nm, ex in (("SOX", SOX), ("NDX", NDX)):
        L.append(f"\n== {nm} ==")
        for n in (50, 100, 150, 200):
            add(f"A {nm} > MA{n} 才進場", dict(entry_ok=ex.above(n)))
        for n in (50, 100, 150, 200):
            add(f"B {nm} < MA{n}x0.97 也出場", dict(force_exit=ex.below(n, 0.03)))
        for n in (50, 100, 200):
            add(f"C 台股>MA60 且 {nm}>MA{n} 提早進", dict(early_entry=(lambda g: (lambda i: PX[i] > M60[i] and g(i)))(ex.above(n))))
    L.append("\n== 台幣（USD/TWD）==")
    for n in (20, 60, 120):
        c = FX.chg(n)
        add(f"D 台幣近 {n} 日升值才進", dict(entry_ok=(lambda c: (lambda i: c(i) is None or c(i) < 0))(c)))
        for x in (0.02, 0.03):
            add(f"D 台幣近 {n} 日貶 > {x:.0%} 就出場", dict(force_exit=(lambda c, x: (lambda i: c(i) is not None and c(i) > x))(c, x)))
    L.append("\n== 對照：隨機進場閘門（開啟比例 50%／70%，30 次）==")
    for p in (0.5, 0.7):
        res = []
        for seed in range(30):
            rnd = random.Random(seed)
            gate = [rnd.random() < p for _ in range(N)]
            res.append(R.run(*PER["全期"], entry_ok=(lambda g: (lambda i: g[i]))(gate)))
        cs = sorted(r["cagr"] for r in res)
        ms = sorted(r["mdd"] for r in res)
        L.append(f"隨機 {p:.0%} 擋進場：全期年化中位數 {cs[15]:.1%}（{cs[0]:.1%}～{cs[-1]:.1%}），回檔中位數 {ms[15]:.1%}")
        print(L[-1], flush=True)
    out = "\n".join(L) + "\n"
    open(os.path.join(HERE, "結果_研究15_跨市場濾網.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
