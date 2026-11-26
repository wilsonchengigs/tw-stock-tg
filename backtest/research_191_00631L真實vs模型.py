"""研究 191：00631L 真實價格 vs 回測模型的追蹤差（2026 高波動下模型有沒有低估正2 的耗損）

回測的 2x 模型（bt.R2）＝2×(加權日報酬＋3%/245) − 1%/245。00631L 實際還有：期貨轉倉、正逆價差、內扣費用、申贖折溢價。
比較（2015-09-01～，00631L、0050 用 Yahoo 調整後收盤）：
- 每年：00631L 實際報酬、模型報酬、差（實際 − 模型）；同時列 2×0050 − 1% 的版本
- 依當月加權波動分組：每月追蹤差的平均（看高波動時差是否擴大）
- 2026 逐月
用法：python -X utf8 backtest/research_191_00631L真實vs模型.py
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402
import data  # noqa: E402

TD = 245
_, E50, E631 = data.series()
DAYS = [d for d in bt.DAYS if d >= "2015-09-01" and d in E50 and d in E631]
idx = {d: i for i, d in enumerate(bt.DAYS)}


def series():
    rows = []
    for a, b in zip(DAYS, DAYS[1:]):
        i = idx[b]
        real = E631[b][1] / E631[a][1] - 1
        model = bt.R2[i] if idx[a] == i - 1 else None
        x50 = 2 * (E50[b][1] / E50[a][1] - 1) - 0.01 / TD
        rx = bt.PX[i] / bt.PX[idx[a]] - 1
        rows.append((b, real, model, x50, rx))
    return [r for r in rows if r[2] is not None]


def comp(rs):
    e = 1.0
    for r in rs:
        e *= 1 + r
    return e - 1


def main():
    rows = series()
    L = [f"研究 191：00631L 真實 vs 模型（{rows[0][0]}～{rows[-1][0]}，{len(rows)} 天）"]
    L.append("\n【每年】實際 00631L｜模型（2×加權+配息−1%）｜差｜2×0050−1%｜差｜當年加權波動")
    for y in sorted({r[0][:4] for r in rows}):
        g = [r for r in rows if r[0][:4] == y]
        real, model, x50 = comp([r[1] for r in g]), comp([r[2] for r in g]), comp([r[3] for r in g])
        m = sum(r[4] for r in g) / len(g)
        vol = math.sqrt(sum((r[4] - m) ** 2 for r in g) / len(g) * TD)
        L.append(f"  {y}：{real:+7.1%}｜{model:+7.1%}｜{real - model:+6.1%}｜{x50:+7.1%}｜{real - x50:+6.1%}｜{vol:4.0%}")
    real, model = comp([r[1] for r in rows]), comp([r[2] for r in rows])
    yrs = len(rows) / TD
    L.append(f"  全期年化：實際 {(1 + real) ** (1 / yrs) - 1:+.1%}、模型 {(1 + model) ** (1 / yrs) - 1:+.1%}")

    L.append("\n【依當月加權波動】每月 實際−模型 的平均（年化前）")
    months = {}
    for r in rows:
        months.setdefault(r[0][:7], []).append(r)
    buckets = {}
    for mth, g in months.items():
        m = sum(r[4] for r in g) / len(g)
        vol = math.sqrt(sum((r[4] - m) ** 2 for r in g) / len(g) * TD)
        diff = comp([r[1] for r in g]) - comp([r[2] for r in g])
        b = "<15%" if vol < 0.15 else ("15～25%" if vol < 0.25 else ("25～35%" if vol < 0.35 else "≥35%"))
        buckets.setdefault(b, []).append(diff)
    for b in ("<15%", "15～25%", "25～35%", "≥35%"):
        v = buckets.get(b, [])
        if v:
            L.append(f"  波動 {b:<7}：{len(v):>3} 個月、平均 {sum(v) / len(v):+.2%}／月、中位 {sorted(v)[len(v) // 2]:+.2%}、最差 {min(v):+.1%}")

    L.append("\n【2026 逐月】實際｜模型｜差")
    for mth in sorted(m for m in months if m.startswith("2026")):
        g = months[mth]
        a, b = comp([r[1] for r in g]), comp([r[2] for r in g])
        L.append(f"  {mth}：{a:+7.1%}｜{b:+7.1%}｜{a - b:+6.1%}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究191_00631L真實vs模型.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
