"""上市個股每日收盤價（算市場廣度用：上漲／下跌家數、創新高家數、站上均線比例）

來源：證交所 MI_INDEX?type=ALLBUT0999（每日收盤行情，不含權證／牛熊證），一天一次請求
存 backtest/stock_closes/YYYY.csv.gz：date,code,close,change_sign（+／-／空白）；只存 4 碼普通股＋ETF（代號 4～6 碼數字）
可續跑：已抓日期記在 stock_closes/_done.txt（寫進檔案後才標記）；每次請求間隔 2 秒；由新到舊
用法：python -X utf8 backtest/build_stock_closes.py [起始年，預設 2010]
"""
import csv
import gzip
import json
import urllib.request
import io
import os
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "stock_closes")
DONE = os.path.join(OUT, "_done.txt")


def main():
    import bt
    start = sys.argv[1] if len(sys.argv) > 1 else "2010"
    os.makedirs(OUT, exist_ok=True)
    done = set(open(DONE, encoding="utf-8").read().split()) if os.path.exists(DONE) else set()
    days = [d for d in bt.DAYS if d >= start and d not in done][::-1]
    print(f"要抓 {len(days)} 天", flush=True)
    buf, pending = defaultdict(list), []

    def flush():
        for y, rows in buf.items():
            path = os.path.join(OUT, f"{y}.csv.gz")
            old = []
            if os.path.exists(path):
                old = list(csv.reader(io.TextIOWrapper(gzip.open(path), encoding="utf-8")))[1:]
            allr = {(r[0], r[1]): r for r in old}
            for r in rows:
                allr[(r[0], r[1])] = r
            with gzip.open(path, "wt", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(["date", "code", "close", "sign"])
                w.writerows(sorted(allr.values()))
        buf.clear()
        with open(DONE, "a", encoding="utf-8") as f:
            f.write("".join(x + "\n" for x in pending))
        pending.clear()

    for n, d in enumerate(days, 1):
        try:
            u = f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={d.replace('-', '')}&type=ALLBUT0999&response=json"
            js = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read().decode("utf-8"))  # 不快取，避免記憶體累積
        except Exception as e:  # noqa: BLE001
            print(d, "ERR", e, flush=True)
            time.sleep(20)
            continue
        got = 0
        for t in js.get("tables", []):
            fl = t.get("fields") or []
            if "證券代號" in fl and "收盤價" in fl:
                ic, ip, isg = fl.index("證券代號"), fl.index("收盤價"), fl.index("漲跌(+/-)")
                for r in t.get("data", []):
                    code = str(r[ic]).strip()
                    if not code.isdigit() or not 4 <= len(code) <= 6:
                        continue
                    try:
                        px = float(str(r[ip]).replace(",", ""))
                    except ValueError:
                        continue
                    sg = "+" if "+" in str(r[isg]) else "-" if "-" in str(r[isg]) else ""
                    buf[d[:4]].append([d, code, f"{px:g}", sg])
                    got += 1
        pending.append(d)
        if n % 25 == 0 or n == len(days):
            flush()
            print(f"{n}/{len(days)} 到 {d}（當天 {got} 檔）", flush=True)
        time.sleep(2)
    flush()


if __name__ == "__main__":
    main()
