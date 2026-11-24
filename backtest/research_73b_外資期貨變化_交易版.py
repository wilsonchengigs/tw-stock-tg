"""研究 73b：研究 73 的可交易版——外資台指期淨未平倉單日大變化，隔天開盤跟著做（台指期近月真實價，2018-06～）

規則：外資 Δz > +x → 隔天日盤開盤買；Δz < −x → 隔天開盤放空；抱 H 個交易日後收盤平；持有中訊號略過；成本 3 點
x＝1.5／2.0／2.5；H＝1／5／10；只做多／只做空／多空都做
對照：同筆數、同方向分布、隨機日期 2000 次；分 2018-2021／2022-2026
另：研究 64b 的加碼訊號（成交金額 ≥1.5x 收黑、現行在場）當天的外資 Δz 分組，看「外資大加空的爆量收黑」是否較差
用法：python -X utf8 backtest/research_73b_外資期貨變化_交易版.py
"""
import csv
import importlib.util
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


r63d = load("r63d", "research_63d_爆量收黑_台指期真實價.py")


def fmean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def fstd(xs):
    m = fmean(xs)
    return (sum((x - m) ** 2 for x in xs) / len(xs)) ** 0.5


def main():
    dates, day, night, near = r63d.load()
    n = len(dates)
    fidx = {d: i for i, d in enumerate(dates)}
    # 連續收盤報酬（換月接續）
    R = [0.0] * n
    for i in range(1, n):
        m = near[dates[i]]
        prev = day[dates[i - 1]].get(m)
        R[i] = day[dates[i]][m][3] / prev[3] - 1 if prev else 0.0
    net = {}
    for r in csv.DictReader(open(os.path.join(HERE, "tx_inst_oi.csv"), encoding="utf-8")):
        if r["investor"] == "外資":
            net[r["date"]] = int(r["long_oi"]) - int(r["short_oi"])
    ds = [d for d in sorted(net) if d in fidx]
    dlt = {ds[k]: net[ds[k]] - net[ds[k - 1]] for k in range(1, len(ds))}
    Z = {}
    hist = []
    for d in ds[1:]:
        if len(hist) >= 120:
            h = hist[-250:]
            sd = fstd(h)
            Z[d] = (dlt[d] - fmean(h)) / sd if sd > 0 else None
        hist.append(dlt[d])

    def trade(i, d_, H):
        e, x = i + 1, i + H
        if x >= n:
            return None
        m = near[dates[e]]
        px = day[dates[e]][m][0]
        g = day[dates[e]][m][3] / px
        for j in range(e + 1, x + 1):
            g *= 1 + R[j]
        return d_ * (g - 1) - 3 / px, x

    rng = random.Random(731)
    L = ["研究 73b：外資台指期淨未平倉單日大變化 → 隔天開盤跟著做（台指期近月真實價，2018-06～2026-11；成本 3 點）"]
    zi = [(fidx[d], z) for d, z in Z.items() if z is not None]
    zi.sort()
    pool = [i for i, _ in zi if i + 11 < n]
    for mode in ("多空", "只做多", "只做空"):
        L.append(f"\n== {mode} ==")
        for x in (1.5, 2.0, 2.5):
            for H in (1, 5, 10):
                cells = []
                for lab, lo, hi in (("全期", "2018", "2027"), ("2018-2021", "2018", "2022"), ("2022-2026", "2022", "2027")):
                    trs, dirs, busy = [], [], -1
                    for i, z in zi:
                        if not (lo <= dates[i] < hi) or i + 1 <= busy:
                            continue
                        d_ = 1 if z > x else (-1 if z < -x else 0)
                        if d_ == 0 or (mode == "只做多" and d_ < 0) or (mode == "只做空" and d_ > 0):
                            continue
                        t = trade(i, d_, H)
                        if t:
                            trs.append(t[0])
                            dirs.append(d_)
                            busy = t[1]
                    if len(trs) < 6:
                        cells.append(f"{lab} {len(trs)}筆")
                        continue
                    ev = fmean(trs)
                    pp = [i for i in pool if lo <= dates[i] < hi]
                    sims = []
                    for _ in range(1000):
                        sims.append(fmean(trade(rng.choice(pp), dd, H)[0] for dd in dirs))
                    p = (sum(s >= ev for s in sims) + 1) / 1001
                    cells.append(f"{lab} {len(trs):3d}筆 勝{sum(t > 0 for t in trs) / len(trs):3.0%} {ev:+.2%} p{p:.2f}")
                L.append(f"  x{x} H{H:2d}  " + " ｜ ".join(cells))
    # 與研究 64b 加碼訊號的交集
    amt = [r63d.AMT.get(d) for d in dates]
    r64 = load("r64", "research_64_爆量收黑加碼現行策略.py")
    st = dict(zip(r64.DAYS, r64.state_series()))
    L.append("\n== 研究 64b 加碼訊號（2018-06 後、現行在場）× 當天外資 Δz ==")
    grp = {"外資大加空 Δz<-1.5": [], "其他": []}
    for i in range(21, n - 11):
        d = dates[i]
        if d < "2018-06-01" or not st.get(d):
            continue
        xs = [amt[k] for k in range(i - 20, i) if amt[k]]
        if not amt[i] or len(xs) < 16 or amt[i] < 1.5 * fmean(xs) or R[i] >= 0:
            continue
        t = trade(i, 1, 10)
        if t is None:
            continue
        z = Z.get(d)
        grp["外資大加空 Δz<-1.5" if z is not None and z < -1.5 else "其他"].append((d, t[0], z))
    for k, v in grp.items():
        if v:
            L.append(f"  {k}：{len(v)} 次 平均 {fmean(x[1] for x in v):+.2%}  " + "、".join(f"{d}（{r:+.1%}，z{z:+.1f}）" for d, r, z in v if z is not None))
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究73b_外資期貨變化交易版.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
