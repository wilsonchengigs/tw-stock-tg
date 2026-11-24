"""研究 71：台指期正逆價差（AI-1：期貨）

價差＝台指期近月日盤收盤 ÷ 加權指數收盤 − 1（期貨 13:45 收、現貨 13:30 收，有 15 分鐘落差，當雜訊）
季節性：6～9 月除息旺季近月有結構性逆價差 → 扣掉「過去 3 年同一個月份的價差中位數」得到「異常價差」（只用過去資料）
另看：距到期天數長的時候價差較大 → 再除以「到期剩餘交易日」的平方根做標準化（敏感度）
1. 事件研究：異常價差 z（相對過去 250 日）< -2（深度逆價差＝恐慌／避險）或 > +2 之後 5／10／20 日加權報酬，去叢集 10 日；
   對照所有日子；分 1998-2012／2013-2026；依多空（加權 > MA60）分組
2. 交易：深度逆價差隔天開盤買台指期抱 10 天；隨機進場對照
用法：python -X utf8 backtest/research_71_台指期正逆價差.py
"""
import importlib.util
import os
import random
import statistics


def fmean(xs):
    xs = list(xs)
    return sum(xs) / len(xs)


def fstd(xs):
    m = fmean(xs)
    return (sum((x - m) ** 2 for x in xs) / len(xs)) ** 0.5
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("r63d", os.path.join(HERE, "research_63d_爆量收黑_台指期真實價.py"))
r63d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r63d)
r61 = r63d.r61
TWII = dict(zip(r61.DAYS, r61.C))
TWO = dict(zip(r61.DAYS, r61.O))


def main():
    dates, day, night, near = r63d.load()
    rng = random.Random(71)
    ds = [d for d in dates if d in TWII and d >= "1998-09-01"]
    idx = {d: i for i, d in enumerate(ds)}
    basis = []
    for d in ds:
        m = near[d]
        basis.append(day[d][m][3] / TWII[d] - 1)
    # 季節性：過去 3 年同月份中位數
    by_ym = defaultdict(list)
    for d, b in zip(ds, basis):
        by_ym[(int(d[:4]), int(d[5:7]))].append(b)
    abn = []
    for d, b in zip(ds, basis):
        y, mo = int(d[:4]), int(d[5:7])
        hist = [x for yy in (y - 1, y - 2, y - 3) for x in by_ym.get((yy, mo), [])]
        abn.append(b - statistics.median(hist) if len(hist) >= 20 else None)
    z = [None] * len(ds)
    for i in range(len(ds)):
        h = [x for x in abn[max(0, i - 250):i] if x is not None]
        if abn[i] is not None and len(h) >= 120:
            sd = fstd(h)
            z[i] = (abn[i] - fmean(h)) / sd if sd > 0 else None
    C = [TWII[d] for d in ds]
    ma60 = [None] * len(ds)
    for i in range(59, len(ds)):
        ma60[i] = sum(C[i - 59:i + 1]) / 60

    def fwd(i, h):
        return C[i + h] / C[i] - 1 if i + h < len(ds) else None

    L = ["研究 71：台指期正逆價差（近月日盤收盤 ÷ 加權收盤 − 1，扣除過去 3 年同月份中位數）"]
    L.append(f"最新 {ds[-1]}：原始價差 {basis[-1]:+.2%}、異常價差 {abn[-1]:+.2%}、z＝{z[-1]:+.2f}" if z[-1] is not None else "")
    base = {h: [x for i in range(len(ds)) if (x := fwd(i, h)) is not None] for h in (5, 10, 20)}
    bmean = {h: fmean(v) for h, v in base.items()}
    L.append("所有日子：" + "  ".join(f"{h}日 {bmean[h]:+.2%}" for h in base))
    for th, below in ((2.0, True), (1.5, True), (2.0, False), (1.5, False)):
        ev, last = [], -99
        for i in range(len(ds)):
            hit = z[i] is not None and (z[i] < -th if below else z[i] > th)
            if hit and i - last > 10:
                ev.append(i)
            if hit:
                last = i
        lab = f"{'逆' if below else '正'}價差異常 z {'<' if below else '>'} {'-' if below else '+'}{th}"
        L.append(f"\n== {lab}：{len(ev)} 次 ==")
        for nm, sel in (("全部", ev), ("1998-2012", [i for i in ev if ds[i] < "2013"]), ("2013-2026", [i for i in ev if ds[i] >= "2013"]),
                        ("多頭(>MA60)", [i for i in ev if ma60[i] and C[i] > ma60[i]]), ("空頭(≤MA60)", [i for i in ev if ma60[i] and C[i] <= ma60[i]])):
            cells = []
            for h in (5, 10, 20):
                v = [x for i in sel if (x := fwd(i, h)) is not None]
                if len(v) >= 5:
                    sims = [fmean(rng.choices(base[h], k=len(v))) for _ in range(2000)]
                    m_ = fmean(v)
                    p = (sum(abs(s - bmean[h]) >= abs(m_ - bmean[h]) for s in sims) + 1) / 2001
                    cells.append(f"{h}日 {m_:+.2%}（上漲 {sum(x > 0 for x in v) / len(v):.0%}，p {p:.2f}）")
            L.append(f"  {nm:10s} {len(sel):3d} 次  " + "  ".join(cells))
    # 交易：深度逆價差隔天開盤買、抱 10 天
    L.append("\n== 交易：異常逆價差 z<-2 → 隔天開盤買、抱 10 天（加權開盤近似；成本 3 點）==")
    for th in (1.5, 2.0, 2.5):
        trs, busy = [], -1
        for i in range(len(ds) - 11):
            if z[i] is not None and z[i] < -th and i + 1 > busy:
                e, x = i + 1, i + 10
                trs.append(C[x] / TWO[ds[e]] - 1 - 3 / TWO[ds[e]])
                busy = x
        pool = [C[i + 10] / TWO[ds[i + 1]] - 1 - 3 / TWO[ds[i + 1]] for i in range(len(ds) - 11)]
        rnd = sorted(fmean(rng.choices(pool, k=len(trs))) for _ in range(2000)) if trs else []
        if trs:
            ev_ = fmean(trs)
            L.append(f"  z<-{th}：{len(trs)} 筆 勝率 {sum(t > 0 for t in trs) / len(trs):.0%} 每筆 {ev_:+.2%}  隨機 {rnd[1000]:+.2%}  p＝{(sum(x >= ev_ for x in rnd) + 1) / 2001:.3f}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究71_正逆價差.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
