"""下載台股 50 大權值股（約 2026-11 的 0050 主要成分，存活者名單）Yahoo 日 K（含還原價）到 backtest/tw50/{代號}.json
注意：名單是「現在」的成分股，歷史上被剔除的股票不在內（存活者偏差），只適合比較策略之間的相對差異
用法：python -X utf8 backtest/build_tw50.py
"""
import json
import os
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "tw50")
TICKERS = ("2330 2317 2454 2308 2382 2881 2891 2882 2303 3711 2412 2886 2884 1216 2357 2885 2892 3231 2345 2880 "
           "3034 2002 2883 2890 3008 2887 1303 1301 2603 3037 5880 2327 2379 3045 4938 2395 6669 2207 1101 2912 "
           "3017 2301 4904 2609 2615 3661 6505 1326 2408 5871").split()


def main():
    os.makedirs(OUT, exist_ok=True)
    for t in TICKERS:
        path = os.path.join(OUT, f"{t}.json")
        if os.path.exists(path):
            continue
        u = f"https://query1.finance.yahoo.com/v8/finance/chart/{t}.TW?period1=0&period2=9999999999&interval=1d&events=div%2Csplit"
        for _ in range(3):
            try:
                d = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read())
                json.dump(d["chart"]["result"][0], open(path, "w"))
                print(t, len(d["chart"]["result"][0]["timestamp"]), flush=True)
                break
            except Exception as e:  # noqa: BLE001
                print(t, "retry", e, flush=True)
                time.sleep(5)
        time.sleep(1)


if __name__ == "__main__":
    main()
