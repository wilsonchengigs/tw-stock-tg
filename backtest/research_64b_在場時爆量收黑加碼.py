"""研究 64b：現行策略「在場（2x）」時遇到爆量收黑，用台指期再加 a 倍、抱 H 天（研究 63i：多頭裡的訊號最好）

現行策略同研究 64（研究 41 模組：MA60×1.01 進、MA80×0.975 出、融資濾網；2x）
加碼：在場時，證交所成交金額 ≥ k × 前 20 日均且加權收黑 → 當天收盤（實務＝當晚 15:00 夜盤開）加 a 倍，抱 H 個交易日後收盤平倉；
      期間現行策略出場 → 加碼一起平倉。台指期成本：每筆來回 3 點 ≈ 0.01%，另扣資金成本（同 bt 的 DRAG 1%／年按比例）
報表：全期 2002-2026、前段、後段的年化／最大回檔，與現行比；加碼次數、平均每次指數漲跌
用法：python -X utf8 backtest/research_64b_在場時爆量收黑加碼.py
"""
import importlib.util
import itertools
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r64", os.path.join(HERE, "research_64_爆量收黑加碼現行策略.py"))
r64 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r64)
R, bt, DAYS, PX, N, WE, HOT, VR = r64.R, r64.bt, r64.DAYS, r64.PX, r64.N, r64.WE, r64.HOT, r64.VR
FUT_COST = 0.0001


def sim(start, end, k=None, add=1.0, H=10):
    i0 = next(i for i, x in enumerate(DAYS) if x >= start)
    i1 = max(i for i, x in enumerate(DAYS) if x <= end)
    eq = peak = 1.0
    mdd = 0.0
    on, lev, pend = False, 0.0, None
    extra, ex_until, ex_entry = 0.0, -1, None
    adds = []
    for i in range(i0, i1 + 1):
        if i > i0:
            L = lev + extra
            r1 = bt.R1[i]
            eq *= 1 + ((L * r1 - max(L - 1, 0) * bt.DRAG / bt.TD) if L > 0 else bt.RC)
        if pend is not None:
            eq *= 1 - bt.COST * abs(pend - lev)
            lev, pend = pend, None
            if lev == 0 and extra:
                adds.append(PX[i] / PX[ex_entry] - 1)
                extra, ex_until = 0.0, -1
                eq *= 1 - FUT_COST * add
        if WE[i] and i >= 260:
            on = (not (PX[i] < R.M80[i] * 0.975 or HOT[i])) if on else (PX[i] > R.M60[i] * 1.01 and not HOT[i])
            want = 2.0 if on else 0.0
            if want != lev:
                pend = want
        if extra and i >= ex_until:
            adds.append(PX[i] / PX[ex_entry] - 1)
            extra, ex_until = 0.0, -1
            eq *= 1 - FUT_COST * add
        if (k is not None and lev == 2.0 and pend is None and not extra and i > i0
                and VR[i] is not None and VR[i] >= k and PX[i] < PX[i - 1]):
            extra, ex_until, ex_entry = add, i + H, i
            eq *= 1 - FUT_COST * add
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd, adds


def main():
    P = (("2002-01-01", "2026-12-31", "全期 2002-2026"), ("2002-01-01", "2012-12-31", "前段 2002-2012"), ("2013-01-01", "2026-12-31", "後段 2013-2026"))
    base = {p[2]: sim(p[0], p[1]) for p in P}
    L = ["研究 64b：現行策略在場（2x）時，爆量收黑用台指期加碼 a 倍、抱 H 天（訊號日收盤＝當晚夜盤進）",
         "現行：" + "  ".join(f"{nm} {b[0]:.1%}／{b[1]:.1%}" for nm, b in base.items()),
         "\nk    加碼  H  | " + " | ".join(p[2] for p in P) + " | 次數 勝率 平均"]
    good = tot = 0
    for k, add, H in itertools.product((1.3, 1.5), (0.5, 1.0), (5, 10)):
        cells, ok = [], True
        for s, e, nm in P:
            c, m, adds = sim(s, e, k, add, H)
            b = base[nm]
            cells.append(f"{c:5.1%}({c - b[0]:+.1%})／{m:6.1%}")
            ok &= c > b[0] and m >= b[1] - 0.01
            if nm.startswith("全期"):
                a_all = adds
        tot += 1
        good += ok
        w = sum(x > 0 for x in a_all) / len(a_all) if a_all else 0
        L.append(f"{k:.1f}  {add:.1f}x  {H:2d} | " + " | ".join(cells) + f" | {len(a_all):3d} {w:4.0%} {sum(a_all) / max(1, len(a_all)):+.2%}"
                 + ("  ★三段都勝、回檔加深 ≤1 個百分點" if ok else ""))
    L.append(f"\n通過：{good}/{tot}")

    # 對照：同樣次數、同樣持有天數，但「在場日隨機挑」加碼——分離「訊號」與「單純多加槓桿」
    import random
    rng = random.Random(6402)
    L.append("\n== 對照：在場日隨機加碼（同次數、同 H、同倍數，200 次）==")
    global VR
    real_vr = list(VR)
    for k, add, H in ((1.5, 1.0, 10), (1.5, 0.5, 5), (1.3, 1.0, 10)):
        c_real, m_real, adds = sim("2002-01-01", "2026-12-31", k, add, H)
        # 在場日（現行策略 2x 的日子）
        on_days = []
        _c, _m, _a = sim("2002-01-01", "2026-12-31")
        st = r64.state_series()
        i0 = next(i for i, x in enumerate(DAYS) if x >= "2002-01-01")
        on_days = [i for i in range(i0, N - H) if st[i] and st[i - 1]]
        res = []
        for _ in range(200):
            pick = set()
            cand = list(on_days)
            rng.shuffle(cand)
            for i in cand:
                if len(pick) >= len(adds):
                    break
                if all(abs(i - j) > H for j in pick):
                    pick.add(i)
            fake = [None] * N
            for i in pick:
                fake[i] = 99.0
            VR[:] = fake
            # 隨機日不要求收黑：暫時把條件放寬——用「收黑」以外的版本
            c, m, _a2 = sim_any("2002-01-01", "2026-12-31", add, H, pick)
            res.append((c, m))
            VR[:] = real_vr
        cs = sorted(x[0] for x in res)
        ms = sorted(x[1] for x in res)
        p = (sum(x >= c_real for x in cs) + 1) / 201
        L.append(f"  k{k} 加{add}x 抱{H}天：實際 {c_real:.1%}／{m_real:.1%}；隨機加碼 年化中位 {cs[100]:.1%}（95 分位 {cs[190]:.1%}）、"
                 f"回檔中位 {ms[100]:.1%}；訊號勝過隨機的 p＝{p:.3f}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究64b_在場時加碼.txt"), "w", encoding="utf-8").write(out)


def sim_any(start, end, add, H, pick):
    """在指定的日子（pick）加碼，其他同 sim()"""
    i0 = next(i for i, x in enumerate(DAYS) if x >= start)
    i1 = max(i for i, x in enumerate(DAYS) if x <= end)
    eq = peak = 1.0
    mdd = 0.0
    on, lev, pend = False, 0.0, None
    extra, ex_until = 0.0, -1
    for i in range(i0, i1 + 1):
        if i > i0:
            L = lev + extra
            eq *= 1 + ((L * bt.R1[i] - max(L - 1, 0) * bt.DRAG / bt.TD) if L > 0 else bt.RC)
        if pend is not None:
            eq *= 1 - bt.COST * abs(pend - lev)
            lev, pend = pend, None
            if lev == 0 and extra:
                extra, ex_until = 0.0, -1
        if WE[i] and i >= 260:
            on = (not (PX[i] < R.M80[i] * 0.975 or HOT[i])) if on else (PX[i] > R.M60[i] * 1.01 and not HOT[i])
            want = 2.0 if on else 0.0
            if want != lev:
                pend = want
        if extra and i >= ex_until:
            extra, ex_until = 0.0, -1
        if i in pick and lev == 2.0 and pend is None and not extra:
            extra, ex_until = add, i + H
            eq *= 1 - FUT_COST * add
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd, None


if __name__ == "__main__":
    main()
