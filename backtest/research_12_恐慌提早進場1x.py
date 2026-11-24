"""研究 12：台指 VIX 恐慌反轉提早進場的保守版（待研究 15）

研究 05 F 類：VIX 近 20 日高點 > x、今日 VIX 低於 5 日均、指數站上 MA20 → 提早全押 2x。全期較好但參數不穩、部分組合回檔 -61%。
這裡改成：提早進場只押 lev_early（1x 或 1.5x），等指數站上現行進場線（MA60×1.01）才加到 2x；出場規則不變。
資料：backtest/vixtwn.csv（salmonmisosoup/leverage-dashboard 鏡像，2001-12～）
用法：python -X utf8 backtest/research_12_恐慌提早進場1x.py
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.argv = [sys.argv[0], os.path.join(HERE, "vixtwn.csv")]
spec = importlib.util.spec_from_file_location("r05", os.path.join(HERE, "research_05_波動濾網.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
bt = R.bt
M60 = bt.get_sma(60)


def lev_fn(lev_early):
    """同一段持有期內：還沒站上現行進場線前用 lev_early，站上過一次之後維持 2x；出場後（隔超過一週沒被呼叫）重置"""
    st = {"prev": -99, "full": False}

    def g(i):
        if i - st["prev"] > 7:
            st["full"] = False
        st["prev"] = i
        if R.PX[i] > M60[i] * 1.01:
            st["full"] = True
        return 2.0 if st["full"] else lev_early
    return g


def row(kw):
    cells = [R.f(R.run(a, b, **kw)) for a, b in R.PER02.values()]
    rr = R.run(*R.REAL, real=True, **kw)
    return " | ".join(cells) + f" | 真實 {R.f(rr)}"


def main():
    L = ["研究 12：恐慌反轉提早進場（全期 2002-2026 | 前段 2002-2012 | 後段 2013-2026 | 真實 2015-09～；年化/最大回檔）"]
    L.append(f"{'現行':34s} {row({})}")
    wins = {1.0: 0, 1.5: 0, 2.0: 0}
    tot = 0
    base = [R.run(a, b) for a, b in R.PER02.values()]
    base_r = R.run(*R.REAL, real=True)
    for x in (30, 35, 40, 45):
        for look in (10, 20, 40):
            for ma in (10, 20, 40):
                tot += 1
                L.append(f"\nx={x} look={look} MA{ma}")
                for le in (1.0, 1.5, 2.0):
                    kw = dict(early_entry=R.panic_reversal(x, look, ma), lev_on=lev_fn(le) if le < 2 else None)
                    rs = [R.run(a, b, **kw) for a, b in R.PER02.values()]
                    rr = R.run(*R.REAL, real=True, **kw)
                    ok = (all(r["cagr"] >= q["cagr"] - 1e-9 for r, q in zip(rs, base)) and rs[0]["mdd"] > -0.5
                          and rr["cagr"] >= base_r["cagr"] - 1e-9 and rr["mdd"] >= base_r["mdd"] - 0.03)
                    wins[le] += ok
                    L.append(f"  早進 {le}x {'★' if ok else ' '} " + " | ".join(R.f(r) for r in rs) + f" | 真實 {R.f(rr)}")
    L.append(f"\n36 組中三段＋真實都勝現行（回檔 < 50%）：1x {wins[1.0]} 組、1.5x {wins[1.5]} 組、2x {wins[2.0]} 組")
    # 逐年（x=40 look=20 MA20）
    ya = R.run(*R.PER02["全期 2002-2026"], yearly=True)["yearly"]
    L.append("\n逐年（x=40 look=20 MA20）：現行 | 早進 1x | 早進 2x")
    y1 = R.run(*R.PER02["全期 2002-2026"], yearly=True, early_entry=R.panic_reversal(40), lev_on=lev_fn(1.0))["yearly"]
    y2 = R.run(*R.PER02["全期 2002-2026"], yearly=True, early_entry=R.panic_reversal(40))["yearly"]
    for y in sorted(ya):
        if abs(y1[y] - ya[y]) > 0.005 or abs(y2[y] - ya[y]) > 0.005:
            L.append(f"  {y} {ya[y]:+7.1%} | {y1[y]:+7.1%} | {y2[y]:+7.1%}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究12_恐慌提早進場1x.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
