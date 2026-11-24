"""研究 73：外資台指期淨未平倉「單日大幅變化」之後的短線報酬（AI-1：法人／期貨；研究 04 測的是當主策略濾網，這裡是短線事件）

資料：FinMind TaiwanFuturesInstitutionalInvestors（TX 大台，2018-06～2026-11；`backtest/tx_inst_oi.csv`）
外資淨未平倉＝多方未平倉口數 − 空方未平倉口數；單日變化 Δ 相對過去 250 日的 z-score（只用過去）
事件：Δz < −2（外資大加空）、Δz > +2（大回補／加多），去叢集 5 日；期交所 15:00 後公布 → 隔天開盤進
報酬：加權隔天開盤 → 第 1／5／10 日收盤；拔靴 p；分 2018-2021／2022-2026；同時看當天加權漲跌（外資常順著當天行情加減碼）
另：同時看投信、自營商
用法：python -X utf8 backtest/research_73_外資期貨未平倉單日變化.py
"""
import csv
import importlib.util
import os
import random
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("r61", os.path.join(HERE, "research_61_爆量順勢短線.py"))
r61 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r61)
DAYS, O, C = r61.DAYS, r61.O, r61.C
N = len(DAYS)


def fmean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def fstd(xs):
    m = fmean(xs)
    return (sum((x - m) ** 2 for x in xs) / len(xs)) ** 0.5


def main():
    net = defaultdict(dict)
    for r in csv.DictReader(open(os.path.join(HERE, "tx_inst_oi.csv"), encoding="utf-8")):
        net[r["investor"]][r["date"]] = int(r["long_oi"]) - int(r["short_oi"])
    idx = {d: i for i, d in enumerate(DAYS)}
    rng = random.Random(73)

    def fwd(i, h):
        e, x = i + 1, i + h
        return C[x] / O[e] - 1 if x < N else None

    L = ["研究 73：法人台指期淨未平倉單日變化 → 加權隔天開盤起的報酬（2018-06～2026-11）"]
    for inv in ("外資", "投信", "自營商"):
        s = net[inv]
        ds = [d for d in sorted(s) if d in idx]
        dlt = [None] + [s[ds[k]] - s[ds[k - 1]] for k in range(1, len(ds))]
        z = [None] * len(ds)
        for k in range(1, len(ds)):
            h = [x for x in dlt[max(1, k - 250):k] if x is not None]
            if len(h) >= 120:
                sd = fstd(h)
                z[k] = (dlt[k] - fmean(h)) / sd if sd > 0 else None
        pool = [i for d in ds if (i := idx[d]) + 11 < N]
        base = {h: [fwd(i, h) for i in pool] for h in (1, 5, 10)}
        bm = {h: fmean(v) for h, v in base.items()}
        L.append(f"\n==================== {inv} ====================")
        L.append(f"最新 {ds[-1]}：淨未平倉 {s[ds[-1]]:+,} 口、單日變化 {dlt[-1]:+,}、z {z[-1]:+.2f}")
        L.append("所有日子：" + "  ".join(f"{h}日 {bm[h]:+.2%}" for h in bm))
        for th, sign, nm in ((2.0, -1, "大加空（Δz<-2）"), (2.0, 1, "大回補／加多（Δz>+2）"), (1.5, -1, "Δz<-1.5"), (1.5, 1, "Δz>+1.5")):
            ev, last = [], -99
            for k in range(len(ds)):
                if z[k] is not None and sign * z[k] > th:
                    i = idx[ds[k]]
                    if i - last > 5:
                        ev.append(i)
                    last = i
            for lab, sel in (("全部", ev), ("2018-2021", [i for i in ev if DAYS[i] < "2022"]), ("2022-2026", [i for i in ev if DAYS[i] >= "2022"]),
                             ("當天收紅", [i for i in ev if C[i] > C[i - 1]]), ("當天收黑", [i for i in ev if C[i] < C[i - 1]])):
                cells = []
                for h in (1, 5, 10):
                    v = [y for i in sel if (y := fwd(i, h)) is not None]
                    if len(v) >= 8:
                        m_ = fmean(v)
                        sims = [fmean(rng.choices(base[h], k=len(v))) for _ in range(2000)]
                        p = (sum(abs(x - bm[h]) >= abs(m_ - bm[h]) for x in sims) + 1) / 2001
                        cells.append(f"{h}日 {m_:+.2%}（{sum(y > 0 for y in v) / len(v):.0%}，p {p:.2f}）")
                if cells:
                    L.append(f"  {nm:16s} {lab:8s} {len(sel):3d}  " + "  ".join(cells))
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究73_法人期貨未平倉變化.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
