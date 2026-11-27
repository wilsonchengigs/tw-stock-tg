"""從證交所 MI_5MINS（每 5 秒委託成交統計；2014-02-23 前約每 1 分）建大盤盤中「累積量」1 分序列（研究 350）

存 backtest/twse_5mins/YYYY.csv.gz：date,time,buy_qty,sell_qty,trades,vol,amt
- 全部是「當天從開盤累積到該分鐘結束」的值（委託買進數量、委託賣出數量、成交筆數、成交數量、成交金額百萬元）
- time 與 taiex_1min 相同慣例：HH:MM＝該分鐘開始；5 秒資料取該分鐘最後一筆（hh:mm:00 算前一分鐘）；
  1 分資料（早年）hh:mm 的值算前一分鐘的收；09:00:00 開盤前那筆略過；13:30 收盤單獨一根
- 交易日清單取 bt.DAYS；由新到舊抓、可中斷續跑（進度 twse_5mins/_done.txt）；每次請求間隔 1.5 秒
用法：python -X utf8 backtest/build_twse_5mins.py [起始年，預設 2010]
"""
import csv
import gzip
import io
import os
import sys
import time
import urllib.request
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "twse_5mins")
DONE = os.path.join(OUT, "_done.txt")
URL = "https://www.twse.com.tw/exchangeReport/MI_5MINS?response=csv&date={}"
COLS = (2, 4, 5, 6, 7)  # 委買量、委賣量、成交筆數、成交量、成交金額


def num(s):
    return float(s.replace(",", ""))


def bars_of(data):
    rows = []
    for r in data:
        t = r[0]
        if len(t) == 5:
            t += ":00"
        try:
            rows.append((t, [num(r[c]) for c in COLS]))
        except (ValueError, IndexError):
            continue
    if not rows:
        return []
    five_sec = any(t[6:8] != "00" for t, _ in rows[:20])
    bars = {}
    for t, v in rows:
        if t == "09:00:00":
            continue
        hh, mm, ss = int(t[:2]), int(t[3:5]), int(t[6:8])
        if t == "13:30:00":
            key = "13:30"
        elif five_sec and ss > 0:
            key = f"{hh:02d}:{mm:02d}"
        else:
            m1 = hh * 60 + mm - 1
            key = f"{m1 // 60:02d}:{m1 % 60:02d}"
        bars[key] = v  # 取該分鐘最後一筆（累積值）
    return sorted(bars.items())


def main():
    start = sys.argv[1] if len(sys.argv) > 1 else "2010"
    os.makedirs(OUT, exist_ok=True)
    done = set(open(DONE, encoding="utf-8").read().split()) if os.path.exists(DONE) else set()
    import bt
    days = [d for d in bt.DAYS if d >= start and d not in done][::-1]
    print(f"要抓 {len(days)} 天", flush=True)
    buf = defaultdict(list)
    pending = []
    for n, d in enumerate(days, 1):
        for attempt in range(3):
            try:
                raw = urllib.request.urlopen(urllib.request.Request(URL.format(d.replace("-", "")),
                                                                    headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read()
                data = [[x.lstrip("=").strip('"') for x in r] for r in csv.reader(raw.decode("big5", errors="replace").splitlines())
                        if r and r[0].lstrip("=").strip('"')[:2].isdigit() and ":" in r[0]]
                break
            except Exception as e:  # noqa: BLE001
                print(d, "retry", e, flush=True)
                time.sleep(15)
        else:
            continue
        for k, v in bars_of(data):
            buf[d[:4]].append([d, k] + [f"{x:.0f}" for x in v])
        pending.append(d)
        if n % 20 == 0 or n == len(days):
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
                    w.writerow(["date", "time", "buy_qty", "sell_qty", "trades", "vol", "amt"])
                    w.writerows(sorted(allr.values()))
            buf.clear()
            with open(DONE, "a", encoding="utf-8") as f:
                f.write("".join(x + "\n" for x in pending))
            pending.clear()
            print(f"{n}/{len(days)} 到 {d}", flush=True)
        time.sleep(1.5)


if __name__ == "__main__":
    main()
