"""研究 65：夜盤爆量 → 隔天日盤（馬克羊「美國數據事件交易」的資料驅動近似）

沒有可靠的經濟數據日曆，改用「夜盤成交量 ≥ k × 前 20 個夜盤平均」定義事件夜（美國數據、美股大波動多半落在夜盤）。
資料：backtest/tx_daily_ohlc.csv 的盤後（night）列，2017-05～；期交所把 D-1 晚上的夜盤記在 D
- 夜盤方向：夜盤收 vs 前一日日盤收（整晚漲跌）；另看夜盤 K 棒（收 vs 開）
- 交易（都在日盤 D）：
  順勢：夜盤漲 → 日盤開盤買、收盤賣；夜盤跌 → 開盤空、收盤補
  逆勢：反過來
  另看「隔天開盤進、抱 3 天」
- 對照：所有夜晚、夜盤大漲跌（|整晚| ≥1%）但量平（<1.2x）
- 成本：每筆 3 點
用法：python -X utf8 backtest/research_65_夜盤爆量隔天日盤.py
"""
import importlib.util
import os
import random
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("r63d", os.path.join(HERE, "research_63d_爆量收黑_台指期真實價.py"))
r63d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r63d)
COST = 3.0


def main():
    dates, day, night, near = r63d.load()
    n = len(dates)
    rows = []  # (i, 夜盤量, 夜盤整晚漲跌, 夜盤K棒, 日盤開, 日盤收, 3天後收)
    for i in range(1, n):
        d, pd = dates[i], dates[i - 1]
        m = near[d]
        nb = night[d].get(m)
        db = day[d].get(m)
        pc = day[pd].get(m)
        if not nb or not db or not pc or nb[4] <= 0:
            continue
        c3 = None
        if i + 2 < n:
            g = db[3] / db[0]
            ok = True
            for j in (i + 1, i + 2):
                mj = near[dates[j]]
                prev = day[dates[j - 1]].get(mj)
                if not prev:
                    ok = False
                    break
                g *= day[dates[j]][mj][3] / prev[3]
            c3 = g - 1 if ok else None
        rows.append((i, nb[4], nb[3] / pc[3] - 1, nb[3] / nb[0] - 1, db[0], db[3], c3))
    # 夜盤量比
    vr = []
    for k, r in enumerate(rows):
        xs = [x[1] for x in rows[max(0, k - 20):k]]
        vr.append(r[1] / statistics.mean(xs) if len(xs) >= 15 else None)
    L = ["研究 65：夜盤爆量 → 隔天日盤（台指期近月；成本每筆 3 點；夜盤 2017-05～）",
         f"夜晚數 {len(rows)}（{dates[rows[0][0]]}～{dates[rows[-1][0]]}）"]

    def intraday(r, d):
        return d * (r[5] / r[4] - 1) - COST / r[4]

    def hold3(r, d):
        return None if r[6] is None else d * r[6] - COST / r[4]

    def show(nm, sel, dir_fn):
        out = []
        for fn, lab in ((intraday, "日盤開→收"), (hold3, "開盤進抱3天")):
            xs = [fn(r, dir_fn(r)) for r in sel]
            xs = [x for x in xs if x is not None]
            if len(xs) < 8:
                out.append(f"{lab} 樣本不足")
                continue
            m = statistics.mean(xs)
            # sign-flip p（雙尾）
            rng = random.Random(65)
            sims = [statistics.mean(x * rng.choice((1, -1)) for x in xs) for _ in range(3000)]
            p = (sum(abs(s) >= abs(m) for s in sims) + 1) / 3001
            out.append(f"{lab} {len(xs):3d} 筆 勝率 {sum(x > 0 for x in xs) / len(xs):4.0%} 每筆 {m:+.2%}（≈{m * 40000:+4.0f} 點）p＝{p:.3f}")
        L.append(f"  {nm:30s} " + " ｜ ".join(out))

    sgn = lambda x: 1 if x > 0 else -1  # noqa: E731
    L.append("\n== 對照：所有夜晚 ==")
    allr = [r for r in rows]
    show("一律做多", allr, lambda r: 1)
    show("順著整晚方向", allr, lambda r: sgn(r[2]))
    for k in (1.5, 2.0, 3.0):
        sel = [r for r, v in zip(rows, vr) if v is not None and v >= k]
        L.append(f"\n== 夜盤量 ≥{k}x：{len(sel)} 晚 ==")
        show("順著整晚漲跌", sel, lambda r: sgn(r[2]))
        show("逆著整晚漲跌", sel, lambda r: -sgn(r[2]))
        show("順著夜盤K棒", sel, lambda r: sgn(r[3]))
        show("整晚跌 → 做多（反彈）", [r for r in sel if r[2] < 0], lambda r: 1)
        show("整晚漲 → 做多（延續）", [r for r in sel if r[2] > 0], lambda r: 1)
        show("一律做多（同樣的晚上）", sel, lambda r: 1)
    calm = [r for r, v in zip(rows, vr) if v is not None and v < 1.2 and abs(r[2]) >= 0.01]
    L.append(f"\n== 對照：整晚漲跌 ≥1% 但量平(<1.2x)：{len(calm)} 晚 ==")
    show("順著整晚漲跌", calm, lambda r: sgn(r[2]))
    show("逆著整晚漲跌", calm, lambda r: -sgn(r[2]))
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究65_夜盤爆量.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
