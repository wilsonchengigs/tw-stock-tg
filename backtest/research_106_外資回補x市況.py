"""研究 106：外資台指期大回補（Δz > +1.5）隔天做多抱 1 天 × 市況（多頭／空頭／融資過熱）；排除結算日與次日（研究 79）
外資淨未平倉＝多單未平倉 − 空單未平倉（tx_inst_oi.csv，FinMind，2018-06～）；Δz＝單日變化相對前 250 日
交易：台指期（進場日到出場日都有交易、進場日量最大的月份）隔天日盤開盤買，第 H 個交易日日盤收盤平；成本 3 點
分組：訊號當天融資過熱（v3）／指數 ≥ MA80×0.975（多頭）／空頭；對照同組隨機日
另看大加空（Δz < −1.5）隔天放空同樣分組（日報目前只觀察、不建議）
用法：python -X utf8 backtest/research_106_外資回補x市況.py
"""
import csv
import importlib.util
import os
import random
import sys
from collections import defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r105", os.path.join(HERE, "research_105_爆量收黑x融資過熱.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
V, DAYS, PX, N, TX = R.V, R.DAYS, R.PX, R.N, R.TX
IDX = {d: i for i, d in enumerate(DAYS)}

net = {}
for r in csv.DictReader(open(os.path.join(HERE, "tx_inst_oi.csv"), encoding="utf-8")):
    if r["investor"].startswith("外資"):
        net[r["date"]] = float(r["long_oi"]) - float(r["short_oi"])
ds = sorted(net)
dl = [net[ds[k]] - net[ds[k - 1]] for k in range(1, len(ds))]
Z = {}
for k in range(250, len(dl)):
    h = dl[k - 250:k]
    m = sum(h) / 250
    sd = (sum((x - m) ** 2 for x in h) / 250) ** 0.5
    Z[ds[k + 1]] = (dl[k] - m) / sd if sd else 0.0


def settle_like(d, prev):
    def tw(x):
        y = date.fromisoformat(x)
        return y.weekday() == 2 and 15 <= y.day <= 21
    return tw(d) or tw(prev)


def trade(i, H, side):
    if i + H >= N:
        return None
    d1, dH = DAYS[i + 1], DAYS[i + H]
    ok = [m for m in TX.get(d1, {}) if m in TX.get(dH, {})]
    if not ok:
        return None
    mo = max(ok, key=lambda k: TX[d1][k][2])
    e, x = TX[d1][mo][0], TX[dH][mo][1]
    return (side * (x - e) - 3) / e


def group(i):
    if V.DEV[i] is None:
        return None
    if V.hot_at(i):
        return "過熱"
    return "多頭" if PX[i] >= V.M80[i] * 0.975 else "空頭"


def main():
    random.seed(106)
    L = [f"研究 106：外資台指期大變化 × 市況（{min(Z)}～{max(Z)}，排除結算日與次日）"]
    days = [d for d in sorted(Z) if d in IDX and IDX[d] > 0 and not settle_like(d, DAYS[IDX[d] - 1])]
    for side, nm, cond in ((1, "大回補 Δz>+1.5 → 做多", lambda z: z > 1.5), (-1, "大加空 Δz<−1.5 → 放空", lambda z: z < -1.5)):
        for H in (1, 3, 5):
            L.append(f"\n== {nm}，抱 {H} 天 ==")
            G = defaultdict(list)
            B = defaultdict(list)
            for d in days:
                i = IDX[d]
                g = group(i)
                r = trade(i, H, side)
                if g is None or r is None:
                    continue
                B[g].append(r)
                B["全部"].append(r)
                if cond(Z[d]):
                    G[g].append(r)
                    G["全部"].append(r)
            for g in ("全部", "多頭", "空頭", "過熱"):
                rs, base = G[g], B[g]
                if not rs:
                    L.append(f"{g:4s} 0 筆")
                    continue
                m = sum(rs) / len(rs)
                p = sum(sum(random.sample(base, len(rs))) / len(rs) >= m for _ in range(1000)) / 1000 if len(base) > len(rs) else float("nan")
                L.append(f"{g:4s} {len(rs):3d} 筆、勝率 {sum(r > 0 for r in rs) / len(rs):4.0%}、每筆 {m:+.2%}（同組隨機 {sum(base) / len(base):+.2%}、p {p:.3f}）")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究106_外資回補x市況.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
