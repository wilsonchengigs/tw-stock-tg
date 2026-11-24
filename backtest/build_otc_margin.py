"""從櫃買中心抓上櫃融資金額（仟元，今日餘額）每週最後交易日（2007～），存 backtest/otc_margin_weekly.csv：date,amount
可中斷續跑。用法：python -X utf8 backtest/build_otc_margin.py"""
import csv
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402

OUT = os.path.join(HERE, "otc_margin_weekly.csv")
done = set()
if os.path.exists(OUT):
    done = {r["date"] for r in csv.DictReader(open(OUT, encoding="utf-8"))}
new = not os.path.exists(OUT)
f = open(OUT, "a", encoding="utf-8", newline="")
w = csv.writer(f)
if new:
    w.writerow(["date", "amount"])
for d, we in zip(bt.DAYS, bt.WEEK_END):
    if not we or d < "2007-01-01" or d in done:
        continue
    u = f"https://www.tpex.org.tw/www/zh-tw/margin/balance?date={d.replace('-', '%2F')}&response=json"
    try:
        j = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read())
        amt = None
        for t in j.get("tables", []):
            for row in t.get("summary", []):
                if "融資金" in str(row[1]):
                    amt = float(str(row[6]).replace(",", "")) * 1000
        if j.get("date") == d.replace("-", "") and amt:
            w.writerow([d, int(amt)])
            f.flush()
            print(d, int(amt / 1e8), flush=True)
        else:
            print(d, "none", flush=True)
    except Exception as e:  # noqa: BLE001
        print(d, "ERR", e, flush=True)
    time.sleep(1.5)
