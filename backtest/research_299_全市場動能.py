"""研究 299：全市場（上市 4 碼普通股）月動能選股

資料：`stock_closes`（2012-12～，**收盤價未還原除權息**，所以報酬少算股利約 3～4%／年；動能排序也被除息稍微干擾）。
每月最後交易日：依 12-1 動能（t-12 月底 → t-1 月底報酬，跳過最近 1 個月）排序，股價 ≥10 元、該月有完整報價者；
十分位等權持有 1 個月；成本：換手部分 × 0.585%（手續費 0.1425%×2 ＋ 證交稅 0.3%）。
比較：等權全市場（同樣未還原）、0050（Yahoo 調整價，含息，2014 起可信）、加權價格指數。
另做 1 個月反轉（最近 1 個月跌最多十分位）。單日報酬 >±11% 視為除權／錯價，該股該月剔除。
用法：python -X utf8 backtest/research_299_全市場動能.py
"""
import csv
import glob
import gzip
import json
import math
import os
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
COST = 0.00585


def load():
    px = defaultdict(dict)
    for f in sorted(glob.glob(os.path.join(HERE, "stock_closes", "*.csv.gz"))):
        for r in csv.DictReader(gzip.open(f, "rt", encoding="utf-8")):
            c = r["code"]
            if len(c) == 4 and not c.startswith("00"):
                try:
                    px[c][r["date"]] = float(r["close"])
                except ValueError:
                    pass
    return px


def main():
    px = load()
    dates = sorted({d for m in px.values() for d in m})
    me = [d for a, d in zip(dates, dates[1:] + ["9999"]) if d[:7] != a[:7]]  # 每月最後交易日
    me = [d for d in me if d[:7] != dates[-1][:7] or d == dates[-1]]
    # 每檔每個月底價格；月內是否有 >±11% 跳動（除權／錯價）
    bad = defaultdict(set)
    for c, m in px.items():
        ds = sorted(m)
        for a, b in zip(ds, ds[1:]):
            if m[a] > 0 and abs(m[b] / m[a] - 1) > 0.11:
                bad[c].add(b[:7])
    mp = {c: {d: m[d] for d in me if d in m} for c, m in px.items()}
    rets = defaultdict(list)  # name -> monthly returns
    prev_hold = {"MOM": set(), "REV": set()}
    rows_out = []
    for k in range(12, len(me) - 1):
        t, t1 = me[k], me[k + 1]
        cand = []
        for c, m in mp.items():
            if not all(x in m for x in (me[k - 12], me[k - 1], t, t1)) or m[t] < 10:
                continue
            if t1[:7] in bad[c] or any(me[j][:7] in bad[c] for j in range(k - 11, k + 1)):
                continue
            mom = m[me[k - 1]] / m[me[k - 12]] - 1
            r1 = m[t] / m[me[k - 1]] - 1
            fwd = m[t1] / m[t] - 1
            cand.append((c, mom, r1, fwd))
        if len(cand) < 200:
            continue
        n10 = len(cand) // 10
        ew = statistics.mean(x[3] for x in cand)
        rets["EW"].append(ew)
        for name, key, rev in (("MOM", 1, True), ("REV", 2, False)):
            top = sorted(cand, key=lambda x: x[key], reverse=rev)[:n10]
            hold = {x[0] for x in top}
            turn = 1 - len(hold & prev_hold[name]) / len(hold)
            prev_hold[name] = hold
            rets[name].append(statistics.mean(x[3] for x in top) - turn * COST)
            rets[name + "_gross"].append(statistics.mean(x[3] for x in top))
        bot = sorted(cand, key=lambda x: x[1])[:n10]
        rets["MOM_LOSER"].append(statistics.mean(x[3] for x in bot))
        rows_out.append(t1)
    # 0050（Yahoo 調整價）同月份
    j = json.load(open(os.path.join(HERE, "0050.TW.json"), encoding="utf-8"))
    tw = timezone(timedelta(hours=8))
    adj = j["indicators"]["adjclose"][0]["adjclose"]
    e50 = {datetime.fromtimestamp(ts, tw).strftime("%Y-%m-%d"): v for ts, v in zip(j["timestamp"], adj) if v}
    r50 = []
    for k in range(12, len(me) - 1):
        t, t1 = me[k], me[k + 1]
        if t1 not in rows_out:
            continue
        r50.append(e50[t1] / e50[t] - 1 if t in e50 and t1 in e50 else None)
    out = [f"研究 299：全市場月動能（{rows_out[0][:7]}～{rows_out[-1][:7]}，{len(rows_out)} 個月；未還原股利）\n"]

    def stat(name, r):
        r = [x for x in r if x is not None]
        g = math.prod(1 + x for x in r)
        yrs = len(r) / 12
        cagr = g ** (1 / yrs) - 1
        lv, pk, mdd = 1.0, 1.0, 0.0
        for x in r:
            lv *= 1 + x
            pk = max(pk, lv)
            mdd = min(mdd, lv / pk - 1)
        sh = statistics.mean(r) / statistics.pstdev(r) * math.sqrt(12)
        return f"{name:<16} 年化 {cagr * 100:+6.1f}%  最大回檔 {mdd * 100:6.1f}%  月 Sharpe {sh:.2f}  ({len(r)} 月)"

    for name, lab in (("MOM", "動能前 10%（扣成本）"), ("MOM_gross", "動能前 10%（未扣）"), ("MOM_LOSER", "動能後 10%"),
                      ("REV", "1 月反轉（扣成本）"), ("EW", "等權全市場")):
        out.append(stat(lab, rets[name]))
    out.append(stat("0050（含息）", r50))
    # 分段
    half = len(rows_out) // 2
    out.append(f"\n前半（～{rows_out[half - 1][:7]}）／後半：")
    for name, lab in (("MOM", "動能前 10%"), ("EW", "等權全市場")):
        out.append("  " + stat(lab + " 前", rets[name][:half]))
        out.append("  " + stat(lab + " 後", rets[name][half:]))
    diff = [a - b for a, b in zip(rets["MOM"], rets["EW"])]
    t = statistics.mean(diff) / (statistics.pstdev(diff) / math.sqrt(len(diff)))
    out.append(f"\n動能（扣成本）− 等權 月超額 {statistics.mean(diff) * 100:+.2f}%（t {t:+.2f}）；勝月 {sum(x > 0 for x in diff)}/{len(diff)}")
    text = "\n".join(out)
    print(text)
    open(os.path.join(HERE, "結果_研究299_全市場動能.txt"), "w", encoding="utf-8").write(text + "\n")


if __name__ == "__main__":
    main()
