"""證交所除權除息計算結果表（TWT49U）→ backtest/exright.csv（研究 302：個股還原股利）

一年一次請求（startDate～endDate 整年），欄位：date（西元）、code、pre_close（除權息前收盤價）、ref（除權息參考價）、kind（權／息／權息）
還原方式：除權息日的報酬改成 收盤 ÷ 參考價 − 1（而不是 收盤 ÷ 前收 − 1）
用法：python -X utf8 backtest/build_exright.py [起始年，預設 2012]
"""
import csv
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "exright.csv")


def roc_to_iso(s):
    y, rest = s.split("年")
    m, rest = rest.split("月")
    d = rest.replace("日", "")
    return f"{int(y) + 1911}-{int(m):02d}-{int(d):02d}"


def main():
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 2012
    rows = []
    for y in range(start, 2027):
        u = f"https://www.twse.com.tw/rwd/zh/exRight/TWT49U?startDate={y}0101&endDate={y}1231&response=json"
        for attempt in range(3):
            try:
                j = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=120))
                break
            except Exception as e:  # noqa: BLE001
                print(y, "重試", attempt + 1, e, flush=True)
                time.sleep(10)
        else:
            raise SystemExit(f"{y} 抓不到")
        n = 0
        for r in j.get("data", []):
            try:
                rows.append([roc_to_iso(r[0]), r[1].strip(), float(r[3].replace(",", "")), float(r[4].replace(",", "")), r[6]])
                n += 1
            except (ValueError, IndexError):
                continue
        print(y, j.get("stat"), n, flush=True)
        time.sleep(3)
    rows.sort()
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "code", "pre_close", "ref", "kind"])
        w.writerows(rows)
    print("寫入", OUT, len(rows))


if __name__ == "__main__":
    main()
