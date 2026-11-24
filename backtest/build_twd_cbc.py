"""中央銀行開放資料 BP01D01：新台幣對美元銀行間即期匯率（每日台灣 16:00），1993～，存 backtest/twd_cbc.csv：date,twd
（Yahoo TWD=X／ext_USDTWD 有錯價與週末報價，研究 72 起改用此來源）
用法：python -X utf8 backtest/build_twd_cbc.py
"""
import csv
import json
import os
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
raw = urllib.request.urlopen(urllib.request.Request("https://cpx.cbc.gov.tw/API/DataAPI/Get?FileName=BP01D01",
                                                    headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read()
rows = json.loads(raw.decode("utf-8-sig"))["data"]["dataSets"]
with open(os.path.join(HERE, "twd_cbc.csv"), "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["date", "twd"])
    n = 0
    for r in rows:
        try:
            v = float(r[1])
        except ValueError:
            continue
        w.writerow([f"{r[0][:4]}-{r[0][4:6]}-{r[0][6:]}", v])
        n += 1
print(n, "筆")
