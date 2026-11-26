"""櫃買指數日資料 → backtest/otc_index.csv：date,open,high,low,close
來源：櫃買中心 https://www.tpex.org.tw/www/zh-tw/indexInfo/inx?date=YYYY/MM/01&response=json（一次一個月）
可續跑：已有月份跳過、最近 2 個月重抓。用法：python -X utf8 backtest/build_otc_index.py [起始年，預設 2000]
"""
import csv
import json
import os
import sys
import time
import urllib.request

from refresh_util import recent_months, this_month

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "otc_index.csv")


def main():
    y0 = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    rows = {}
    if os.path.exists(OUT):
        for r in csv.DictReader(open(OUT, encoding="utf-8")):
            if r["date"][:7] not in recent_months():
                rows[r["date"]] = [r[k] for k in ("date", "open", "high", "low", "close")]
    done = {d[:7] for d in rows}
    y, m = y0, 1
    while (y, m) <= this_month():
        key = f"{y}-{m:02d}"
        if key not in done:
            u = f"https://www.tpex.org.tw/www/zh-tw/indexInfo/inx?date={y}%2F{m:02d}%2F01&response=json"
            try:
                d = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=40).read())
                n = 0
                for t in d.get("tables", []):
                    for r in t.get("data", []):
                        dd = r[0].replace("/", "-")
                        if len(dd) == 10:
                            rows[dd] = [dd] + [x.replace(",", "") for x in r[1:5]]
                            n += 1
                print(key, n, flush=True)
            except Exception as e:  # noqa: BLE001
                print(key, "ERR", e, flush=True)
            time.sleep(1.5)
        m += 1
        if m > 12:
            y, m = y + 1, 1
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "open", "high", "low", "close"])
        w.writerows(rows[d] for d in sorted(rows))
    print(len(rows), "天")


if __name__ == "__main__":
    main()
