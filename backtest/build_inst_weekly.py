"""從證交所 BFI82U 週報抓三大法人每週買賣超金額（元），存 backtest/inst_weekly.csv：week_end,foreign,trust,dealer,total
week_end＝該週最後交易日；可中斷續跑。用法：python -X utf8 backtest/build_inst_weekly.py"""
import csv
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import bt  # noqa: E402
import report  # noqa: E402

OUT = os.path.join(HERE, "inst_weekly.csv")
done = set()
if os.path.exists(OUT):
    done = {r["week_end"] for r in csv.DictReader(open(OUT, encoding="utf-8"))}
new = not os.path.exists(OUT)
f = open(OUT, "a", encoding="utf-8", newline="")
w = csv.writer(f)
if new:
    w.writerow(["week_end", "foreign", "trust", "dealer", "total"])
starts, ends, prev = {}, {}, None
for d in bt.DAYS:
    k = date.fromisoformat(d).isocalendar()[:2]
    starts.setdefault(k, d)
    ends[k] = d
for k in sorted(starts):
    s, e = starts[k], ends[k]
    if e < "2004-04-07" or e in done:
        continue
    try:
        j = report.get_json(f"https://www.twse.com.tw/rwd/zh/fund/BFI82U?type=week&weekDate={s.replace('-', '')}&response=json")
    except Exception as ex:  # noqa: BLE001
        print(e, "ERR", ex, flush=True)
        continue
    if j.get("stat") != "OK":
        print(e, "none", flush=True)
        continue
    fo = tr = de = to = 0.0
    for r in j.get("data", []):
        name, net = str(r[0]), report.num(r[3])
        if name.startswith("外資"):
            fo += net
        elif name.startswith("投信"):
            tr += net
        elif name.startswith("自營商"):
            de += net
        elif name.startswith("合計"):
            to = net
    w.writerow([e, int(fo), int(tr), int(de), int(to)])
    f.flush()
    print(e, int(fo / 1e8), flush=True)
