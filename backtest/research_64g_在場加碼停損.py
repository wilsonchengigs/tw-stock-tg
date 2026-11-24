"""研究 64g：在場加碼（研究 64b）加上停損——馬克羊「少輸」
加碼部位在指數收盤跌破進場價 ×(1−s) 時當天收盤平倉（s＝2／3／5%），其餘同研究 64b（k 1.5）
用法：python -X utf8 backtest/research_64g_在場加碼停損.py
"""
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("r64b", os.path.join(HERE, "research_64b_在場時爆量收黑加碼.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
bt, R, DAYS, WE, HOT, PX, VR = m.bt, m.R, m.DAYS, m.WE, m.HOT, m.PX, m.VR


def sim(start, end, k, add, H, stop):
    i0 = next(i for i, x in enumerate(DAYS) if x >= start)
    i1 = max(i for i, x in enumerate(DAYS) if x <= end)
    eq = peak = 1.0
    mdd = 0.0
    on, lev, pend = False, 0.0, None
    extra, until, entry = 0.0, -1, None
    n = stopped = 0
    for i in range(i0, i1 + 1):
        if i > i0:
            Lv = lev + extra
            eq *= 1 + ((Lv * bt.R1[i] - max(Lv - 1, 0) * bt.DRAG / bt.TD) if Lv > 0 else bt.RC)
        if pend is not None:
            eq *= 1 - bt.COST * abs(pend - lev)
            lev, pend = pend, None
            if lev == 0:
                extra, until = 0.0, -1
        if WE[i] and i >= 260:
            on = (not (PX[i] < R.M80[i] * 0.975 or HOT[i])) if on else (PX[i] > R.M60[i] * 1.01 and not HOT[i])
            want = 2.0 if on else 0.0
            if want != lev:
                pend = want
        if extra and (i >= until or (stop and PX[i] < entry * (1 - stop))):
            stopped += i < until
            extra, until = 0.0, -1
        if k and lev == 2.0 and pend is None and not extra and i > i0 and VR[i] is not None and VR[i] >= k and PX[i] < PX[i - 1]:
            extra, until, entry = add, i + H, PX[i]
            n += 1
            eq *= 1 - m.FUT_COST * add
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
    return eq ** (1 / ((i1 - i0) / bt.TD)) - 1, mdd, n, stopped


def main():
    P = (("2002-01-01", "2026-12-31", "全期"), ("2002-01-01", "2012-12-31", "前段"), ("2013-01-01", "2026-12-31", "後段"))
    L = ["研究 64g：在場加碼＋停損（k 1.5；指數收盤跌破進場價 ×(1−s) 平掉加碼）"]
    b = {nm: sim(s, e, None, 0, 0, None) for s, e, nm in P}
    L.append("現行：" + "  ".join(f"{nm} {r[0]:.1%}／{r[1]:.1%}" for nm, r in b.items()))
    for add, H in ((1.0, 10), (0.5, 5), (1.0, 5)):
        L.append(f"\n== 加 {add}x 抱 {H} 天 ==")
        for stop in (None, 0.02, 0.03, 0.05):
            res = {nm: sim(s, e, 1.5, add, H, stop) for s, e, nm in P}
            L.append(f"  停損 {'無' if stop is None else f'{stop:.0%}':>3s}：" + "  ".join(
                f"{nm} {r[0]:.1%}({r[0] - b[nm][0]:+.1%})／{r[1]:.1%}" for nm, r in res.items())
                + f"  ｜ {res['全期'][2]} 次、停損 {res['全期'][3]} 次")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究64g_在場加碼停損.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
