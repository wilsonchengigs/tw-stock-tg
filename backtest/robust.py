import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import bt  # noqa: E402

out = []
FULL, IS, OOS = ("1998-01-01", "2026-12-31"), ("1998-01-01", "2012-12-31"), ("2013-01-01", "2026-12-31")


def f(r):
    return f"{r['cagr']:5.1%}/{r['mdd']:6.1%}"


for on in ("1.5x", "2x"):
    out.append(f"\n== 鄰近參數穩定度（站上 {on}、跌破現金；格子＝全期 年化/最大回檔）==")
    bands = (0.0, 0.01, 0.015, 0.02, 0.025, 0.03)
    out.append("N\\band  " + "  ".join(f"{b:>13.1%}" for b in bands))
    for n in (50, 60, 70, 80, 90, 100, 110, 120):
        cells = []
        for b in bands:
            r = bt.run(bt.ma_signal(n, b), bt.POS[on], bt.POS["cash"], *FULL)
            cells.append(f"{f(r):>13s}")
        out.append(f"{n:<8d}" + "  ".join(cells))

# 壓力測試
cands = [(80, 0.02, "1.5x"), (60, 0.02, "1.5x"), (100, 0.01, "1.5x"), (80, 0.02, "2x")]
out.append("\n== 壓力測試（全期）==")
for n, b, on in cands:
    base = bt.run(bt.ma_signal(n, b), bt.POS[on], bt.POS["cash"], *FULL)
    old = bt.COST
    bt.COST = 0.005
    c2 = bt.run(bt.ma_signal(n, b), bt.POS[on], bt.POS["cash"], *FULL)
    bt.COST = old
    od, odr = bt.DRAG, bt.CASH
    bt.DRAG = 0.025  # 槓桿內扣再多 1.5%
    bt.R2 = [0.0] + [2 * bt.R1[i] - bt.DRAG / bt.TD for i in range(1, len(bt.PX))]
    d2 = bt.run(bt.ma_signal(n, b), bt.POS[on], bt.POS["cash"], *FULL)
    bt.DRAG = od
    bt.R2 = [0.0] + [2 * bt.R1[i] - bt.DRAG / bt.TD for i in range(1, len(bt.PX))]
    bt.CASH = 0.0
    z = bt.run(bt.ma_signal(n, b), bt.POS[on], bt.POS["cash"], *FULL)
    bt.CASH = odr
    out.append(f"MA{n} 緩衝{b:.0%} {on}: 基本 {f(base)} | 成本加倍 {f(c2)} | 槓桿內扣+1.5% {f(d2)} | 現金 0 利率 {f(z)}")

# 各次大跌期間
crashes = [
    ("2000 網路泡沫", "2000-02-01", "2001-10-31"),
    ("2008 金融海嘯", "2007-10-01", "2008-12-31"),
    ("2011 歐債", "2011-01-01", "2011-12-31"),
    ("2015 股災", "2015-04-01", "2015-09-30"),
    ("2018 Q4", "2018-09-01", "2018-12-31"),
    ("2020 疫情", "2020-01-01", "2020-04-30"),
    ("2022 升息", "2022-01-01", "2022-12-31"),
    ("2024-25 關稅", "2024-07-01", "2025-05-31"),
    ("2026 下半年", "2026-06-01", "2026-12-31"),
]
out.append("\n== 各次大跌期間（期間報酬 / 期間內最大回檔）==")
hold = lambda i, s: True  # noqa: E731
for name, a, b in crashes:
    bh = bt.run(hold, bt.POS["1x"], bt.POS["1x"], a, b)
    cells = [f"大盤 {bh['mult'] - 1:6.1%}/{bh['mdd']:6.1%}"]
    for n, bd, on in cands[:1] + cands[-1:]:
        r = bt.run(bt.ma_signal(n, bd), bt.POS[on], bt.POS["cash"], a, b)
        cells.append(f"MA{n}/{on} {r['mult'] - 1:6.1%}/{r['mdd']:6.1%}")
    out.append(f"{name:12s} " + " | ".join(cells))

# 每年報酬
out.append("\n== 每年報酬：大盤 vs MA80 緩衝2% 1.5x vs 2x ==")
for y in range(1998, 2027):
    a, b = f"{y}-01-01", f"{y}-12-31"
    bh = bt.run(hold, bt.POS["1x"], bt.POS["1x"], a, b)
    s15 = bt.run(bt.ma_signal(80, 0.02), bt.POS["1.5x"], bt.POS["cash"], a, b)
    s2 = bt.run(bt.ma_signal(80, 0.02), bt.POS["2x"], bt.POS["cash"], a, b)
    out.append(f"{y}  大盤 {bh['mult'] - 1:7.1%}  1.5x {s15['mult'] - 1:7.1%}  2x {s2['mult'] - 1:7.1%}")

open(os.path.join(os.path.dirname(__file__), "robust.txt"), "w", encoding="utf-8").write("\n".join(out))
