"""研究 64f：研究 64b 的加碼效果是「量」的貢獻，還是只是「多頭中逢低買進」？

同研究 64b 的框架（現行 2x 在場時加碼 1x、抱 10 天；加 0.5x 抱 5 天），只換訊號：
  A 爆量收黑（成交金額 ≥1.5x 且收黑）＝研究 64b
  B 任何收黑日
  C 跌 ≥1%      D 跌 ≥2%
  E 量平（<1.2x）且跌 ≥1%   F 量平且跌 ≥2%
  G 爆量（≥1.5x）且收紅（對照：爆量但方向相反）
報表：全期年化／回檔（與現行差）、加碼次數、平均每次指數漲跌
用法：python -X utf8 backtest/research_64f_在場加碼_量的貢獻.py
"""
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("r64b", os.path.join(HERE, "research_64b_在場時爆量收黑加碼.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
PX, VR, N = m.PX, m.VR, m.N


def main():
    def ch(i):
        return PX[i] / PX[i - 1] - 1 if i > 0 else 0

    conds = {
        "A 爆量≥1.5x 且收黑": lambda i: VR[i] is not None and VR[i] >= 1.5 and ch(i) < 0,
        "B 任何收黑日": lambda i: ch(i) < 0,
        "C 跌≥1%": lambda i: ch(i) <= -0.01,
        "D 跌≥2%": lambda i: ch(i) <= -0.02,
        "E 量平<1.2x 且跌≥1%": lambda i: VR[i] is not None and VR[i] < 1.2 and ch(i) <= -0.01,
        "F 量平<1.2x 且跌≥2%": lambda i: VR[i] is not None and VR[i] < 1.2 and ch(i) <= -0.02,
        "G 爆量≥1.5x 且收紅": lambda i: VR[i] is not None and VR[i] >= 1.5 and ch(i) > 0,
    }
    P = (("2002-01-01", "2026-12-31", "全期"), ("2002-01-01", "2012-12-31", "前段"), ("2013-01-01", "2026-12-31", "後段"))
    base = {nm: m.sim(s, e) for s, e, nm in P}
    L = ["研究 64f：在場加碼的訊號拆解（量的貢獻）",
         "現行：" + "  ".join(f"{nm} {b[0]:.1%}／{b[1]:.1%}" for nm, b in base.items())]
    real_vr = list(VR)
    for add, H in ((1.0, 10), (0.5, 5)):
        L.append(f"\n== 加碼 {add}x、抱 {H} 天 ==")
        for nm, cond in conds.items():
            # sim() 的條件是 VR≥k 且收黑：用假 VR（符合條件＝99、否則 0）並讓「收黑」條件對 G 失效 → 改寫 PX 比較不安全，
            # 這裡直接替換 VR，並對 G（收紅）另外處理
            flag = [cond(i) for i in range(N)]
            m.VR[:] = [99.0 if f else 0.0 for f in flag]
            if nm.startswith("G"):
                res = {pn: g_sim(s, e, flag, add, H) for s, e, pn in P}
            else:
                res = {pn: m.sim(s, e, 1.5, add, H) for s, e, pn in P}
            m.VR[:] = real_vr
            adds = res["全期"][2]
            L.append(f"  {nm:18s} " + "  ".join(f"{pn} {r[0]:.1%}({r[0] - base[pn][0]:+.1%})／{r[1]:.1%}" for pn, r in res.items())
                     + f"  ｜ {len(adds)} 次 平均 {sum(adds) / max(1, len(adds)):+.2%}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究64f_量的貢獻.txt"), "w", encoding="utf-8").write(out)


def g_sim(start, end, flag, add, H):
    """訊號不要求收黑（給 G 用）：暫時把 PX 比較條件繞過——複製 sim 的邏輯"""
    bt, R, DAYS, WE, HOT, PX = m.bt, m.R, m.DAYS, m.WE, m.HOT, m.PX
    i0 = next(i for i, x in enumerate(DAYS) if x >= start)
    i1 = max(i for i, x in enumerate(DAYS) if x <= end)
    eq = peak = 1.0
    mdd = 0.0
    on, lev, pend = False, 0.0, None
    extra, ex_until, ex_entry = 0.0, -1, None
    adds = []
    for i in range(i0, i1 + 1):
        if i > i0:
            Lv = lev + extra
            eq *= 1 + ((Lv * bt.R1[i] - max(Lv - 1, 0) * bt.DRAG / bt.TD) if Lv > 0 else bt.RC)
        if pend is not None:
            eq *= 1 - bt.COST * abs(pend - lev)
            lev, pend = pend, None
            if lev == 0 and extra:
                adds.append(PX[i] / PX[ex_entry] - 1)
                extra, ex_until = 0.0, -1
        if WE[i] and i >= 260:
            on = (not (PX[i] < R.M80[i] * 0.975 or HOT[i])) if on else (PX[i] > R.M60[i] * 1.01 and not HOT[i])
            want = 2.0 if on else 0.0
            if want != lev:
                pend = want
        if extra and i >= ex_until:
            adds.append(PX[i] / PX[ex_entry] - 1)
            extra, ex_until = 0.0, -1
        if lev == 2.0 and pend is None and not extra and i > i0 and flag[i]:
            extra, ex_until, ex_entry = add, i + H, i
            eq *= 1 - m.FUT_COST * add
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd, adds


if __name__ == "__main__":
    main()
