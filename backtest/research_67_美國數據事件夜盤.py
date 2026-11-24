"""研究 67：美國數據事件交易（非農、FOMC）——馬克羊「以美國經濟數據公布時間做事件交易」

日曆：backtest/us_events.csv（build_us_events.py；FOMC 官網日期、非農依 BLS 規則推算）
台指期：tx_daily_ohlc.csv（2017-05 起有夜盤）。美東日期 E 的事件落在「E 當天 15:00 開始的夜盤」，期交所記在 E 之後的第一個交易日 D
1. 驗證：事件夜的夜盤振幅（高-低）／前日收、夜盤量比，對比一般夜晚
2. 方向：夜盤整晚漲跌（夜盤收 vs 前日日盤收）→ 交易日 D 的日盤
   - 順勢／逆勢：D 開盤進、D 收盤出；或 D 開盤進抱 3 天
   - 事件前一天收盤就進場「賭方向」沒有意義（方向未知）→ 改看「事件夜大波動之後」：|整晚| ≥ 1% 時順／逆
3. 事件前的跨夜：事件前一個交易日日盤收盤 → D 日盤開盤（多空不明，只看平均絕對值＝持倉風險）
成本：每筆 3 點；檢定：sign-flip（雙尾）
用法：python -X utf8 backtest/research_67_美國數據事件夜盤.py
"""
import csv
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
    ev = defaultdict_list()
    for r in csv.DictReader(open(os.path.join(HERE, "us_events.csv"), encoding="utf-8")):
        ev[r["date"]].append(r["event"])
    # 事件 → 台指期交易日 D（E 之後第一個交易日）
    tag = {}
    for e, kinds in ev.items():
        d = next((x for x in dates if x > e), None)
        if d:
            for k in kinds:
                tag.setdefault(d, set()).add(k)
    rows = []
    for i in range(1, n):
        d, pd = dates[i], dates[i - 1]
        m = near[d]
        nb, db, pc = night[d].get(m), day[d].get(m), day[pd].get(m)
        if not nb or not db or not pc or nb[4] <= 0:
            continue
        c3 = None
        if i + 2 < n:
            g, ok = db[3] / db[0], True
            for j in (i + 1, i + 2):
                mj = near[dates[j]]
                prev = day[dates[j - 1]].get(mj)
                if not prev:
                    ok = False
                    break
                g *= day[dates[j]][mj][3] / prev[3]
            c3 = g - 1 if ok else None
        rows.append(dict(d=d, vol=nb[4], rng=(nb[1] - nb[2]) / pc[3], move=nb[3] / pc[3] - 1, gap=db[0] / pc[3] - 1,
                         o=db[0], c=db[3], c3=c3, tag=tag.get(d, set())))
    for k, r in enumerate(rows):
        xs = [x["vol"] for x in rows[max(0, k - 20):k]]
        r["vr"] = r["vol"] / statistics.mean(xs) if len(xs) >= 15 else None
    rows = [r for r in rows if r["vr"] is not None]
    L = ["研究 67：美國數據事件（非農、FOMC）× 台指期夜盤 → 隔天日盤（2017-05～；成本每筆 3 點）"]

    def grp(nm, sel):
        return nm, sel

    groups = [grp("一般夜晚（無事件）", [r for r in rows if not r["tag"]]),
              grp("非農夜", [r for r in rows if "NFP" in r["tag"]]),
              grp("FOMC 夜", [r for r in rows if "FOMC" in r["tag"]])]
    L.append("\n== 1. 事件夜是否比較大（驗證日曆）==")
    for nm, sel in groups:
        L.append(f"  {nm:12s} {len(sel):4d} 晚  夜盤振幅中位 {statistics.median(r['rng'] for r in sel):.2%}  "
                 f"夜盤量比中位 {statistics.median(r['vr'] for r in sel):.2f}  整晚漲跌絕對值平均 {statistics.mean(abs(r['move']) for r in sel):.2%}  "
                 f"隔天日盤開→收絕對值平均 {statistics.mean(abs(r['c'] / r['o'] - 1) for r in sel):.2%}")

    rng = random.Random(67)

    def test(xs):
        m = statistics.mean(xs)
        sims = [statistics.mean(x * rng.choice((1, -1)) for x in xs) for _ in range(3000)]
        return m, (sum(abs(s) >= abs(m) for s in sims) + 1) / 3001

    def show(nm, sel, dir_fn):
        cells = []
        for lab, fn in (("日盤開→收", lambda r, d: d * (r["c"] / r["o"] - 1) - COST / r["o"]),
                        ("開盤進抱3天", lambda r, d: None if r["c3"] is None else d * r["c3"] - COST / r["o"])):
            xs = [fn(r, dir_fn(r)) for r in sel]
            xs = [x for x in xs if x is not None]
            if len(xs) < 8:
                cells.append(f"{lab} 樣本不足")
                continue
            m, p = test(xs)
            cells.append(f"{lab} {len(xs):3d} 筆 勝率 {sum(x > 0 for x in xs) / len(xs):4.0%} 每筆 {m:+.2%}（≈{m * 40000:+4.0f} 點）p＝{p:.3f}")
        L.append(f"  {nm:26s} " + " ｜ ".join(cells))

    sgn = lambda x: 1 if x > 0 else -1  # noqa: E731
    L.append("\n== 2. 事件夜的方向 → 隔天日盤 ==")
    for nm, sel in groups:
        L.append(f"-- {nm}（{len(sel)} 晚）--")
        show("順著整晚方向", sel, lambda r: sgn(r["move"]))
        show("逆著整晚方向", sel, lambda r: -sgn(r["move"]))
        big = [r for r in sel if abs(r["move"]) >= 0.01]
        show(f"|整晚|≥1% 順勢（{len(big)}）", big, lambda r: sgn(r["move"]))
        show(f"|整晚|≥1% 逆勢（{len(big)}）", big, lambda r: -sgn(r["move"]))
        show("一律做多", sel, lambda r: 1)

    L.append("\n== 3. 跨事件夜持倉的風險（前一日日盤收 → 隔天日盤開，絕對值）==")
    for nm, sel in groups:
        g = [abs(r["gap"]) for r in sel]
        L.append(f"  {nm:12s} 平均 {statistics.mean(g):.2%}  90 分位 {sorted(g)[int(len(g) * .9)]:.2%}  最大 {max(g):.2%}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究67_美國數據事件.txt"), "w", encoding="utf-8").write(out)


def defaultdict_list():
    from collections import defaultdict
    return defaultdict(list)


if __name__ == "__main__":
    main()
