"""研究 186b：研究 09 的「台股＋美股趨勢腿」在 v3 現行策略上重驗

研究 09 用舊版台股腿（無融資濾網）得到「台 80%＋NDX 20% 10 月線」全期勝現行、回檔較淺，但真實價格略輸，列候選沒採用。
v3 加了融資過熱濾網後台股腿變強很多，這裡重驗：
- 台股腿：v3 每日淨值（strategy_v3，含融資過熱、每日檢查）；真實段用 00631L 真實價
- 美股腿：研究 09 的 USLeg（2x＝2×指數含息−1%，換台幣；2015-09 後真實價 QLD（NDX 2x））；規則 10 個月線（月底）或 200 日線（週五）
- NDX 有後見之明（事後知道科技股最強），另跑 S&P 500（GSPC，只有模擬價）當比較
- 兩腿每月底再平衡；美股腿換手成本 0.25%/單位
- 權重：台股 100／90／80／70%
看：全期 2002–｜前段 –2012｜後段 2013–｜真實 2015-09–；逐年勝負；2026 這一波
用法：python -X utf8 backtest/research_186b_v3加美股腿.py
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


V3 = load("v3", "strategy_v3.py")
R09 = load("r09", "research_09_多市場分散.py")
bt, DAYS, N = V3.bt, V3.DAYS, V3.N
ME = R09.ME
COST = bt.COST


def v3_rets(start, real):
    _, _, e = V3.run(start, "2026-12-31", real=real, curve=True)
    i0 = next(i for i, d in enumerate(DAYS) if d >= start)
    r = [0.0] * N
    for k in range(1, len(e)):
        r[i0 + k] = e[k] / e[k - 1] - 1
    return r


TW = {False: v3_rets("2002-01-01", False), True: v3_rets("2015-09-01", True)}
LEGS = {"NDX": R09.USLeg("NDX", 0.008, real_etf="QLD"), "S&P": R09.USLeg("GSPC", 0.018)}


def run(wtw, legname, rule, start, end, real=False, curve=False):
    i0 = next(i for i, d in enumerate(DAYS) if d >= start)
    i1 = max(i for i, d in enumerate(DAYS) if d <= end)
    tr = TW[real]
    leg = LEGS.get(legname)
    ur = (leg.r2tw_real if (real and leg.r2tw_real) else leg.r2tw) if leg else None
    usig = leg.signal(rule) if leg else None
    a, b = wtw, 1 - wtw
    pb, pend = 0.0, None
    eq, peak, mdd, ys = 1.0, 1.0, 0.0, {}
    for i in range(i0, i1 + 1):
        if i > i0:
            a *= 1 + tr[i]
            b *= 1 + (pb * ur[i] + (1 - pb) * bt.RC if leg else bt.RC)
        if pend is not None:
            b *= 1 - COST * 2 * abs(pend - pb)
            pb, pend = pend, None
        eq = a + b
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        ys[DAYS[i][:4]] = eq
        if leg and usig[i] != (pb == 1.0) and pend is None:
            pend = 1.0 if usig[i] else 0.0
        if ME[i]:
            a, b = eq * wtw, eq * (1 - wtw)
    yrs = (i1 - i0) / bt.TD
    out = (eq ** (1 / yrs) - 1, mdd)
    if curve:
        prev, yr = 1.0, {}
        for y in sorted(ys):
            yr[y] = ys[y] / prev - 1
            prev = ys[y]
        return out + (yr,)
    return out


PER = [("2002-01-01", "2026-12-31"), ("2002-01-01", "2012-12-31"), ("2013-01-01", "2026-12-31")]


def main():
    L = ["研究 186b：v3 ＋ 美股趨勢腿（每月再平衡；全期｜前段｜後段｜真實 2015-09–；逐年勝 v3 的年數）"]
    _, _, ybase = run(1.0, None, None, *PER[0], curve=True)
    base = None
    for legname, rule in ((None, None), ("NDX", "m10"), ("NDX", "ma200"), ("S&P", "m10"), ("S&P", "ma200")):
        for w in ((1.0,) if legname is None else (0.9, 0.8, 0.7)):
            rs = [run(w, legname, rule, a, b) for a, b in PER]
            rr = run(w, legname, rule, "2015-09-01", "2026-12-31", real=True)
            _, _, yv = run(w, legname, rule, *PER[0], curve=True)
            win = sum(yv[y] > ybase[y] + 1e-9 for y in ybase)
            name = "v3 單獨" if legname is None else f"台 {w:.0%}＋{legname} {rule}"
            if base is None:
                base = (rs, rr)
            ok = legname and all(x[0] >= y[0] for x, y in zip(rs, base[0])) and rr[0] >= base[1][0]
            lessdd = legname and all(x[1] >= y[1] for x, y in zip(rs, base[0])) and rr[1] >= base[1][1]
            L.append(f"  {name:<22}" + " | ".join(f"{c:5.1%}/{m:6.1%}" for c, m in rs) + f" | 真實 {rr[0]:5.1%}/{rr[1]:6.1%}"
                     + (f"  勝 {win}/{len(ybase)} 年" if legname else "") + ("  ★報酬四段都不輸" if ok else "") + ("  ◆回檔四段都較淺" if lessdd else ""))
    _, _, y80 = run(0.8, "NDX", "m10", *PER[0], curve=True)
    L.append("\n逐年（v3 單獨 vs 台 80%＋NDX 10 月線）：" + "、".join(f"{y} {ybase[y]:+.0%}/{y80[y]:+.0%}" for y in ybase))
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究186b_v3加美股腿.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
