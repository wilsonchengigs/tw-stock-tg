"""從證交所逐週（每週最後交易日）抓上市融資金額與融資維持率（同 report.py 算法），存 backtest/margin_ratio_weekly.csv
可中斷續跑。用法：python -X utf8 backtest/build_margin_ratio.py"""
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import bt  # noqa: E402
import report  # noqa: E402

OUT = os.path.join(HERE, "margin_ratio_weekly.csv")
done = set()
if os.path.exists(OUT):
    done = {r["date"] for r in csv.DictReader(open(OUT, encoding="utf-8"))}
days = [d for d, we in zip(bt.DAYS, bt.WEEK_END) if we and d >= "2001-01-01"]
new = not os.path.exists(OUT)
f = open(OUT, "a", encoding="utf-8", newline="")
w = csv.writer(f)
if new:
    w.writerow(["date", "ratio", "amount"])
for d in days:
    if d in done:
        continue
    try:
        m = report.margin_data(d.replace("-", ""))
    except Exception as e:  # noqa: BLE001
        print(d, "ERR", e, flush=True)
        continue
    if m:
        w.writerow([d, f"{m['ratio']:.2f}", int(m["amount"])])
        f.flush()
        print(d, f"{m['ratio']:.1f}", flush=True)
    else:
        print(d, "none", flush=True)
