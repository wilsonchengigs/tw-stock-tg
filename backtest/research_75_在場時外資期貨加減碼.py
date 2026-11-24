"""研究 75：現行策略在場（2x）時，依外資台指期淨未平倉單日大變化（研究 73）加減碼（2018-06～2026-11，只有 8 年）

A 加碼：Δz > +x（外資大回補／加多）→ 當天收盤（實務＝隔天開盤，期交所 15:00 公布）加 a 倍，抱 H 天
B 減碼：Δz < −x（外資大加空）→ 降到 1x，H 天後恢復
C A＋B
與研究 64b（爆量收黑加 1x 抱 10 天）並列；另看 A＋64b 合併
架構：研究 64b 的 bt 模擬（加權指數＋配息、2x 內扣、成本）；週期間 2018-06-05～2026-11-20
用法：python -X utf8 backtest/research_75_在場時外資期貨加減碼.py
"""
import csv
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("r64b", os.path.join(HERE, "research_64b_在場時爆量收黑加碼.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
bt, R, DAYS, WE, HOT, PX, VR, N = m.bt, m.R, m.DAYS, m.WE, m.HOT, m.PX, m.VR, m.N


def fmean(xs):
    xs = list(xs)
    return sum(xs) / len(xs)


def fstd(xs):
    mm = fmean(xs)
    return (sum((x - mm) ** 2 for x in xs) / len(xs)) ** 0.5


def zseries():
    net = {}
    for r in csv.DictReader(open(os.path.join(HERE, "tx_inst_oi.csv"), encoding="utf-8")):
        if r["investor"] == "外資":
            net[r["date"]] = int(r["long_oi"]) - int(r["short_oi"])
    ds = sorted(net)
    Z, hist = {}, []
    for k in range(1, len(ds)):
        dl = net[ds[k]] - net[ds[k - 1]]
        if len(hist) >= 120:
            h = hist[-250:]
            sd = fstd(h)
            Z[ds[k]] = (dl - fmean(h)) / sd if sd > 0 else None
        hist.append(dl)
    return Z


def sim(start, end, Z, x=None, add=0.0, Hadd=5, cut=False, Hcut=5, vol_add=0.0, Hvol=10):
    i0 = next(i for i, d in enumerate(DAYS) if d >= start)
    i1 = max(i for i, d in enumerate(DAYS) if d <= end)
    eq = peak = 1.0
    mdd = 0.0
    on, lev, pend = False, 0.0, None
    extra, until = 0.0, -1
    vextra, vuntil = 0.0, -1
    for i in range(i0, i1 + 1):
        if i > i0:
            Lv = max(lev + extra + vextra, 0.0)
            eq *= 1 + ((Lv * bt.R1[i] - max(Lv - 1, 0) * bt.DRAG / bt.TD) if Lv > 0 else bt.RC)
        if pend is not None:
            eq *= 1 - bt.COST * abs(pend - lev)
            lev, pend = pend, None
            if lev == 0:
                extra, until, vextra, vuntil = 0.0, -1, 0.0, -1
        if WE[i] and i >= 260:
            on = (not (PX[i] < R.M80[i] * 0.975 or HOT[i])) if on else (PX[i] > R.M60[i] * 1.01 and not HOT[i])
            want = 2.0 if on else 0.0
            if want != lev:
                pend = want
        if extra and i >= until:
            eq *= 1 - 0.0001 * abs(extra)
            extra, until = 0.0, -1
        if vextra and i >= vuntil:
            vextra, vuntil = 0.0, -1
        z = Z.get(DAYS[i])
        if x is not None and lev == 2.0 and pend is None and not extra and z is not None:
            if add and z > x:
                extra, until = add, i + Hadd
                eq *= 1 - 0.0001 * add
            elif cut and z < -x:
                extra, until = -1.0, i + Hcut
                eq *= 1 - 0.0001
        if vol_add and lev == 2.0 and pend is None and not vextra and VR[i] is not None and VR[i] >= 1.5 and PX[i] < PX[i - 1]:
            vextra, vuntil = vol_add, i + Hvol
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
    return eq ** (1 / ((i1 - i0) / bt.TD)) - 1, mdd


def main():
    Z = zseries()
    P = (("2018-06-05", "2026-12-31", "2018-2026"), ("2018-06-05", "2021-12-31", "2018-2021"), ("2022-01-01", "2026-12-31", "2022-2026"))
    L = ["研究 75：在場時依外資台指期大變化加減碼（bt 模擬；2018-06～）"]
    base = {nm: sim(s, e, Z) for s, e, nm in P}
    L.append("現行：" + "  ".join(f"{nm} {c:.1%}／{d:.1%}" for nm, (c, d) in base.items()))
    vol = {nm: sim(s, e, Z, vol_add=1.0) for s, e, nm in P}
    L.append("研究 64b（爆量收黑加 1x 抱 10 天）：" + "  ".join(f"{nm} {c:.1%}({c - base[nm][0]:+.1%})／{d:.1%}" for nm, (c, d) in vol.items()))
    for x in (1.5, 2.0):
        for nm2, kw in ((f"A 加 0.5x 抱5", dict(add=0.5, Hadd=5)), (f"A 加 1x 抱5", dict(add=1.0, Hadd=5)), (f"A 加 1x 抱10", dict(add=1.0, Hadd=10)),
                        (f"B 減到 1x 5天", dict(cut=True, Hcut=5)), (f"C 加1x抱5＋減", dict(add=1.0, Hadd=5, cut=True)),
                        (f"A 加1x抱5＋64b", dict(add=1.0, Hadd=5, vol_add=1.0))):
            res = {nm: sim(s, e, Z, x=x, **kw) for s, e, nm in P}
            L.append(f"x{x} {nm2:14s} " + "  ".join(f"{nm} {c:.1%}({c - base[nm][0]:+.1%})／{d:.1%}" for nm, (c, d) in res.items()))
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究75_在場時外資期貨加減碼.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
