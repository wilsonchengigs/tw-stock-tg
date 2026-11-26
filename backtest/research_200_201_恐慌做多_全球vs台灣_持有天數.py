"""研究 200：恐慌做多（P）在「只有台灣跌」vs「全球一起跌」
研究 201：熊市裡 P 要不要抱久一點（D 開盤進 → D+1／D+2／D+3／D+5 開盤出）

資料：研究 148 的台指期近月日盤／夜盤與 S&P（R144.R139.load_tx、R144.us）；S&P 離 250 日高用 GSPC.json 收盤
200 分組：訊號前最後一個 S&P 收盤離 250 日高 > -5%（美股還在高檔＝台灣自己的恐慌）／-5～-10%／≤ -10%（全球修正）；
          觸發類型：只有夜盤、只有 S&P、兩者
201 分組：加權離 250 日高 > -10%／-10～-20%／≤ -20%；各持有天數的每筆、勝率、比 D+1 多出的部分；兩段（1998–2017／2017～）
每筆扣 3 點（同研究 148）
用法：python -X utf8 backtest/research_200_201_恐慌做多_全球vs台灣_持有天數.py
"""
import bisect
import importlib.util
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r148", os.path.join(HERE, "research_148_恐慌連續觸發.py"))
R148 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R148)
import bt  # noqa: E402

COST = R148.COST
g = json.load(open(os.path.join(HERE, "GSPC.json")))
NY = timezone(timedelta(hours=-5))
SP = [(datetime.fromtimestamp(t, NY).strftime("%Y-%m-%d"), p) for t, p in zip(g["timestamp"], g["indicators"]["quote"][0]["close"]) if p]
SPD, SPP = [d for d, _ in SP], [p for _, p in SP]


def sp_dd(day):
    k = bisect.bisect_left(SPD, day) - 1
    return SPP[k] / max(SPP[max(0, k - 249):k + 1]) - 1 if k >= 250 else None


def build():
    dates, day, night, near = R148.R144.R139.load_tx()
    US = R148.R144.us("GSPC.json")
    pos = {d: i for i, d in enumerate(bt.DAYS)}
    rows = []
    for k in range(1, len(dates) - 5):
        d, pd_ = dates[k], dates[k - 1]
        m = near[pd_]
        b = day[d].get(m)
        if not b:
            continue
        nb = night[d].get(m)
        nr = (nb[3] / nb[0] - 1) if nb and nb[4] >= 1000 else None
        u = None
        for back in range(1, 5):
            kk = (datetime.fromisoformat(d) - timedelta(days=back)).strftime("%Y-%m-%d")
            if kk in US:
                u = US[kk]
                break
        tn = nr is not None and nr <= -0.02
        ts = u is not None and u <= -0.02
        if not (tn or ts):
            continue
        rets = {}
        for h in (1, 2, 3, 5):
            bh = day[dates[k + h]].get(m)
            if bh:
                rets[h] = (bh[0] - b[0] - COST) / b[0]
        if 1 not in rets:
            continue
        i = pos.get(d)
        dd = bt.PX[i - 1] / max(bt.PX[max(0, i - 251):i]) - 1 if i and i > 251 else None
        rows.append(dict(d=d, typ="兩者" if (tn and ts) else ("夜盤" if tn else "S&P"), sp=sp_dd(d), dd=dd, r=rets))
    return rows


def stat(rs):
    a = np.array(rs)
    return f"{len(a):3d} 筆  每筆 {a.mean():+.2%}  中位 {np.median(a):+.2%}  勝率 {np.mean(a > 0):.0%}  最差 {a.min():+.1%}"


def main():
    rows = build()
    L = [f"研究 200／201：恐慌做多（{rows[0]['d']}～{rows[-1]['d']}，{len(rows)} 筆，D 開→D+h 開、扣 3 點）"]
    L.append("\n【200】依訊號前 S&P 離 250 日高（D+1 出場）")
    for seg, lo, hi in (("全期", "1998", "2099"), ("1998～2017-05", "1998", "2017-05-15"), ("2017-05～", "2017-05-15", "2099")):
        g2 = [x for x in rows if lo <= x["d"] < hi and x["sp"] is not None]
        L.append(f" {seg}")
        for name, f in (("S&P > -5%（台灣自己恐慌）", lambda v: v > -0.05), ("S&P -5～-10%", lambda v: -0.10 < v <= -0.05), ("S&P ≤ -10%（全球修正）", lambda v: v <= -0.10)):
            rs = [x["r"][1] for x in g2 if f(x["sp"])]
            if rs:
                L.append(f"   {name:<22}{stat(rs)}")
    L.append(" 觸發類型（2017-05～，有夜盤）")
    for t in ("夜盤", "S&P", "兩者"):
        rs = [x["r"][1] for x in rows if x["d"] >= "2017-05-15" and x["typ"] == t]
        if rs:
            L.append(f"   {t:<6}{stat(rs)}")
    L.append(" 加權已熊市（≤-20%）且 S&P > -5%（＝現在這種）：")
    rs = [x for x in rows if x["dd"] is not None and x["dd"] <= -0.2 and x["sp"] is not None and x["sp"] > -0.05]
    if rs:
        L.append("   " + stat([x["r"][1] for x in rs]) + "：" + "、".join(f"{x['d']} {x['r'][1]:+.1%}" for x in rs))

    L.append("\n【201】持有天數 × 加權深度（每筆；括號＝比 D+1 多出的平均）")
    for seg, lo, hi in (("全期", "1998", "2099"), ("1998～2017-05", "1998", "2017-05-15"), ("2017-05～", "2017-05-15", "2099")):
        L.append(f" {seg}")
        for name, f in (("> -10%", lambda v: v > -0.10), ("-10～-20%", lambda v: -0.20 < v <= -0.10), ("≤ -20%（熊市）", lambda v: v <= -0.20)):
            g2 = [x for x in rows if lo <= x["d"] < hi and x["dd"] is not None and f(x["dd"]) and all(h in x["r"] for h in (1, 2, 3, 5))]
            if len(g2) < 5:
                continue
            parts = []
            for h in (1, 2, 3, 5):
                a = np.array([x["r"][h] for x in g2])
                extra = np.array([x["r"][h] - x["r"][1] for x in g2])
                parts.append(f"D+{h} {a.mean():+.2%}／勝 {np.mean(a > 0):.0%}" + (f"（{extra.mean():+.2%}）" if h > 1 else ""))
            L.append(f"   {name:<12}{len(g2):3d} 筆：" + "｜".join(parts))
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究200_201_恐慌做多_全球vs台灣_持有天數.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()


def control():
    """201 對照：同深度的『非訊號日』從 D+1 開盤抱到 D+5 開盤（4 天）的報酬，看延長持有多出的是不是 P 特有；另做去叢集（訊號間隔 >5 天）"""
    dates, day, night, near = R148.R144.R139.load_tx()
    pos = {d: i for i, d in enumerate(bt.DAYS)}
    sigs = {x["d"] for x in build()}
    rows_all = []
    for k in range(1, len(dates) - 5):
        d, m = dates[k], near[dates[k - 1]]
        b1, b5 = day[dates[k + 1]].get(m), day[dates[k + 5]].get(m)
        i = pos.get(d)
        if not (b1 and b5 and i and i > 251):
            continue
        dd = bt.PX[i - 1] / max(bt.PX[i - 251:i]) - 1
        rows_all.append((d, dd, (b5[0] - b1[0]) / b1[0], d in sigs))
    L = ["\n【201 對照】D+1 開→D+5 開 這 4 天：訊號日 vs 同深度非訊號日（+ 訊號去叢集：間隔 >5 個交易日）"]
    for seg, lo, hi in (("全期", "1998", "2099"), ("1998～2017-05", "1998", "2017-05-15"), ("2017-05～", "2017-05-15", "2099")):
        for name, f in (("-10～-20%", lambda v: -0.20 < v <= -0.10), ("≤ -20%", lambda v: v <= -0.20), ("> -10%", lambda v: v > -0.10)):
            g2 = [x for x in rows_all if lo <= x[0] < hi and f(x[1])]
            s = np.array([x[2] for x in g2 if x[3]])
            c = np.array([x[2] for x in g2 if not x[3]])
            last, dec = -99, []
            for idx, x in enumerate(g2):
                if x[3] and idx - last > 5:
                    dec.append(x[2])
                    last = idx
            if len(s) >= 5:
                rng = np.random.default_rng(201)
                null = np.array([rng.choice(c, len(s)).mean() for _ in range(3000)])
                p = np.mean(null >= s.mean())
                L.append(f"  {seg:<13}{name:<10} 訊號 {len(s):3d} 筆 {s.mean():+.2%}｜非訊號 {len(c):4d} 天 {c.mean():+.2%}｜差 {s.mean() - c.mean():+.2%}（p {p:.3f}）｜去叢集 {len(dec)} 筆 {np.mean(dec):+.2%}")
    return L


if __name__ == "__main__":
    add = control()
    print("\n".join(add))
    open(os.path.join(HERE, "結果_研究200_201_恐慌做多_全球vs台灣_持有天數.txt"), "a", encoding="utf-8").write("\n".join(add) + "\n")
