"""研究 64：現行策略「空手時」加上研究 63b 的爆量收黑短抱，能不能提高報酬而不加深回檔？

現行策略：週五收盤 加權 > MA60×1.01 → 下一交易日收盤全押 2x；< MA80×0.975 或融資過熱 → 賣出轉現金（研究 41 模組）
加碼規則（只在現行策略空手時）：
- 訊號日 i：證交所成交金額 ≥ k × 前 20 日均，且收盤 < 前收
- 成交：(a) 保守＝i+1 日收盤買（bt.py 慣例，吃不到隔天反彈）；(b) 樂觀上限＝i 日收盤買（實務需 13:25 預估量，或用台指期夜盤）
- 部位 Lo＝1x 或 2x，持有 H 個交易日後收盤賣；持有中現行策略轉多 → 直接由現行策略接手
- 成本：每換手 1 單位 0.25%
報表：全期 2002～（融資濾網有資料起）、前段 2002-2012、後段 2013-2026 的年化／最大回檔，與現行比；加碼筆數與勝率
用法：python -X utf8 backtest/research_64_爆量收黑加碼現行策略.py
"""
import importlib.util
import itertools
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r41", os.path.join(HERE, "research_41_總經濾網.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
bt, DAYS, PX, N, WE, HOT = R.bt, R.DAYS, R.PX, R.N, R.WE, R.HOT
spec = importlib.util.spec_from_file_location("r61", os.path.join(HERE, "research_61_爆量順勢短線.py"))
r61 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r61)
_vr = dict(zip(r61.DAYS, r61.VR["成交金額"]))
VR = [_vr.get(d) for d in DAYS]


def sim(start, end, k=None, lo=1.0, H=5, mode="next"):
    i0 = next(i for i, x in enumerate(DAYS) if x >= start)
    i1 = max(i for i, x in enumerate(DAYS) if x <= end)
    eq = peak = 1.0
    mdd = 0.0
    on = False        # 現行策略想要的狀態
    lev = 0.0         # 目前實際曝險
    pend = None       # 下一交易日收盤要換到的曝險
    ov = False        # 加碼部位進行中（含已下單待成交）
    ov_until = -1     # 加碼持有到哪一天（收盤賣）
    ov_entry = -1
    ov_trades = []
    for i in range(i0, i1 + 1):
        if i > i0:
            r1 = bt.R1[i]
            eq *= 1 + ((lev * r1 - max(lev - 1, 0) * bt.DRAG / bt.TD) if lev > 0 else bt.RC)
        target, pend = pend, None   # 昨天決定、今天收盤執行
        if WE[i] and i >= 260:
            on = (not (PX[i] < R.M80[i] * 0.975 or HOT[i])) if on else (PX[i] > R.M60[i] * 1.01 and not HOT[i])
            if on:
                ov = False          # 現行策略接手
            want = 2.0 if on else (lo if ov else 0.0)
            if want != (target if target is not None else lev):
                pend = want
        eff = target if target is not None else lev
        # 加碼訊號（只在空手、沒有待執行單時）
        if (k is not None and not on and not ov and eff == 0 and pend is None and i > i0
                and VR[i] is not None and VR[i] >= k and PX[i] < PX[i - 1]):
            ov = True
            if mode == "same":
                target, ov_until, ov_entry = lo, i + H, i
            else:
                pend, ov_until, ov_entry = lo, i + 1 + H, i + 1
        # 加碼到期
        if ov and i == ov_until:
            ov = False
            if not on:
                target = 0.0
                pend = None
            ov_trades.append(PX[i] / PX[ov_entry] - 1)
        if target is not None and target != lev:
            eq *= 1 - bt.COST * abs(target - lev)
            lev = target
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd, ov_trades


def main():
    L = ["研究 64：現行策略空手時加上「爆量收黑短抱」（2x 在場；出場 2.5%＋融資濾網）",
         "格式：年化／最大回檔；加碼筆數、勝率、平均每筆（指數漲跌，未含槓桿與成本）"]
    periods = (("2002-01-01", "2026-12-31", "全期 2002-2026"), ("2002-01-01", "2012-12-31", "前段 2002-2012"), ("2013-01-01", "2026-12-31", "後段 2013-2026"))
    base = {p[2]: sim(p[0], p[1]) for p in periods}
    L.append("\n現行：" + "  ".join(f"{nm} {b[0]:.1%}／{b[1]:.1%}" for nm, b in base.items()))
    L.append("\nk    倍數  H   成交   | " + " | ".join(p[2] for p in periods) + " | 加碼筆數 勝率 平均")
    better = 0
    total = 0
    for mode, k, lo, H in itertools.product(("next", "same"), (1.3, 1.5, 1.8), (1.0, 2.0), (3, 5, 10)):
        cells = []
        allwin = True
        for s, e, nm in periods:
            cagr, mdd, trs = sim(s, e, k, lo, H, mode)
            b = base[nm]
            cells.append(f"{cagr:5.1%}({cagr - b[0]:+.1%})／{mdd:6.1%}")
            if not (cagr > b[0] and mdd >= b[1] - 0.005):
                allwin = False
            if nm.startswith("全期"):
                ft = trs
        total += 1
        better += allwin
        w = sum(x > 0 for x in ft) / len(ft) if ft else 0
        avg = sum(ft) / len(ft) if ft else 0
        L.append(f"{k:.1f}  {lo:.0f}x  {H:2d}  {'隔天收' if mode == 'next' else '當天收'} | " + " | ".join(cells)
                 + f" | {len(ft):3d}  {w:4.0%}  {avg:+.2%}{'  ★三段都勝且回檔沒加深' if allwin else ''}")
    L.append(f"\n三段年化都勝現行、且最大回檔沒有加深超過 0.5 個百分點的組數：{better}/{total}")

    # 拆解：研究 63b 的訊號（成交金額 ≥k、收黑，隔天開盤買抱 H 天）依訊號日的趨勢狀態分組
    spec2 = importlib.util.spec_from_file_location("r63b", os.path.join(HERE, "research_63b_爆量收黑買進.py"))
    r63b = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(r63b)
    pos = {d: i for i, d in enumerate(DAYS)}
    L.append("\n== 拆解：研究 63b 訊號依趨勢狀態（訊號日加權 vs MA80；以及現行策略是否在場）==")
    for k, H in ((1.3, 5), (1.5, 5), (1.5, 10)):
        trs = r63b.trades(r63b.signals("成交金額", k, 0.0), H)
        groups = {"指數 > MA80（多頭）": [], "指數 ≤ MA80（空頭）": [], "現行策略在場": [], "現行策略空手": []}
        state = state_series()
        for e, x, r in trs:
            d = r63b.DAYS[e - 1]
            j = pos.get(d)
            if j is None or R.M80[j] is None:
                continue
            groups["指數 > MA80（多頭）" if PX[j] > R.M80[j] else "指數 ≤ MA80（空頭）"].append(r)
            groups["現行策略在場" if state[j] else "現行策略空手"].append(r)
        L.append(f"-- 成交金額 ≥{k}x 收黑、抱 {H} 天 --")
        for nm, rs in groups.items():
            if rs:
                L.append(f"  {nm:14s} {len(rs):3d} 筆 勝率 {sum(r > 0 for r in rs) / len(rs):4.0%} 每筆 {sum(rs) / len(rs):+.2%}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究64_爆量收黑加碼.txt"), "w", encoding="utf-8").write(out)


def state_series():
    """現行策略每天的在場狀態（週五判斷，下一交易日生效；含融資濾網）"""
    st = [False] * N
    on = False
    for i in range(N):
        if WE[i] and i >= 260 and R.M80[i] is not None and R.M60[i] is not None:
            on = (not (PX[i] < R.M80[i] * 0.975 or HOT[i])) if on else (PX[i] > R.M60[i] * 1.01 and not HOT[i])
        st[i] = on
    return st


if __name__ == "__main__":
    main()
