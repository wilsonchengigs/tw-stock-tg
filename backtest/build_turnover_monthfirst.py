"""每月第一個交易日的上市個股成交金額（研究 307：52 週高點選股流動性門檻）

來源：證交所 MI_INDEX（與 stock_closes 同一支），只抓每月第一個交易日，存 backtest/turnover_monthfirst.csv（date,code,amount 元）。
可續跑：已抓的日期跳過；請求間隔 2 秒。
用法：python -X utf8 backtest/build_turnover_monthfirst.py
"""
import csv
import glob
import gzip
import io
import json
import os
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "turnover_monthfirst.csv")


def main():
    dates = set()
    for f in glob.glob(os.path.join(HERE, "stock_closes", "*.csv.gz")):
        for r in csv.reader(io.TextIOWrapper(gzip.open(f), encoding="utf-8")):
            if r[0] != "date":
                dates.add(r[0])
    dates = sorted(dates)
    firsts = [d for a, d in zip([""] + dates, dates) if d[:7] != a[:7]]
    have = set()
    if os.path.exists(OUT):
        have = {r["date"] for r in csv.DictReader(open(OUT, encoding="utf-8"))}
    todo = [d for d in firsts if d not in have]
    print("要抓", len(todo), flush=True)
    new = not os.path.exists(OUT)
    with open(OUT, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["date", "code", "amount"])
        for n, d in enumerate(todo, 1):
            u = f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={d.replace('-', '')}&type=ALLBUT0999&response=json"
            for k in range(3):
                try:
                    js = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=120))
                    break
                except Exception as e:  # noqa: BLE001
                    print(d, "重試", e, flush=True)
                    time.sleep(15)
            else:
                continue
            for t in js.get("tables", []):
                fl = t.get("fields") or []
                if "證券代號" in fl and "成交金額" in fl:
                    ic, ia = fl.index("證券代號"), fl.index("成交金額")
                    for r in t.get("data", []):
                        c = str(r[ic]).strip()
                        if c.isdigit() and len(c) == 4:
                            try:
                                w.writerow([d, c, int(str(r[ia]).replace(",", ""))])
                            except ValueError:
                                pass
            f.flush()
            if n % 20 == 0:
                print(n, d, flush=True)
            time.sleep(2)


if __name__ == "__main__":
    main()
