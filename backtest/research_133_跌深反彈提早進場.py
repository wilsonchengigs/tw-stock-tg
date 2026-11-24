"""研究 133：不靠 P/C 的「跌深反彈提早進場」× v3（研究 132 發現平移後的假 P/C 也不輸 v3，檢查機制本身）
- 訊號：近 L 日內某天收盤比當時近 60 日最高收盤低 D% 以上（跌深），且本週五收盤 > 近 L 日最低 ×(1+c) → 提早持有（其餘同研究 132 引擎）
- 格點：D 10／15／20% × L 10／20 × c 3／5% × 早進 1x／2x 共 24 組；全期、前段 2002–2012、後段、真實價
- 樣本外：只用前段挑最好的一組，看後段與真實價
用法：python -X utf8 backtest/research_133_跌深反彈提早進場.py
"""
import importlib.util
import itertools
import os

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("r132", os.path.join(HERE, "research_132_PC提早進場多重檢定.py"))
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
PX, N = M.PX, M.N
SEGS = (("全期", "2002-01-01", "2026-12-31", False), ("前段", "2002-01-01", "2012-12-31", False),
        ("後段", "2013-01-01", "2026-12-31", False), ("真實", "2015-09-01", "2026-12-31", True))


def dd_flag(D):
    return [None if i < 60 else (1.0 if PX[i] <= max(PX[i - 59:i + 1]) * (1 - D) else 0.0) for i in range(N)]


def main():
    base = [M.run(a, b, M.PR0, real=r) for _, a, b, r in SEGS]
    L_ = ["研究 133：跌深反彈提早進場 × v3（全期｜前段｜後段｜真實）", "v3：" + "｜".join(f"{x:.1%}" for x in base)]
    res = {}
    for D, L, c, le in itertools.product((0.10, 0.15, 0.20), (10, 20), (0.03, 0.05), (1.0, 2.0)):
        r = [M.run(a, b, dd_flag(D), q=0.5, L=L, c=c, lev_early=le, real=rl) for _, a, b, rl in SEGS]
        res[(D, L, c, le)] = r
        beat = sum(x > y for x, y in zip(r, base))
        L_.append(f"D{D:.0%} L{L} c{c:.0%} 早進{le:.0f}x：" + "｜".join(f"{x:.1%}" for x in r) + f"｜勝 v3 {beat}/4")
    best = max(res, key=lambda k: res[k][1])
    L_.append(f"\n樣本外：前段最好 {best} → 後段 {res[best][2]:.1%}（v3 {base[2]:.1%}）、真實 {res[best][3]:.1%}（v3 {base[3]:.1%}）")
    L_.append(f"四段都勝 v3：{sum(all(x > y for x, y in zip(v, base)) for v in res.values())}/{len(res)} 組")
    txt = "\n".join(L_) + "\n"
    print(txt)
    open(os.path.join(HERE, "結果_研究133_跌深反彈提早進場.txt"), "w", encoding="utf-8").write(txt)


if __name__ == "__main__":
    main()
