"""研究 522：研究 165 重跑（521）冒出的兩條日內順勢規則的穩健度
D 早盤趨勢 → 午盤順勢：09:05→T 漲跌 ≥ x → T(+延後) 進順勢，13:30 出
   T ∈ 10:00／10:30／11:00／11:30／12:00；x ∈ 0.3／0.5／0.75／1.0%；延後 0／5／10 分
E 盤中第一次跌（漲）≥ x（相對 09:05）→ 順勢（做空／做多），13:30 出；x ∈ 0.75／1.0／1.5%；延後 0／5／10 分；只做在 13:00 前
加權 1 分 K 2010～2026；成本 3 點；四段＋逐年正的比例；VIX（前一晚美國）≥18／<18 分組
另：近 33 天台指期真實 1 分 K（tx_1min.csv 日盤）抽驗 D 11:00／0.5%、E 1%
用法：python -X utf8 backtest/research_522_intraday_trend_robust.py
"""
import csv, gzip, io, os, sys
from collections import defaultdict
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from research_514_pattern_regime import yahoo
COST = 3.0
SEGS = [("2010", "2015"), ("2015", "2020"), ("2020", "2024"), ("2024", "2027")]


def load_idx():
    raw = defaultdict(list)
    for fn in sorted(os.listdir(os.path.join(HERE, "taiex_1min"))):
        if fn.endswith(".csv.gz"):
            for r in csv.DictReader(io.TextIOWrapper(gzip.open(os.path.join(HERE, "taiex_1min", fn)), encoding="utf-8")):
                t = r["time"]; raw[r["date"]].append((int(t[:2]) * 60 + int(t[3:5]) - 540, float(r["close"])))
    return {d: np.array(v) for d, v in raw.items() if len(v) >= 200}


def load_tx():
    raw = defaultdict(list)
    for r in csv.DictReader(open(os.path.join(HERE, "tx_1min.csv"), encoding="utf-8")):
        if r["session"] != "day":
            continue
        t = r["ts"][11:16]; raw[r["trade_day"]].append((int(t[:2]) * 60 + int(t[3:5]) - 540, float(r["close"])))
    return {d: np.array(sorted(v)) for d, v in raw.items() if len(v) >= 200}


def at(a, mm):
    j = int(np.searchsorted(a[:, 0], mm, side="right")) - 1
    return a[max(j, 0), 1]


def rule_D(a, T, x, dl, close_m=270):
    o = at(a, 5); m = at(a, T); tr = m / o - 1
    if abs(tr) < x:
        return None
    s = 1 if tr > 0 else -1; e = at(a, T + dl); c = at(a, close_m)
    return s * (c / e - 1) - COST / e


def rule_E(a, x, dl, close_m=270):
    o = at(a, 5)
    for mm, cl in a:
        if mm < 6 or mm > 240:
            continue
        ch = cl / o - 1
        if abs(ch) >= x:
            s = 1 if ch > 0 else -1; e = at(a, mm + dl); c = at(a, close_m)
            return s * (c / e - 1) - COST / e
    return None


def summarize(lst):
    v = np.array([x[1] for x in lst])
    yrs = defaultdict(float)
    for d, r in lst:
        yrs[d[:4]] += r
    seg = " ".join(f"{np.mean([r for d, r in lst if a <= d < z])*100:+.3f}" for a, z in SEGS)
    t = v.mean() / (v.std(ddof=1) / np.sqrt(len(v)))
    return f"{len(v):5d} 筆 {v.mean()*100:+.3f}%（≈{v.mean()*39000:+4.0f} 點）t {t:+.2f} 勝率 {(v>0).mean()*100:.0f}%｜四段 {seg}｜正的年 {sum(1 for y in yrs.values() if y>0)}/{len(yrs)}"


def main():
    days = load_idx(); ds = sorted(days)
    vix = yahoo("VIX.json"); vk = np.array(sorted(vix))
    vhi = {d: vix[vk[np.searchsorted(vk, d) - 1]] >= 18 for d in ds}
    out = [__doc__, f"加權 1 分 K {ds[0]}～{ds[-1]} {len(ds)} 天"]
    out.append("\n===== D 早盤趨勢 → 午盤順勢 =====")
    for T, lab in ((60, "10:00"), (90, "10:30"), (120, "11:00"), (150, "11:30"), (180, "12:00")):
        for x in (0.003, 0.005, 0.0075, 0.01):
            for dl in ((0, 5, 10) if (T == 120 and x == 0.005) else (0, 10)):
                lst = [(d, r) for d in ds if (r := rule_D(days[d], T, x, dl)) is not None]
                out.append(f"  {lab} ≥{x*100:.2f}% 延後{dl:2d}：{summarize(lst)}")
    lst = [(d, rule_D(days[d], 120, 0.005, 0)) for d in ds]; lst = [z for z in lst if z[1] is not None]
    out.append(f"  11:00/0.5% VIX≥18：{summarize([z for z in lst if vhi[z[0]]])}")
    out.append(f"  11:00/0.5% VIX<18：{summarize([z for z in lst if not vhi[z[0]]])}")
    up = []; dn = []
    for d in ds:
        a = days[d]; tr = at(a, 120) / at(a, 5) - 1; r = rule_D(a, 120, 0.005, 0)
        if r is not None:
            (up if tr > 0 else dn).append((d, r))
    out.append(f"  11:00/0.5% 只看上漲做多：{summarize(up)}")
    out.append(f"  11:00/0.5% 只看下跌做空：{summarize(dn)}")
    out.append("\n===== E 盤中第一次漲跌 ≥x → 順勢 =====")
    for x in (0.0075, 0.01, 0.015):
        for dl in (0, 5, 10):
            lst = [(d, r) for d in ds if (r := rule_E(days[d], x, dl)) is not None]
            out.append(f"  ≥{x*100:.2f}% 延後{dl:2d}：{summarize(lst)}")
    for x in (0.01,):
        up = []; dn = []
        for d in ds:
            a = days[d]; o = at(a, 5); r = rule_E(a, x, 0)
            if r is None:
                continue
            first = next(cl for mm, cl in a if 6 <= mm <= 240 and abs(cl / o - 1) >= x)
            (up if first > o else dn).append((d, r))
        out.append(f"  ≥1% 只看漲→做多：{summarize(up)}")
        out.append(f"  ≥1% 只看跌→做空：{summarize(dn)}")
        lst = up + dn
        out.append(f"  ≥1% VIX≥18：{summarize([z for z in lst if vhi[z[0]]])}")
        out.append(f"  ≥1% VIX<18：{summarize([z for z in lst if not vhi[z[0]]])}")
    tx = load_tx()
    out.append(f"\n===== 台指期真實 1 分 K 抽驗（{len(tx)} 天，13:30 出）=====")
    for nm, f in (("D 11:00/0.5%", lambda a: rule_D(a, 120, 0.005, 0)), ("E 1%", lambda a: rule_E(a, 0.01, 0))):
        r1 = [(d, f(tx[d])) for d in sorted(tx)]; r1 = [z for z in r1 if z[1] is not None]
        r2 = [(d, f(days[d])) for d in sorted(tx) if d in days]; r2 = [z for z in r2 if z[1] is not None]
        if r1:
            v = np.array([z[1] for z in r1])
            out.append(f"  {nm} 台指期：{len(v)} 筆 每筆 {v.mean()*100:+.3f}% 勝率 {(v>0).mean()*100:.0f}%")
        if r2:
            v = np.array([z[1] for z in r2])
            out.append(f"  {nm} 同期加權：{len(v)} 筆 每筆 {v.mean()*100:+.3f}% 勝率 {(v>0).mean()*100:.0f}%")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究522_日內順勢穩健度.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
