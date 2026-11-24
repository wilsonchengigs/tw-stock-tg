"""研究 66b：研究 66「S&P 500 + 200 日線 2x」的鄰近參數穩定度
均線 150／175／200／225／250 日 × 進出緩衝 0／1／2% × 槓桿 1.5x／2x；每天收盤 > 均線×(1+緩衝) 才持有（隔天收盤成交）
驗收：全期、前段、後段年化都勝 S&P 買進持有 1x，且最大回檔 < 50%
用法：python -X utf8 backtest/research_66b_美股均線鄰近參數.py
"""
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("r66", os.path.join(HERE, "research_66_美股投資方式比較.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
P, R = m.PS, m.RS
PER = (("1986-06-01", "2026-12-31"), ("1986-06-01", "2005-12-31"), ("2006-01-01", "2026-12-31"))


def main():
    bh = [m.simulate(lambda i: [(R, 1)], s, e) for s, e in PER]
    L = ["研究 66b：S&P 500 均線濾網鄰近參數（全期／前段／後段 年化/最大回檔）",
         "買進持有 1x：" + "  ".join(f"{c:.1%}/{d:.1%}" for c, d, _w, _v in bh)]
    ok = tot = 0
    for lev in (1.5, 2.0):
        for n in (150, 175, 200, 225, 250):
            ma = m.sma(P, n)
            for b in (0.0, 0.01, 0.02):
                def f(i, ma=ma, b=b, lev=lev):
                    return [(R, lev)] if ma[i] and P[i] > ma[i] * (1 + b) else []
                res = [m.simulate(f, s, e) for s, e in PER]
                good = all(r[0] > h[0] for r, h in zip(res, bh)) and all(r[1] > -0.5 for r in res)
                ok += good
                tot += 1
                L.append(f"{lev}x MA{n} 緩衝{b:.0%}: " + "  ".join(f"{c:5.1%}/{d:6.1%}" for c, d, _w, _v in res) + (" ✓" if good else ""))
    L.append(f"三段都勝買進持有且回檔 < 50%：{ok}/{tot}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究66b_美股均線鄰近參數.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
