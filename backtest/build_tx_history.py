"""從期交所下載台指期（TX）每日行情（一般交易時段），存 backtest/tx_daily.csv：date,month,close,settle,volume,oi
可中斷續跑（已有的月份跳過）。用法：python -X utf8 backtest/build_tx_history.py"""
import calendar
import csv
import os
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "tx_daily.csv")
done = set()
if os.path.exists(OUT):
    done = {r["date"][:7] for r in csv.DictReader(open(OUT, encoding="utf-8"))}
new = not os.path.exists(OUT)
f = open(OUT, "a", encoding="utf-8", newline="")
w = csv.writer(f)
if new:
    w.writerow(["date", "month", "close", "settle", "volume", "oi"])
y, m = 1998, 7
while (y, m) <= (2026, 11):
    key = f"{y}-{m:02d}"
    if key not in done:
        last = calendar.monthrange(y, m)[1]
        body = urllib.parse.urlencode({"down_type": "1", "commodity_id": "TX", "commodity_id2": "",
                                       "queryStartDate": f"{y}/{m:02d}/01", "queryEndDate": f"{y}/{m:02d}/{last}"}).encode()
        for attempt in range(3):
            try:
                raw = urllib.request.urlopen(urllib.request.Request("https://www.taifex.com.tw/cht/3/futDataDown", data=body,
                                                                    headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read()
                break
            except Exception as e:  # noqa: BLE001
                print(key, "retry", e, flush=True)
                time.sleep(10)
        else:
            continue
        rows = list(csv.reader(raw.decode("big5", errors="replace").splitlines()))[1:]
        n = 0
        for r in rows:
            if len(r) < 12 or r[1].strip() != "TX":
                continue
            session = r[17].strip() if len(r) > 17 else ""
            mon = r[2].strip()
            if session not in ("", "一般") or "/" in mon or "W" in mon:
                continue
            w.writerow([r[0].strip().replace("/", "-"), mon, r[6].strip(), r[10].strip(), r[9].strip(), r[11].strip()])
            n += 1
        f.flush()
        print(key, n, flush=True)
        time.sleep(3)
    m += 1
    if m > 12:
        y, m = y + 1, 1
