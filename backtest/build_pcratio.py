"""從期交所下載台指選擇權 Put/Call Ratio（每日），存 backtest/pcratio_daily.csv：date,vol_ratio,oi_ratio（%）
可中斷續跑。用法：python -X utf8 backtest/build_pcratio.py"""
import calendar
import csv
import os
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "pcratio_daily.csv")
done = set()
if os.path.exists(OUT):
    done = {r["date"][:7] for r in csv.DictReader(open(OUT, encoding="utf-8"))}
new = not os.path.exists(OUT)
f = open(OUT, "a", encoding="utf-8", newline="")
w = csv.writer(f)
if new:
    w.writerow(["date", "vol_ratio", "oi_ratio"])
y, m = 2001, 12
while (y, m) <= (2026, 11):
    key = f"{y}-{m:02d}"
    if key not in done:
        last = calendar.monthrange(y, m)[1]
        body = urllib.parse.urlencode({"queryStartDate": f"{y}/{m:02d}/01", "queryEndDate": f"{y}/{m:02d}/{last}"}).encode()
        try:
            raw = urllib.request.urlopen(urllib.request.Request("https://www.taifex.com.tw/cht/3/pcRatioDown", data=body,
                                                                headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read()
            rows = list(csv.reader(raw.decode("big5", errors="replace").splitlines()))[1:]
            n = 0
            for r in sorted(rows):
                if len(r) >= 7 and r[0].count("/") == 2:
                    w.writerow([r[0].replace("/", "-"), r[3], r[6]])
                    n += 1
            f.flush()
            print(key, n, flush=True)
        except Exception as e:  # noqa: BLE001
            print(key, "ERR", e, flush=True)
        time.sleep(3)
    m += 1
    if m > 12:
        y, m = y + 1, 1
