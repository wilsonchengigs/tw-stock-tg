"""期交所大額交易人未沖銷部位——台指選擇權 TXO（買權／賣權，所有月份合計）→ backtest/large_trader_txo.csv（由 build_large_trader.py 改）

欄位：date,cp,cat,top5_buy,top5_sell,top10_buy,top10_sell,oi（cp：C 買權／P 賣權）
  cat 0＝全部交易人、1＝特定法人（期交所定義）；到期月份取「999999」（所有契約月份合計）
來源：https://www.taifex.com.tw/cht/3/largeTraderOptDown（POST queryStartDate／queryEndDate，一次一個月）
可續跑：已有的月份跳過，最近 2 個月每次重抓。用法：python -X utf8 backtest/build_large_trader.py [起始年，預設 2004；TXO 大額交易人約從 2004 起]
"""
import calendar
import csv
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "large_trader_txo.csv")
UA = {"User-Agent": "Mozilla/5.0"}
COLS = ["date", "cp", "cat", "top5_buy", "top5_sell", "top10_buy", "top10_sell", "oi"]


def fetch(y, m):
    last = calendar.monthrange(y, m)[1]
    body = urllib.parse.urlencode({"queryStartDate": f"{y}/{m:02d}/01", "queryEndDate": f"{y}/{m:02d}/{last}"}).encode()
    for attempt in range(3):
        try:
            raw = urllib.request.urlopen(urllib.request.Request("https://www.taifex.com.tw/cht/3/largeTraderOptDown", data=body, headers=UA),
                                         timeout=90).read().decode("big5", "replace")
            break
        except Exception as e:  # noqa: BLE001
            print(y, m, "retry", e, flush=True)
            time.sleep(15)
    else:
        return None
    rows = []
    for r in csv.reader(raw.splitlines()[1:]):
        if len(r) < 11 or r[1].strip() != "TXO" or r[4].strip() != "999999":
            continue
        try:
            rows.append([r[0].strip().replace("/", "-"), "C" if "買" in r[3] else "P", r[5].strip()] + [int(x.strip().replace(",", "")) for x in r[6:11]])
        except ValueError:
            continue
    return rows


def main():
    y0 = int(sys.argv[1]) if len(sys.argv) > 1 else 2004
    old = list(csv.DictReader(open(OUT, encoding="utf-8"))) if os.path.exists(OUT) else []
    t = date.today()
    recent = {f"{t.year}-{t.month:02d}", f"{t.year if t.month > 1 else t.year - 1}-{(t.month - 1) or 12:02d}"}
    keep = [r for r in old if r["date"][:7] not in recent]
    done = {r["date"][:7] for r in keep}
    allrows = [[r[c] for c in COLS] for r in keep]
    y, m = y0, 1
    while (y, m) <= (t.year, t.month):
        key = f"{y}-{m:02d}"
        if key not in done:
            rows = fetch(y, m)
            if rows is not None:
                allrows += rows
                print(key, len(rows), flush=True)
            time.sleep(2)
        m += 1
        if m > 12:
            y, m = y + 1, 1
    allrows.sort(key=lambda r: (r[0], r[1], r[2]))
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLS)
        w.writerows(allrows)
    print(len(allrows), "列", allrows[0][0] if allrows else "", "～", allrows[-1][0] if allrows else "")


if __name__ == "__main__":
    main()
