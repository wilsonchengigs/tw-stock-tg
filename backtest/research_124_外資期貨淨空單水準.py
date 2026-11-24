"""研究 124：外資台指期淨未平倉「水準」極端（相對過去 250 日 z）之後的報酬（研究 73 看單日變化，這裡看累積水準）
現況：2026-11-20 外資淨未平倉 -97,863 口（極端淨空）
事件：水準 z < −2（極端淨空）／> +2（極端淨多），去叢集 10 日；加權隔天開盤 → 5／10／20 日；拔靴 p；分 2018-2021／2022-2026
另：水準 z 分組（五分位）的之後 20 日平均
用法：python -X utf8 backtest/research_124_外資期貨淨空單水準.py
"""
import csv
import importlib.util
import os
import random

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
    net = {}
    for r in csv.DictReader(open(os.path.join(HERE, "tx_inst_oi.csv"), encoding="utf-8")):
        if r["investor"] == "外資":
            net[r["date"]] = int(r["long_oi"]) - int(r["short_oi"])
    idx = {d: i for i, d in enumerate(DAYS)}
    ds = [d for d in sorted(net) if d in idx]
    lv = [net[d] for d in ds]
    z = [None] * len(ds)
    for k in range(len(ds)):
        h = lv[max(0, k - 250):k]
        if len(h) >= 120:
            sd = fstd(h)
            z[k] = (lv[k] - fmean(h)) / sd if sd > 0 else None
    rng = random.Random(124)

    def fwd(i, h):
        e, x = i + 1, i + h
        return C[x] / O[e] - 1 if x < N else None

    pool = [idx[d] for d in ds if idx[d] + 21 < N]
    base = {h: [fwd(i, h) for i in pool] for h in (5, 10, 20)}
    bm = {h: fmean(v) for h, v in base.items()}
    L = ["研究 124：外資台指期淨未平倉水準 z（相對過去 250 日）→ 加權隔天開盤起報酬（2018-06～）",
         f"最新 {ds[-1]}：淨未平倉 {lv[-1]:+,} 口、水準 z {z[-1]:+.2f}",
         "所有日子：" + "  ".join(f"{h}日 {bm[h]:+.2%}" for h in bm)]
    for th, sign, nm in ((2.0, -1, "極端淨空 z<-2"), (1.5, -1, "淨空 z<-1.5"), (2.0, 1, "極端淨多 z>+2"), (1.5, 1, "淨多 z>+1.5")):
        ev, last = [], -99
        for k in range(len(ds)):
            if z[k] is not None and sign * z[k] > th:
                i = idx[ds[k]]
                if i - last > 10:
                    ev.append(i)
                last = i
        for lab, sel in (("全部", ev), ("2018-2021", [i for i in ev if DAYS[i] < "2022"]), ("2022-2026", [i for i in ev if DAYS[i] >= "2022"])):
            cells = []
            for h in (5, 10, 20):
                v = [y for i in sel if (y := fwd(i, h)) is not None]
                if len(v) >= 5:
                    m_ = fmean(v)
                    sims = [fmean(rng.choices(base[h], k=len(v))) for _ in range(2000)]
                    p = (sum(abs(x - bm[h]) >= abs(m_ - bm[h]) for x in sims) + 1) / 2001
                    cells.append(f"{h}日 {m_:+.2%}（{sum(y > 0 for y in v) / len(v):.0%}，p {p:.2f}）")
            L.append(f"  {nm:12s} {lab:9s} {len(sel):3d}  " + "  ".join(cells))
    # 五分位
    pairs = [(z[k], fwd(idx[d], 20)) for k, d in enumerate(ds) if z[k] is not None and fwd(idx[d], 20) is not None]
    pairs.sort()
    q = len(pairs) // 5
    L.append("\n水準 z 五分位 → 之後 20 日平均（每日樣本重疊，僅供參考）：")
    for j in range(5):
        seg = pairs[j * q:(j + 1) * q] if j < 4 else pairs[4 * q:]
        L.append(f"  第 {j + 1} 組 z {seg[0][0]:+.2f}～{seg[-1][0]:+.2f}：{fmean(x[1] for x in seg):+.2%}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究124_外資淨空單水準.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
