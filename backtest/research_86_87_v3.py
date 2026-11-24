"""研究 86：過熱時保留部分部位（hot_lev 0／0.5／1.0／1.5）；研究 87：v3 現行策略逐年報酬與回本時間
用法：python -X utf8 backtest/research_86_87_v3.py
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("v3", os.path.join(HERE, "strategy_v3.py"))
V = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V)
DAYS, N = V.DAYS, V.N


def main():
    L = ["研究 86：過熱時保留部分部位（全期 2002- | 前段 | 後段 | 真實）"]
    for hl in (0.0, 0.5, 1.0, 1.5):
        L.append(f"過熱時保留 {hl}x  {V.fmt(hot_lev=hl)}")
    L.append("\n研究 87：v3 現行策略逐年（2015-09 起真實價格；2026 到 11/20）")
    i0 = next(i for i, d in enumerate(DAYS) if d >= "2002-01-01")
    _, _, curve = V.run("2002-01-01", "2026-12-31", curve=True)
    # 2015-09 起用真實價格接續
    _, _, curve_r = V.run("2015-09-01", "2026-12-31", real=True, curve=True)
    j0 = next(i for i, d in enumerate(DAYS) if d >= "2015-09-01")
    eq = curve[:j0 - i0] + [curve[j0 - i0 - 1] * x for x in curve_r[1:]]
    days = DAYS[i0:i0 + len(eq)]
    ys = {}
    for d, e in zip(days, eq):
        ys[d[:4]] = e
    prev = 1.0
    L.append("年份 | v3 報酬 | 年內最大回檔")
    peak_y, mdd_y = {}, {}
    pk = None
    for d, e in zip(days, eq):
        y = d[:4]
        if y not in peak_y:
            pk = e
            peak_y[y] = e
        pk = max(pk, e)
        mdd_y[y] = min(mdd_y.get(y, 0.0), e / pk - 1)
    for y in sorted(ys):
        L.append(f"{y} | {ys[y] / prev - 1:+7.1%} | {mdd_y[y]:6.1%}")
        prev = ys[y]
    tot = eq[-1] / eq[0]
    yrs = len(eq) / 245
    L.append(f"2002～2026/11 累積 {tot:,.0f} 倍，年化 {tot ** (1 / yrs) - 1:.1%}")
    e20 = [e for d, e in zip(days, eq) if d >= "2007-01-01"]
    L.append(f"近 20 年（2007～）累積 {e20[-1] / e20[0]:,.1f} 倍，年化 {(e20[-1] / e20[0]) ** (245 / len(e20)) - 1:.1%}")
    # 最長水下
    pk_i, longest, cur_start = 0, (0, None, None), None
    for k in range(len(eq)):
        if eq[k] >= eq[pk_i]:
            if k - pk_i > longest[0]:
                longest = (k - pk_i, days[pk_i], days[k])
            pk_i = k
    if len(eq) - 1 - pk_i > longest[0]:
        longest = (len(eq) - 1 - pk_i, days[pk_i], "尚未回本")
    L.append(f"最長從前高到回本：{longest[0] / 21:.0f} 個月（{longest[1]} → {longest[2]}）；目前距前高 {eq[-1] / max(eq) - 1:+.1%}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究86_87_v3.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
