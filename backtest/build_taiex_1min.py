"""從證交所 MI_5MINS_INDEX（每 5 秒／早年每 1 分的加權指數）建加權指數日盤 1 分 K（09:00～13:30）

存 backtest/taiex_1min/YYYY.csv.gz：date,time,open,high,low,close（time＝該分鐘開始 HH:MM，13:30 收盤單獨一根）
- 09:00:00 那一筆是開盤前的參考值（多為昨收／部分成交），不當成 09:00 的開盤價；09:00 K 棒從 09:00:05 起算（早年 1 分資料則用 09:01 的值當 09:00 收）
- 交易日清單取 bt.DAYS（加權日線）；由新到舊抓，可中斷續跑（已抓的日期跳過，進度存 taiex_1min/_done.txt）
- 每次請求間隔 1.5 秒；用 exchangeReport csv 版（rwd json 版會被限速到每天 20 秒以上）
用法：python -X utf8 backtest/build_taiex_1min.py [起始年，預設 2010]
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
OUT = os.path.join(HERE, "taiex_1min")
DONE = os.path.join(OUT, "_done.txt")
URL = "https://www.twse.com.tw/exchangeReport/MI_5MINS_INDEX?response=csv&date={}"  # csv 版回應比 rwd json 快很多


def num(s):
    return float(s.replace(",", ""))


def bars_of(data):
    rows = []
    for r in data:
        t = r[0]
        if len(t) == 5:
            t += ":00"
        try:
            rows.append((t, num(r[1])))
        except ValueError:
            continue
    if not rows:
        return []
    five_sec = any(t[6:8] not in ("00",) for t, _ in rows[:20])
    bars = defaultdict(list)
    for t, v in rows:
        if t == "09:00:00":
            continue  # 開盤前參考值
        hh, mm, ss = int(t[:2]), int(t[3:5]), int(t[6:8])
        if t == "13:30:00":
            key = "13:30"
        elif five_sec:
            key = f"{hh:02d}:{mm:02d}" if ss > 0 else f"{(hh * 60 + mm - 1) // 60:02d}:{(hh * 60 + mm - 1) % 60:02d}"
        else:  # 1 分資料：hh:mm 的值是前一分鐘的收
            m1 = hh * 60 + mm - 1
            key = f"{m1 // 60:02d}:{m1 % 60:02d}"
        bars[key].append(v)
    return [(k, v[0], max(v), min(v), v[-1]) for k, v in sorted(bars.items())]


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
                        if r and r[0].lstrip("=").strip('"')[:2].isdigit() and ":" in r[0]]  # 09 點用 ="09:.." 格式、10 點起沒有 =
                break
            except Exception as e:  # noqa: BLE001
                print(d, "retry", e, flush=True)
                time.sleep(15)
        else:
            continue
        b = bars_of(data)
        if b:
            buf[d[:4]] += [(d, *x) for x in b]
        pending.append(d)
        if n % 20 == 0 or n == len(days):
            for y, rows in buf.items():
                path = os.path.join(OUT, f"{y}.csv.gz")
                old = []
                if os.path.exists(path):
                    old = list(csv.reader(io.TextIOWrapper(gzip.open(path), encoding="utf-8")))[1:]
                allr = {(r[0], r[1]): r for r in old}
                for r in rows:
                    allr[(r[0], r[1])] = [r[0], r[1]] + [f"{x:.2f}" for x in r[2:]]
                with gzip.open(path, "wt", encoding="utf-8", newline="") as f:
                    w = csv.writer(f)
                    w.writerow(["date", "time", "open", "high", "low", "close"])
                    w.writerows(sorted(allr.values()))
            buf.clear()
            with open(DONE, "a", encoding="utf-8") as f:  # 寫進檔案後才標記完成
                f.write("".join(x + "\n" for x in pending))
            pending.clear()
            print(f"{n}/{len(days)} 到 {d}", flush=True)
        time.sleep(1.5)


if __name__ == "__main__":
    main()
